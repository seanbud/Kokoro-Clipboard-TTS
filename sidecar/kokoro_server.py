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

@app.route("/tts", methods=["POST"])
def tts():
    p = get_pipeline()
    data = request.json
    text = data.get("text", "")
    speed = data.get("speed", 1.0)
    voice = data.get("voice", "am_fenrir")
    volume = data.get("volume", 1.0)
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    print(f"[Sidecar] Synthesizing: {text[:50]}... (Voice: {voice}, Speed: {speed}, Vol: {volume})")
    
    # Reset stop event for new playback
    stop_event.clear()
    
    # Handle synthesis and playback in a separate thread
    def play_audio():
        print("[Sidecar] Playback started")
        try:
            # Generate audio chunks
            generator = p(text, voice=voice, speed=speed)
            for i, (gs, ps, audio) in enumerate(generator):
                if stop_event.is_set():
                    print("[Sidecar] Playback interrupted")
                    break
                print(f"[Sidecar] Playing chunk {i}...")
                
                # Apply volume
                played_audio = audio * volume
                
                sd.play(played_audio, samplerate=24000)
                sd.wait() # Wait for this chunk to finish playing before next
        except Exception as e:
            print(f"[Sidecar] Error during synthesis/playback: {e}")
            
        print("[Sidecar] Playback finished")

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
        volume = data.get("volume", 1.0)
        
        fs = 44100
        duration = 0.5
        # Generate a nice soft 440Hz sine wave (A4 note)
        t = np.linspace(0, duration, int(fs * duration), False)
        # Apply a simple envelope so it doesn't click sharply
        envelope = np.concatenate([
            np.linspace(0, 1, int(fs * 0.05)),
            np.ones(int(fs * 0.4)),
            np.linspace(1, 0, int(fs * 0.05))
        ])
        note = np.sin(440 * t * 2 * np.pi) * 0.1 * envelope * volume
        sd.play(note, fs)
        # we don't block here, let it play asynchronously
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[Sidecar] Test audio error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "sidecar": "kokoro-tts"})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    
    print(f"[Sidecar] Starting Kokoro TTS server on port {args.port}")
    app.run(host="127.0.0.1", port=args.port)
