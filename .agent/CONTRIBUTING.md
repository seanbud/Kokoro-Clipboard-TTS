# Contributing to Kokoro-Clipboard-TTS

Thank you for your interest in contributing! This document contains the necessary information for setting up your development environment, understanding the CI/CD pipeline, and building the standalone Kokoro TTS sidecar if you are working on the AI engine.

## 🛠 Development Setup

### Prerequisites

- **Node.js** 20+ and **npm**
- **Rust** (stable, 1.88.0+ recommended)
- **Python 3.10+** (for sidecar development)
- **macOS only**: `brew install portaudio libsndfile`

### Clone & Install

```bash
git clone https://github.com/seanbud/Kokoro-Clipboard-TTS.git
cd Kokoro-Clipboard-TTS
npm install
```

### Run in Development

```bash
# 1. Build the sidecar once for your platform
# This script automatically detects your OS/Architecture and builds the sidecar into src-tauri/binaries/
python3 scripts/build_local_sidecar.py

# 2. Run Tauri dev
npm run tauri dev
```

---

## 🐍 CI/CD Automation

The GitHub Actions workflow (`release.yml`) automatically:
1. Sets up a Python environment.
2. Downloads the **Kokoro-82M** ONNX model and voice weights.
3. Bundles them into a standalone sidecar binary using **PyInstaller**.
4. Packages everything into the final Tauri installer.

---

If you are developing the sidecar script (`sidecar/kokoro_server.py`), you can use the provided build script which handles all collectors and renaming:

```bash
python3 scripts/build_local_sidecar.py
```
> The file naming convention with target triples is required by Tauri's `externalBin` resolver (e.g., `kokoro-x86_64-pc-windows-msvc.exe`).
