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

from kokoro import KPipeline

app = Flask(__name__)
stop_event = threading.Event()

print("[Sidecar] Initializing Kokoro Pipeline (this may take a moment to download weights on first run...)")
# 'a' => American English, 'b' => British English
pipeline = KPipeline(lang_code='a') 

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
    
    # Handle synthesis and playback in a separate thread
    def play_audio():
        print("[Sidecar] Playback started")
        try:
            # Generate audio chunks
            generator = pipeline(text, voice=voice, speed=speed)
            for i, (gs, ps, audio) in enumerate(generator):
                if stop_event.is_set():
                    print("[Sidecar] Playback interrupted")
                    break
                print(f"[Sidecar] Playing chunk {i}...")
                sd.play(audio, samplerate=24000)
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

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "sidecar": "kokoro-tts"})

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    
    print(f"[Sidecar] Starting Kokoro TTS server on port {args.port}")
    app.run(host="127.0.0.1", port=args.port)
