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

## Step 2: Download the v1.0 Model (Simulating CI)
The CI downloads the official Kokoro v1.0 weights and voices to `sidecar/model` before freezing. Use the same pinned file set locally:

```powershell
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='hexgrad/Kokoro-82M', local_dir='sidecar/model', allow_patterns=['config.json', 'kokoro-v1_0.pth', 'voices/*.pt'])"
```

Verify that `sidecar/model/config.json`, `sidecar/model/kokoro-v1_0.pth`, and at least one file under `sidecar/model/voices/` exist.

---

## Step 3: PyInstaller Freeze (Simulating CI)
From your root repository (make sure your `.sidecar-venv` is activated):

Build the vendored Sonic real-time speed library first:

```powershell
python scripts/build_sonic_dsp.py
```

**In PowerShell:**
```powershell
pyinstaller --onefile --name kokoro `
  --add-data "sidecar/model;model" `
  --add-binary "sidecar/native/sonic_kctts.dll;native" `
  --collect-all onnxruntime `
  --collect-all kokoro `
  --collect-all misaki `
  --collect-all phonemizer `
  --collect-all language_tags `
  --collect-all espeakng_loader `
  --collect-all huggingface_hub `
  --collect-all sounddevice `
  --collect-all soundfile `
  --collect-all torch `
  --collect-all loguru `
  --collect-all transformers `
  --collect-all spacy `
  --collect-all en_core_web_sm `
  sidecar/kokoro_server.py
```

**In Git Bash:**
```bash
pyinstaller --onefile --name kokoro \
  --add-data "sidecar/model;model" \
  --add-binary "sidecar/native/sonic_kctts.dll;native" \
  --collect-all onnxruntime \
  --collect-all kokoro \
  --collect-all misaki \
  --collect-all phonemizer \
  --collect-all language_tags \
  --collect-all espeakng_loader \
  --collect-all huggingface_hub \
  --collect-all sounddevice \
  --collect-all soundfile \
  --collect-all torch \
  --collect-all loguru \
  --collect-all transformers \
  --collect-all spacy \
  --collect-all en_core_web_sm \
  sidecar/kokoro_server.py
```

---

## Step 4: Run and Test the Standalone Sidecar
Run your newly built `.exe` from the `dist` folder:
```powershell
.\dist\kokoro.exe --port 8791
```

Wait for the health endpoint before testing audio. Startup now prewarms both Kokoro and the Sonic speed processor:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8791/health"
```

Then send a test-audio request:

**In PowerShell:**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8791/test_audio" -Method POST -Body "{}" -ContentType "application/json"
```

**In Git Bash:**
```bash
curl -X POST http://127.0.0.1:8791/test_audio -H "Content-Type: application/json" -d "{}"
```
The beep is only a packaging smoke test. Before release, also run the Python, frontend, and Rust suites; synthesize the reader corpus; verify a mid-sentence speed change; and complete the manual/soak gates in `ROADMAP.md`.
