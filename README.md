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

## 📦 Installation

**Kokoro Clipboard TTS is designed for zero-config easy installation.**

1. Go to the [Releases](https://github.com/seanbud/Kokoro-Clipboard-TTS/releases) page.
2. Download the installer for your platform:
   - **Windows**: `.msi` or `.jsis` installer
   - **macOS**: `.dmg` (Universal binary)
3. Run the installer. **That's it!** The AI engine and model weights are bundled inside.

---

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
