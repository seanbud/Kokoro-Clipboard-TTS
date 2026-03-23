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

def watchdog():
    """ Monitors the parent process and exits if it dies. """
    import time
    initial_ppid = os.getppid()
    # If ppid is 1, we are already orphaned
    if initial_ppid <= 1 and sys.platform != "win32":
        return

    print(f"[Sidecar] Watchdog active. Monitoring parent: {initial_ppid}")
    while True:
        try:
            # Check if parent is still alive
            if sys.platform == "win32":
                # On Windows, os.kill(child, 0) works if we have permissions
                os.kill(initial_ppid, 0)
            else:
                if os.getppid() != initial_ppid:
                    raise OSError()
        except OSError:
            print("[Sidecar] Parent process lost. Exiting...")
            os._exit(0)
        time.sleep(5)

# Initialize
cleanup_zombies()
threading.Thread(target=watchdog, daemon=True).start()

@app.route("/tts", methods=["POST"])
def tts():
    p = get_pipeline()
    data = request.json or {}
    text = data.get("text", "")
    speed = float(data.get("speed", 1.0))
    voice = data.get("voice", "am_fenrir")
    volume = float(data.get("volume", 1.0))
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    print(f"[Sidecar] Synthesizing: '{text[:20]}...' (V:{voice}, S:{speed}, Vol:{volume})")
    
    stop_event.clear()
    
    def play_audio():
        print("[Sidecar] Playback started")
        try:
            generator = p(text, voice=voice, speed=speed)
            for i, (gs, ps, audio) in enumerate(generator):
                if stop_event.is_set():
                    print("[Sidecar] Playback interrupted")
                    break
                
                # audio is a PyTorch Tensor from Kokoro. 
                # Convert to NumPy for sounddevice processing.
                played_audio = (audio * volume).cpu().numpy().astype(np.float32)
                
                # Stats for debugging silence
                max_val = float(np.max(np.abs(played_audio)))
                rms = float(np.sqrt(np.mean(played_audio**2)))
                print(f"[Sidecar] Chunk {i} | Len: {len(played_audio)} | Max: {max_val:.4f} | RMS: {rms:.4f} | Type: {played_audio.dtype}")
                
                try:
                    sd.play(played_audio, samplerate=24000)
                    sd.wait()
                except Exception as playback_err:
                    print(f"[Sidecar] PLAYBACK ERROR on chunk {i}: {playback_err}")
        except Exception as e:
            print(f"[Sidecar] ERROR in main loop: {e}")
            import traceback
            traceback.print_exc()
            
        print("[Sidecar] Playback thread finished")

    threading.Thread(target=play_audio, daemon=True).start()
    
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
