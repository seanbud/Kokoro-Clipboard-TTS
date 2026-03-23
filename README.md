# 🎙️ Kokoro Clipboard TTS

<div align="center">

A lightweight, cross-platform desktop app that reads your clipboard aloud using **Kokoro-82M** — a blazing-fast, local AI text-to-speech model.

**Windows 10/11** · **macOS (Universal)**

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| **Global Hotkey** | Select text anywhere → press `Win+Shift+Q` (or `Cmd+Shift+Q`) → hear it read aloud |
| **Floating Reader** | A minimal, always-on-top widget appears near your cursor with Play/Pause, Stop, and Speed controls |
| **Speed Control** | Click or scroll-wheel to cycle: 0.5× → 0.75× → 1× → 1.25× → 1.5× → 1.75× → 2× |
| **28 Voice Presets** | Choose from Kokoro's full voice library (default: Fenrir) |
| **System Tray** | Runs headless — lives in your tray/menu bar, never clutters your taskbar |
| **Auto-Updater** | Silently checks for updates on launch and offers one-click install |
| **100% Local** | No cloud APIs. No data leaves your machine. Zero latency. |

---

## 📦 Installation

### Download a Release

1. Go to the [Releases](https://github.com/seanbud/Kokoro-Clipboard-TTS/releases) page.
2. Download the installer for your platform:
   - **Windows**: `.msi` or `.exe` (NSIS) installer
   - **macOS**: `.dmg` (Universal binary — Apple Silicon + Intel)
3. Run the installer. The app will appear in your system tray.

---

## 🛠 Development Setup

### Prerequisites

- **Node.js** 20+ and **npm**
- **Rust** (stable toolchain) — install via [rustup](https://rustup.rs)
- **Tauri v2 CLI**: comes bundled via `npm run tauri`
- **Platform SDKs**: 
  - Windows: Visual Studio Build Tools with C++ workload
  - macOS: Xcode Command Line Tools

### Clone & Install

```bash
git clone https://github.com/seanbud/Kokoro-Clipboard-TTS.git
cd Kokoro-Clipboard-TTS
npm install
```

### Run in Development

```bash
npm run tauri dev
```

The app will launch with hot-reload for the frontend and automatic Rust recompilation.

> **Note:** TTS won't work until you build and place the Kokoro sidecar binary (see below).

### Run Tests

```bash
# Frontend tests (vitest)
npx vitest run

# Rust tests
cd src-tauri && cargo test
```

---

## 🐍 Building the Kokoro Sidecar

The TTS engine is a Python application bundled as a standalone executable via **PyInstaller**.

### 1 — Set up the Python environment

```bash
# Create a virtual environment
python -m venv kokoro-env
source kokoro-env/bin/activate  # or kokoro-env\Scripts\activate on Windows

# Install dependencies
pip install kokoro sounddevice flask pyinstaller
```

### 2 — Create the server script

The sidecar is a simple Flask HTTP server. Create `kokoro_server.py`:

```python
from flask import Flask, request, jsonify
import kokoro
import sounddevice as sd
import threading

app = Flask(__name__)
stop_event = threading.Event()

@app.route("/tts", methods=["POST"])
def tts():
    data = request.json
    text = data.get("text", "")
    speed = data.get("speed", 1.0)
    voice = data.get("voice", "am_fenrir")
    
    stop_event.clear()
    # Generate and play audio with kokoro
    # (Adapt to the actual kokoro API)
    
    return jsonify({"status": "ok"})

@app.route("/stop", methods=["POST"])
def stop():
    stop_event.set()
    sd.stop()
    return jsonify({"status": "stopped"})

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port)
```

### 3 — Bundle with PyInstaller

```bash
pyinstaller --onefile --name kokoro kokoro_server.py
```

### 4 — Place the binary

Copy the output to the Tauri sidecar location:

```bash
# Windows
copy dist\kokoro.exe src-tauri\binaries\kokoro-x86_64-pc-windows-msvc.exe

# macOS (Universal needs both)
cp dist/kokoro src-tauri/binaries/kokoro-x86_64-apple-darwin
cp dist/kokoro src-tauri/binaries/kokoro-aarch64-apple-darwin
```

> The file naming convention with target triples is required by Tauri's `externalBin` resolver.

---

## 🏗 Architecture

```
┌──────────────────────────────────────────────────┐
│                    Tauri Shell                    │
│                                                  │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐ │
│  │  Reader   │  │  Settings  │  │   Tutorial   │ │
│  │  Window   │  │  Window    │  │   Window     │ │
│  │(frameless)│  │            │  │              │ │
│  └─────┬─────┘  └─────┬──────┘  └──────┬───────┘ │
│        │               │               │         │
│  ┌─────┴───────────────┴───────────────┴──────┐  │
│  │             React Frontend                  │  │
│  │   App.tsx → routes by window.label          │  │
│  └──────────────────┬──────────────────────────┘  │
│                     │  invoke()                   │
│  ┌──────────────────┴──────────────────────────┐  │
│  │             Rust Backend (lib.rs)           │  │
│  │  • Sidecar Manager (spawn/kill)             │  │
│  │  • System Tray                              │  │
│  │  • Global Shortcut registration             │  │
│  │  • TTS HTTP commands (reqwest)              │  │
│  └──────────────────┬──────────────────────────┘  │
│                     │  HTTP :8787                  │
│  ┌──────────────────┴──────────────────────────┐  │
│  │        Kokoro TTS Sidecar (Python)          │  │
│  │  PyInstaller exe · Flask server · Kokoro-82M│  │
│  └─────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
Kokoro-Clipboard-TTS/
├── .github/workflows/release.yml   # CI/CD pipeline
├── src/
│   ├── App.tsx                      # Window-label router
│   ├── index.css                    # Tailwind + glassmorphism
│   ├── components/
│   │   ├── FloatingWidget.tsx       # Reader pill UI
│   │   ├── SettingsWindow.tsx       # Voice & shortcut config
│   │   └── Tutorial.tsx             # First-run guide
│   └── utils/
│       ├── textCleaner.ts           # Markdown stripper for TTS
│       └── textCleaner.test.ts      # Vitest suite
├── src-tauri/
│   ├── tauri.conf.json              # Tauri config
│   ├── Cargo.toml                   # Rust dependencies
│   ├── src/
│   │   ├── main.rs                  # Entry point
│   │   ├── lib.rs                   # Core app logic
│   │   └── sidecar.rs               # Process manager + tests
│   ├── binaries/                    # Place kokoro sidecar here
│   └── icons/                       # App icons
└── package.json
```

---

## 📄 License

MIT © 2026
