import os
import sys
import builtins
import threading
import argparse
from flask import Flask, request, jsonify

# Force unbuffered output so Windows doesn't swallow logs until the buffer fills
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    builtins.print(*args, **kwargs)

# Redirect stderr to stdout so that Python tracebacks and error output are
# captured by the Tauri sidecar log (which reads stdout line-by-line with
# flush=True). Without this, buffered stderr output is often lost on Windows
# when a PyInstaller --onefile process crashes before the buffer is flushed.
sys.stderr = sys.stdout

import sounddevice as sd
import numpy as np

# Kokoro-82M is small, but needs its weights and voices.
# We'll handle both development and frozen (PyInstaller executable) paths.

def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        # Running as a PyInstaller executable
        return sys._MEIPASS
    else:
        # Running from source
        return os.path.dirname(os.path.abspath(__file__))

BUNDLE_DIR = get_bundle_dir()
MODEL_DIR = os.path.join(BUNDLE_DIR, "model")

from kokoro import KPipeline

app = Flask(__name__)
stop_event = threading.Event()
pipeline = None
request_counter = 0

def get_pipeline():
    global pipeline
    if pipeline is None:
        print("[Sidecar] Initializing Kokoro Pipeline (this may take a moment to download weights on first run...)")
        try:
            pipeline = KPipeline(lang_code='a')
            print("[Sidecar] Pipeline initialized successfully.")
        except Exception as e:
            print(f"[Sidecar] CRITICAL: Failed to initialize Pipeline: {e}")
            raise e
    return pipeline

def cleanup_zombies():
    """ Force-kills any previous instances using a PID file. """
    pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kokoro.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            if old_pid != os.getpid():
                print(f"[Sidecar] Cleaning up zombie process {old_pid}...")
                if sys.platform == "win32":
                    os.system(f"taskkill /F /PID {old_pid} /T")
                else:
                    import signal
                    os.kill(old_pid, signal.SIGKILL)
        except Exception as e:
            print(f"[Sidecar] Cleanup warning: {e}")
    
    # Write current PID
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except:
        pass

# Initialize
cleanup_zombies()

@app.route("/tts", methods=["POST"])
def tts():
    # Stop any previous playback immediately
    stop_event.set()
    sd.stop()
    
    p = get_pipeline()
    data = request.json or {}
    text = data.get("text", "")
    speed = float(data.get("speed", 1.0))
    voice = data.get("voice", "am_fenrir")
    volume = float(data.get("volume", 1.0))
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    print(f"[Sidecar] Synthesizing: '{text[:20]}...' (V:{voice}, S:{speed}, Vol:{volume})")
    
    # Small pause to let previous workers exit gracefully
    import time
    time.sleep(0.1)
    stop_event.clear()
    
    import queue
    audio_queue = queue.Queue(maxsize=10)

    def generator_worker():
        """ Thread that generates audio tensors as fast as possible. """
        try:
            generator = p(text, voice=voice, speed=speed)
            for i, (gs, ps, audio) in enumerate(generator):
                if stop_event.is_set():
                    break
                
                # Push the raw tensor and its index into the queue
                audio_queue.put((i, audio))
                print(f"[Sidecar] Generated chunk {i} (queued)")
            
            # Signal end of generation
            audio_queue.put((None, None))
        except Exception as e:
            print(f"[STATUS] ERROR: {e}")
            import traceback
            traceback.print_exc()
            audio_queue.put((None, None))

    def playback_worker():
        """ Thread that consumes from the queue and plays audio. """
        print("[STATUS] START")
        try:
            while not stop_event.is_set():
                try:
                    i, audio = audio_queue.get(timeout=1.0)
                except queue.Empty:
                    if stop_event.is_set(): break
                    continue
                
                if i is None: # End of stream
                    break
                
                # Convert to NumPy/float32 and apply volume
                played_audio = (audio * volume).cpu().numpy().astype(np.float32)
                
                # Print status for frontend parsing
                max_val = float(np.max(np.abs(played_audio)))
                print(f"[Sidecar] Chunk {i} | Max: {max_val:.4f} | RMS: {float(np.sqrt(np.mean(played_audio**2))):.4f}")
                
                try:
                    sd.play(played_audio, samplerate=24000)
                    sd.wait()
                except Exception as playback_err:
                    print(f"[STATUS] ERROR: {playback_err}")
                
                audio_queue.task_done()
        except Exception as e:
            print(f"[STATUS] ERROR: {e}")
            
        print("[STATUS] FINISHED")

    # Start both workers
    threading.Thread(target=generator_worker, daemon=True).start()
    threading.Thread(target=playback_worker, daemon=True).start()
    
    return jsonify({"status": "ok"})

@app.route("/stop", methods=["POST"])
def stop():
    print("[Sidecar] Stopping playback")
    stop_event.set()
    sd.stop()
    return jsonify({"status": "stopped"})

@app.route("/devices", methods=["GET"])
def get_devices():
    try:
        devices = sd.query_devices()
        outputs = []
        for d in devices:
            if d['max_output_channels'] > 0:
                outputs.append({"id": d['index'], "name": d['name']})
        
        # In dict form, sd.default.device is a tuple: (input_device_id, output_device_id)
        current_out = sd.default.device[1]
        
        # If current_out is a valid list matching an index, fallback
        if current_out is None and len(outputs) > 0:
            current_out = outputs[0]['id']
            
        return jsonify({"devices": outputs, "current": current_out})
    except Exception as e:
        print(f"[Sidecar] Error fetching devices: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/devices", methods=["POST"])
def set_device():
    data = request.json
    device_id = data.get("id")
    if device_id is not None:
        try:
            # sd.default.device is (input, output)
            sd.default.device = (sd.default.device[0], int(device_id))
            print(f"[Sidecar] Set audio output device to {device_id}")
            return jsonify({"status": "ok", "current": device_id})
        except Exception as e:
            print(f"[Sidecar] Error setting device: {e}")
            return jsonify({"error": str(e)}), 400
    return jsonify({"error": "No device id provided"}), 400

@app.route("/test_audio", methods=["POST"])
def test_audio():
    print("[Sidecar] Playing test audio beep...")
    try:
        data = request.json or {}
        volume = float(data.get("volume", 1.0))
        
        fs = 44100
        duration = 0.5
        t = np.linspace(0, duration, int(fs * duration), False)
        envelope = np.concatenate([
            np.linspace(0, 1, int(fs * 0.01)),
            np.ones(int(fs * 0.48)),
            np.linspace(1, 0, int(fs * 0.01))
        ])
        note = np.sin(440 * t * 2 * np.pi) * 0.1 * envelope * volume
        
        # Stats
        max_val = np.max(np.abs(note))
        print(f"[Sidecar] Test Beep | Max: {max_val:.4f} | Vol: {volume}")
        
        sd.play(note, fs)
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[Sidecar] Test audio ERROR: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "sidecar": "kokoro-tts"})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    
    print(f"[Sidecar] Starting Kokoro TTS server on port {args.port}")
    # Use threaded=True to ensure one hanging request doesn't block the whole server
    app.run(host="127.0.0.1", port=args.port, threaded=True)
