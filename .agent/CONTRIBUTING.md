# Contributing to Kokoro-Clipboard-TTS

Thank you for your interest in contributing! This document contains the necessary information for setting up your development environment, understanding the CI/CD pipeline, and building the standalone Kokoro TTS sidecar if you are working on the AI engine.

## 🛠 Development Setup

### Prerequisites

- **Node.js** 20+ and **npm**
- **Rust** (stable)
- **Python 3.10+** (for sidecar development)

### Clone & Install

```bash
git clone https://github.com/seanbud/Kokoro-Clipboard-TTS.git
cd Kokoro-Clipboard-TTS
npm install
```

### Run in Development

```bash
# 1. Build the sidecar once for your platform
# Windows
pyinstaller --onefile --name kokoro --add-data "sidecar/model;model" sidecar/kokoro_server.py
mv dist/kokoro.exe src-tauri/binaries/kokoro-x86_64-pc-windows-msvc.exe

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

## 🏗 Building the Kokoro Sidecar (Manual)

If you are developing the sidecar script (`sidecar/kokoro_server.py`), you can manually test building it via PyInstaller.

```bash
# Create a virtual environment
python -m venv kokoro-env
kokoro-env\Scripts\activate

# Install dependencies
pip install kokoro sounddevice flask pyinstaller

# Bundle with PyInstaller
pyinstaller --onefile --name kokoro --add-data "sidecar/model;model" sidecar/kokoro_server.py
```
> The file naming convention with target triples is required by Tauri's `externalBin` resolver (e.g., `kokoro-x86_64-pc-windows-msvc.exe`).
