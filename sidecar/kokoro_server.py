import os
import sys
import builtins
import threading
import argparse
import uuid
from flask import Flask, request, jsonify

try:
    from .tts_protocol import encode_tts_event, normalize_synthesis_segments
    from .audio_playback import AudioChunk, play_queued_audio
    from .playback_session import PlaybackSessionController
    from .pipeline_loader import create_offline_pipeline
    from .sonic_speed import SonicSpeedProcessor
except ImportError:
    # Script/PyInstaller execution places the sidecar directory on sys.path.
    from tts_protocol import encode_tts_event, normalize_synthesis_segments
    from audio_playback import AudioChunk, play_queued_audio
    from playback_session import PlaybackSessionController
    from pipeline_loader import create_offline_pipeline
    from sonic_speed import SonicSpeedProcessor

# Make stdout write-through (unbuffered) so every write is flushed to disk
# immediately. This is critical on Windows where PyInstaller --onefile processes
# can terminate before a block-buffered stdout drains, causing log truncation.
try:
    sys.stdout.reconfigure(write_through=True)
except Exception:
    pass  # frozen exe may raise UnsupportedOperation or other errors; best-effort

# Force unbuffered output so Windows doesn't swallow logs until the buffer fills
def print(*args, **kwargs):
    kwargs.setdefault('flush', True)
    builtins.print(*args, **kwargs)

# Redirect stderr to stdout so that Python tracebacks and error output are
# captured by the Tauri sidecar log (which reads stdout line-by-line).
# Without this, buffered stderr output is often lost on Windows when a
# PyInstaller --onefile process crashes before the buffer is flushed.
sys.stderr = sys.stdout

# On Windows, PyInstaller --onefile extracts everything to a temp directory
# (sys._MEIPASS). Windows does NOT automatically search subdirectories of
# _MEIPASS when loading DLLs, so packages like espeak-ng, torch, and
# sounddevice fail to find their native libraries.  We register every
# relevant subdirectory via os.add_dll_directory() so the OS loader can
# find them.  We also set ESPEAK_DATA_PATH so phonemizer/misaki can locate
# the espeak-ng voice data inside the bundle.
if sys.platform == "win32" and getattr(sys, "frozen", False):
    _bundle = sys._MEIPASS
    # Directories known to contain native DLLs in a collected PyInstaller bundle
    _dll_search = [
        _bundle,
        os.path.join(_bundle, "torch", "lib"),          # torch_cpu.dll, c10.dll …
        os.path.join(_bundle, "espeakng_loader"),        # espeak-ng.dll
    ]
    for _d in _dll_search:
        if os.path.isdir(_d):
            try:
                os.add_dll_directory(_d)
            except Exception:
                pass
    # Point espeak-ng to its data directory so phonemizer initialises correctly
    _espeak_data = os.path.join(_bundle, "espeakng_loader", "espeak-ng-data")
    if os.path.isdir(_espeak_data):
        os.environ.setdefault("ESPEAK_DATA_PATH", _espeak_data)

try:
    import sounddevice as sd
    import numpy as np
except Exception:
    import traceback
    import time
    for line in traceback.format_exc().splitlines():
        print(line)
    time.sleep(1)  # give the Tauri pipe reader time to drain before exit
    sys.exit(1)

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

try:
    from kokoro import KModel, KPipeline
except Exception:
    import traceback
    import time
    for line in traceback.format_exc().splitlines():
        print(line)
    time.sleep(1)  # give the Tauri pipe reader time to drain before exit
    sys.exit(1)

app = Flask(__name__)
pipeline = None
pipeline_lock = threading.Lock()
inference_lock = threading.Lock()
request_counter = 0
session_controller = PlaybackSessionController()


def emit_tts_event(event, request_id, **data):
    """Write one machine-readable lifecycle event without clipboard content."""
    print(encode_tts_event(event, request_id, **data))


def validate_control_request(data):
    """Reject delayed controls intended for a playback session that is no longer active."""
    request_id = str(data.get("request_id") or "").strip()
    session, error = session_controller.control_target(request_id)
    if error == "no_active_session":
        return None, (
            jsonify({"error": "There is no active playback request"}),
            409,
        )
    if error == "stale_session":
        return None, (
            jsonify({"error": "Playback request is no longer active"}),
            409,
        )
    return session, None

def get_pipeline():
    global pipeline
    if pipeline is None:
        with pipeline_lock:
            if pipeline is None:
                print("[Sidecar] Initializing Kokoro Pipeline...")
                try:
                    config_path = os.path.join(MODEL_DIR, "config.json")
                    model_path = os.path.join(MODEL_DIR, "kokoro-v1_0.pth")
                    if os.path.isfile(config_path) and os.path.isfile(model_path):
                        print("[Sidecar] Loading bundled model weights.")
                        repo_id = "hexgrad/Kokoro-82M"
                        pipeline = create_offline_pipeline(
                            KModel,
                            KPipeline,
                            repo_id=repo_id,
                            config_path=config_path,
                            model_path=model_path,
                        )
                    else:
                        print("[Sidecar] Bundled weights not found; downloading from Hugging Face.")
                        pipeline = KPipeline(lang_code='a')
                    print("[Sidecar] Pipeline initialized successfully.")
                except Exception as e:
                    print(f"[Sidecar] CRITICAL: Failed to initialize Pipeline: {e}")
                    raise e
    return pipeline


def warm_pipeline():
    """Load weights and run one tiny inference before the server reports healthy."""
    import time

    started_at = time.perf_counter()
    warmed_pipeline = get_pipeline()
    bundled_voice = os.path.join(MODEL_DIR, "voices", "am_fenrir.pt")
    voice_source = bundled_voice if os.path.isfile(bundled_voice) else "am_fenrir"
    next(warmed_pipeline("Ready.", voice=voice_source, speed=1.0))
    elapsed_ms = round((time.perf_counter() - started_at) * 1000)
    print(f"[Sidecar] Pipeline prewarmed in {elapsed_ms}ms.")


def warm_speed_processor():
    """Fail startup early if the packaged real-time DSP cannot load or process."""
    with SonicSpeedProcessor(initial_speed=1.0) as processor:
        processor.process(np.zeros((480, 1), dtype=np.float32))
        processor.flush()
    print("[Sidecar] Sonic speed DSP ready.")

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

@app.route("/tts", methods=["POST"])
def tts():
    data = request.json or {}
    text = data.get("text", "")
    synthesis_segments = normalize_synthesis_segments(data.get("segments"), text)
    request_id = str(data.get("request_id") or uuid.uuid4()).strip()
    speed = float(data.get("speed", 1.0))
    voice = data.get("voice", "am_fenrir")
    bundled_voice = os.path.join(MODEL_DIR, "voices", f"{voice}.pt")
    voice_source = bundled_voice if os.path.isfile(bundled_voice) else voice
    volume = float(data.get("volume", 1.0))
    
    if not synthesis_segments:
        return jsonify({"error": "No text provided"}), 400

    # Each worker captures this token. Starting another request sets only the old
    # token, so clearing state for the new session can never revive old workers.
    session = session_controller.begin(request_id, initial_speed=speed)
    request_cancel_event = session.cancel_event
    sd.stop()
    emit_tts_event(
        "request_received",
        request_id,
        textLength=sum(len(segment["spoken_text"]) for segment in synthesis_segments),
        segmentCount=len(synthesis_segments),
        voice=voice,
        speed=speed,
    )

    try:
        p = get_pipeline()
    except Exception as e:
        emit_tts_event("error", request_id, message=str(e), stage="engine_initialization")
        session_controller.clear(session)
        return jsonify({"error": "TTS engine failed to initialize", "request_id": request_id}), 500
    emit_tts_event("engine_ready", request_id)
        
    meta = f"V:{voice}, S:{speed}, Vol:{volume}"
    if not getattr(sys, 'frozen', False):
        # Dev mode: include a snippet of the text for easier debugging in the live console.
        # This is intentionally NOT printed in release builds so clipboard content
        # never appears in log files on user machines.
        print(f"[Sidecar] Synthesizing: '{text[:20]}...' ({meta})")
    else:
        print(f"[Sidecar] Synthesizing ({meta}, chars:{len(text)})")
    
    import queue
    audio_queue = queue.Queue(maxsize=10)
    request_failed_event = threading.Event()

    def put_audio_queue(item):
        """Apply backpressure without trapping a cancelled generator thread."""
        while not request_cancel_event.is_set():
            try:
                audio_queue.put(item, timeout=0.1)
                return True
            except queue.Full:
                continue
        return False

    def generator_worker():
        """ Thread that generates audio tensors as fast as possible. """
        try:
            emit_tts_event("inference_started", request_id)
            chunk_index = 0
            for segment in synthesis_segments:
                if request_cancel_event.is_set():
                    break
                # The PyTorch pipeline is shared. Serialize model calls so a
                # replacement request cannot execute concurrently with the old
                # request while its cancellation reaches a yield boundary.
                with inference_lock:
                    if request_cancel_event.is_set():
                        break
                    generator = p(
                        segment["spoken_text"],
                        voice=voice_source,
                        # Runtime speed is handled by the streaming Sonic DSP so
                        # it can change inside already-generated speech.
                        speed=1.0,
                    )
                    for gs, ps, audio in generator:
                        if request_cancel_event.is_set():
                            break

                        # The planner bounds segments below Kokoro's token limit, so a
                        # planned segment normally produces one engine chunk.
                        queued = put_audio_queue(AudioChunk(
                            index=chunk_index,
                            audio=audio,
                            pause_after_ms=segment["pause_after_ms"],
                            segment_id=segment["id"],
                        ))
                        if not queued:
                            break
                        print(f"[Sidecar] Generated chunk {chunk_index} (queued)")
                        emit_tts_event(
                            "chunk_ready",
                            request_id,
                            chunkIndex=chunk_index,
                            segmentId=segment["id"],
                            segmentKind=segment["kind"],
                            pauseAfterMs=segment["pause_after_ms"],
                            sampleCount=int(audio.shape[-1]) if hasattr(audio, "shape") else len(audio),
                        )
                        chunk_index += 1
                if request_cancel_event.is_set():
                    break
            
            # Signal end of generation
            put_audio_queue(None)
        except Exception as e:
            print(f"[Sidecar] Inference error: {e}")
            request_failed_event.set()
            emit_tts_event("error", request_id, message=str(e), stage="inference")
            import traceback
            traceback.print_exc()
            put_audio_queue(None)

    def playback_worker():
        """ Thread that consumes from the queue and plays audio. """
        print("[STATUS] START")

        def emit_control_acknowledgement(event, position):
            emit_tts_event(
                event,
                request_id,
                chunkIndex=position.chunk_index,
                sampleOffset=position.sample_offset,
            )

        def prepare_audio(chunk):
            audio = chunk.audio
            if hasattr(audio, "cpu"):
                played_audio = (audio * volume).cpu().numpy().astype(np.float32)
            else:
                played_audio = (np.asarray(audio) * volume).astype(np.float32)

            if len(played_audio.shape) == 1:
                played_audio = played_audio.reshape(-1, 1)

            pause_sample_count = int(24000 * chunk.pause_after_ms / 1000)
            if pause_sample_count:
                played_audio = np.concatenate([
                    played_audio,
                    np.zeros((pause_sample_count, 1), dtype=np.float32),
                ], axis=0)

            max_val = float(np.max(np.abs(played_audio)))
            rms = float(np.sqrt(np.mean(played_audio**2)))
            print(f"[Sidecar] Chunk {chunk.index} | Max: {max_val:.4f} | RMS: {rms:.4f}")
            return played_audio

        def on_first_write(chunk):
            emit_tts_event(
                "playback_started",
                request_id,
                chunkIndex=chunk.index,
                segmentId=chunk.segment_id,
            )

        def process_speed_block(processor, audio):
            desired_speed, speed_version = session.speed_snapshot()
            processed = processor.process(audio, speed=desired_speed)
            if session.acknowledge_speed(speed_version):
                position = session.position()
                emit_tts_event(
                    "speed_changed",
                    request_id,
                    speed=desired_speed,
                    chunkIndex=position.chunk_index,
                    sampleOffset=position.sample_offset,
                )
            return processed
        
        try:
            # Open a persistent stream for the entire session
            # This fixes #9 by avoiding the startup/shutdown latency of sd.play()
            with (
                sd.OutputStream(samplerate=24000, channels=1, dtype='float32') as stream,
                SonicSpeedProcessor(initial_speed=speed) as speed_processor,
            ):
                play_queued_audio(
                    stream,
                    audio_queue,
                    session,
                    prepare_audio=prepare_audio,
                    # A 20ms source block becomes at most 40ms at 0.5x, keeping
                    # pause and speed-command response comfortably sub-100ms.
                    block_size=960,
                    on_first_write=on_first_write,
                    on_paused=lambda position: emit_control_acknowledgement("paused", position),
                    on_resumed=lambda position: emit_control_acknowledgement("resumed", position),
                    process_audio_block=lambda audio: process_speed_block(speed_processor, audio),
                    flush_audio=speed_processor.flush,
                    source_block_size=480,
                )
        except Exception as e:
            print(f"[Sidecar] Playback stream error: {e}")
            request_failed_event.set()
            emit_tts_event("error", request_id, message=str(e), stage="playback")
            
        print("[STATUS] FINISHED")
        if (
            not request_failed_event.is_set()
            and session_controller.is_active(session)
        ):
            emit_tts_event("playback_finished", request_id)
        session_controller.clear(session)

    # Start both workers
    threading.Thread(target=generator_worker, daemon=True).start()
    threading.Thread(target=playback_worker, daemon=True).start()
    
    return jsonify({"status": "ok", "request_id": request_id})

@app.route("/stop", methods=["POST"])
def stop():
    data = request.get_json(silent=True) or {}
    session, error_response = validate_control_request(data)
    if error_response:
        return error_response
    print("[Sidecar] Stopping playback")
    if session is not None:
        session.cancel()
    sd.stop()
    if session is not None:
        emit_tts_event("cancelled", session.request_id)
        session_controller.clear(session)
    return jsonify({"status": "stopped"})

@app.route("/pause", methods=["POST"])
def pause():
    data = request.get_json(silent=True) or {}
    session, error_response = validate_control_request(data)
    if error_response:
        return error_response
    print("[Sidecar] Pausing playback")
    if session is not None:
        session.pause()
    return jsonify({"status": "pause_requested"})

@app.route("/resume", methods=["POST"])
def resume():
    data = request.get_json(silent=True) or {}
    session, error_response = validate_control_request(data)
    if error_response:
        return error_response
    print("[Sidecar] Resuming playback")
    if session is not None:
        session.resume()
    return jsonify({"status": "resume_requested"})

@app.route("/speed", methods=["POST"])
def set_speed():
    data = request.get_json(silent=True) or {}
    session, error_response = validate_control_request(data)
    if error_response:
        return error_response
    if session is None:
        return jsonify({"error": "There is no active playback request"}), 409
    try:
        speed = float(data.get("speed"))
        version = session.set_speed(speed)
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
    print(f"[Sidecar] Playback speed requested: {speed:.1f}x")
    return jsonify({"status": "speed_requested", "speed": speed, "version": version})

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
    import multiprocessing
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    
    cleanup_zombies()

    # Health means ready to synthesize, not merely that Flask has bound a port.
    # This moves cold model/JIT cost into the existing splash startup phase.
    warm_pipeline()
    warm_speed_processor()

    print(f"[Sidecar] Starting Kokoro TTS server on port {args.port}")
    # Use threaded=True to ensure one hanging request doesn't block the whole server
    app.run(host="127.0.0.1", port=args.port, threaded=True)
