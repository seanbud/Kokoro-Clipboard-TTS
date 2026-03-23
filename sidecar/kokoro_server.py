import os
import sys
import threading
import argparse
from flask import Flask, request, jsonify
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

app = Flask(__name__)
stop_event = threading.Event()

# Placeholder for Kokoro model instance
# model = Kokoro(os.path.join(MODEL_DIR, "kokoro-v0.19.onnx"), 
#                voices=os.path.join(MODEL_DIR, "voices.json"))
model = None

@app.route("/tts", methods=["POST"])
def tts():
    data = request.json
    text = data.get("text", "")
    speed = data.get("speed", 1.0)
    voice = data.get("voice", "am_fenrir")
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    print(f"[Sidecar] Synthesizing: {text[:50]}... (Voice: {voice}, Speed: {speed})")
    
    # Reset stop event for new playback
    stop_event.clear()
    
    # Handle synthesis and playback in a separate thread to not block HTTP response
    # In a real app, you might want to return a stream or handle queuing.
    # For MVP, we'll fire-and-forget the audio playback.
    
    # mock logic for the template:
    def play_audio():
        # This is where you'd call kokoro.generate()
        # and sd.play(audio, sample_rate)
        print("[Sidecar] Playback started")
        # Simulate wait
        # stop_event.wait(timeout=5)
        print("[Sidecar] Playback finished")

    threading.Thread(target=play_audio, daemon=True).start()
    
    return jsonify({"status": "ok"})

@app.route("/stop", methods=["POST"])
def stop():
    print("[Sidecar] Stopping playback")
    stop_event.set()
    sd.stop()
    return jsonify({"status": "stopped"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "sidecar": "kokoro-tts"})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    
    print(f"[Sidecar] Starting Kokoro TTS server on port {args.port}")
    app.run(host="127.0.0.1", port=args.port)
