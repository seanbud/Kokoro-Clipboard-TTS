# Kokoro Clipboard TTS

<div align="center">
  <img src="public/icon.png" width="128" alt="Kokoro Clipboard TTS Logo">
</div>

<div align="center">

**A locally run, open-source** TTS desktop app.

Reads your clipboard aloud with [**Kokoro-82M**](https://github.com/hexgrad/kokoro) AI text-to-speech.
</div>
</br>

---

## 🛡️ Privacy
  Your data never leaves your PC.
  
  No cloud. No API keys. No telemetry. 
  
  Just fast, private, offline TTS.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Global Hotkey** | Select text anywhere → press `Win+Shift+Q` on Windows or `Control+Option+R` on macOS → hear it read aloud |
| **Floating Reader** | A minimal, always-on-top widget appears near your cursor with Play/Pause, Stop, and Speed controls |
| **Speed Control** | Click or scroll-wheel to cycle: 0.5× → 0.75× → 1× → 1.25× → 1.5× → 1.75× → 2× |
| **28 Voice Presets** | Choose from Kokoro's full voice library (default: Fenrir) |
| **System Tray** | Runs headless — choose **Read Clipboard** from the tray/menu-bar menu as an alternative to the hotkey |
| **Auto-Updater** | Silently checks for updates on launch and offers one-click install |
| **100% Local** | No cloud APIs. No data leaves your machine. Zero latency. |

---

## 📦 Installation

**Kokoro Clipboard TTS is designed for zero-config easy installation.**

1. Go to the [Releases](https://github.com/seanbud/Kokoro-Clipboard-TTS/releases) page.
2. Download the installer for your platform:
   - **Windows**: `.msi` or `.exe` installer
   - **macOS**: `.dmg` for Apple Silicon (`aarch64`) or Intel (`x64`)
3. Run the installer. **That's it!** The AI engine and model weights are bundled inside.

---

## 🛠 Development & Contributing

Want to build from source, modify the Python AI sidecar, or understand the automated CI/CD pipeline? 

Please check out our **[Contributing Guide](.agent/CONTRIBUTING.md)** for full development setup instructions.

---

## 🏗 Architecture

<div align="center">
  <img src="public/architecture.png" alt="Kokoro Clipboard TTS Architecture Diagram">
</div>

*The React frontend communicates via Tauri with the Rust backend, which securely manages a headless local Python server running the Kokoro TTS engine.*

The Python sidecar is packaged as a standalone executable during release builds, so users do not need to install Python or set up the AI stack manually. It bundles the Kokoro runtime and its supporting libraries, including `torch`, `onnxruntime`, `phonemizer`, `espeak-ng` data, and the model weights/voices used for offline synthesis. That keeps the app fully local while still shipping the native ML dependencies needed to generate speech.

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
