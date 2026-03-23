import os
import subprocess
import sys
import shutil

def run():
    print("--- Kokoro TTS Sidecar Local Build ---")
    
    # 1. Ensure directories exist
    os.makedirs("src-tauri/binaries", exist_ok=True)
    
    # 2. Setup virtual environment to avoid permission issues
    venv_dir = os.path.join(os.getcwd(), ".sidecar-venv")
    if not os.path.exists(venv_dir):
        print("Creating virtual environment to bypass permission errors...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        
    # Determine the python and pyinstaller executable paths in the venv
    if os.name == 'nt':
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        venv_pyinstaller = os.path.join(venv_dir, "Scripts", "pyinstaller.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")
        venv_pyinstaller = os.path.join(venv_dir, "bin", "pyinstaller")

    # 3. Install requirements
    print("Installing dependencies into the isolated virtual environment...")
    subprocess.check_call([venv_python, "-m", "pip", "install", "-U", "pip"])
    subprocess.check_call([venv_python, "-m", "pip", "install", "-r", "requirements.txt"])

    # 4. Build with PyInstaller
    print("Building sidecar executable...")
    # We use --onefile and --name kokoro
    # The output will be in dist/kokoro.exe
    try:
        subprocess.check_call([
            venv_pyinstaller, 
            "--onefile", 
            "--name", "kokoro",
            "--collect-all", "onnxruntime",
            "--collect-all", "kokoro",
            "--collect-all", "misaki",
            "--collect-all", "phonemizer",
            "--collect-all", "language_tags",
            "--collect-all", "espeakng_loader",
            "--collect-all", "huggingface_hub",
            "--collect-all", "sounddevice",
            "--collect-all", "soundfile",
            "sidecar/kokoro_server.py"
        ])
    except Exception as e:
        print(f"Error building with PyInstaller: {e}")
        return

    # 5. Move and rename for Tauri
    # Triple for Windows: x86_64-pc-windows-msvc
    triple = "x86_64-pc-windows-msvc"
    src = "dist/kokoro.exe"
    dst = f"src-tauri/binaries/kokoro-{triple}.exe"
    
    print(f"\nMoving {src} to {dst}...")
    if os.path.exists(dst):
        os.remove(dst)
        
    if os.path.exists(src):
        shutil.move(src, dst)
        print("SUCCESS! Sidecar built for local dev.")
        print("You can now run: npm run tauri dev")
    else:
        print(f"Error: Could not find build output at {src}")

if __name__ == "__main__":
    run()
