# Release Testing Process

To ensure the standalone Text-to-Speech (TTS) engine works correctly on other Windows machines before you cut a release, follow this process to test the "frozen" executable locally.

---

## Step 0: Activate the Virtual Environment
A virtual environment ensures you use the project-specific versions of Python libraries instead of your global system ones. In your project, this is the `.sidecar-venv` folder.

**In PowerShell (Standard Windows Terminal):**
```powershell
. \.sidecar-venv\Scripts\Activate.ps1
```

**In Command Prompt (CMD):**
```cmd
.sidecar-venv\Scripts\activate.bat
```

**In Git Bash:**
```bash
source .sidecar-venv/Scripts/activate
```
*You will know it's working when you see `(.sidecar-venv)` appear at the start of your terminal prompt.*

---

## Step 1: Ensure Local Dependencies are Synced
Always ensure your `requirements.txt` precisely matches what your local virtual environment needs to run the app. If you install a new package or fix a version, update `requirements.txt` immediately.

---

## Step 2: Download Necessary Models Locally (Simulating CI)
The CI downloads the model to `sidecar/model` before freezing it. You need to do this locally as well before running PyInstaller:

**In PowerShell:**
```powershell
New-Item -ItemType Directory -Force -Path sidecar\model
Invoke-WebRequest -Uri "https://github.com/hexgrad/kokoro/raw/main/kokoro-v0.19.onnx" -OutFile "sidecar\model\kokoro-v0.19.onnx"
Invoke-WebRequest -Uri "https://github.com/hexgrad/kokoro/raw/main/voices.json" -OutFile "sidecar\model\voices.json"
```

**In Git Bash:**
```bash
mkdir -p sidecar/model
curl -L -o sidecar/model/kokoro-v0.19.onnx https://github.com/hexgrad/kokoro/raw/main/kokoro-v0.19.onnx
curl -L -o sidecar/model/voices.json https://github.com/hexgrad/kokoro/raw/main/voices.json
```

---

## Step 3: PyInstaller Freeze (Simulating CI)
From your root repository (make sure your `.sidecar-venv` is activated):

**In PowerShell:**
```powershell
pyinstaller --onefile --name kokoro `
  --add-data "sidecar/model;model" `
  --collect-all onnxruntime `
  --collect-all kokoro `
  --collect-all misaki `
  --collect-all phonemizer-fork `
  --collect-all language_tags `
  --collect-all espeakng_loader `
  --collect-all huggingface_hub `
  --collect-all sounddevice `
  --collect-all soundfile `
  --collect-all torch `
  --collect-all loguru `
  --collect-all transformers `
  sidecar/kokoro_server.py
```

**In Git Bash:**
```bash
pyinstaller --onefile --name kokoro \
  --add-data "sidecar/model;model" \
  --collect-all onnxruntime \
  --collect-all kokoro \
  --collect-all misaki \
  --collect-all phonemizer-fork \
  --collect-all language_tags \
  --collect-all espeakng_loader \
  --collect-all huggingface_hub \
  --collect-all sounddevice \
  --collect-all soundfile \
  --collect-all torch \
  --collect-all loguru \
  --collect-all transformers \
  sidecar/kokoro_server.py
```

---

## Step 4: Run and Test the Standalone Sidecar
Run your newly built `.exe` from the `dist` folder:
```powershell
.\dist\kokoro.exe --port 8791
```

Send a test POST request to it from another terminal to ensure it loads everything without crashing:

**In PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8791/test_audio" -Method POST -Body "{}" -ContentType "application/json"
```

**In Git Bash:**
```bash
curl -X POST http://127.0.0.1:8791/test_audio -H "Content-Type: application/json" -d "{}"
```
If you hear the beep and see no errors in the console, your frozen sidecar is solid and safe to release!
