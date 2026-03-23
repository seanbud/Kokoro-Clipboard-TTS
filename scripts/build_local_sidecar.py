import os
import subprocess
import sys
import shutil

def run():
    print("--- Kokoro TTS Sidecar Local Build ---")
    
    # 1. Ensure directories exist
    os.makedirs("src-tauri/binaries", exist_ok=True)
    
    # 2. Install requirements
    print("Installing Python dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 3. Build with PyInstaller
    print("Building sidecar executable...")
    # We use --onefile and --name kokoro
    # The output will be in dist/kokoro.exe
    try:
        subprocess.check_call([
            "pyinstaller", 
            "--onefile", 
            "--name", "kokoro",
            "--collect-all", "onnxruntime",
            "sidecar/main.py"
        ])
    except Exception as e:
        print(f"Error building with PyInstaller: {e}")
        return

    # 4. Move and rename for Tauri
    # Triple for Windows: x86_64-pc-windows-msvc
    triple = "x86_64-pc-windows-msvc"
    src = "dist/kokoro.exe"
    dst = f"src-tauri/binaries/kokoro-{triple}.exe"
    
    print(f"Moving {src} to {dst}...")
    if os.path.exists(dst):
        os.remove(dst)
    shutil.move(src, dst)
    
    print("\nSUCCESS! Sidecar built for local dev.")
    print("You can now run: npm run tauri dev")

if __name__ == "__main__":
    run()
