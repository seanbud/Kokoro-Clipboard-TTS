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
        # Prefer python3.10 if available on macOS
        python_exec = sys.executable
        if os.name != 'nt':
            p310 = shutil.which("python3.10")
            if p310:
                python_exec = p310
                print(f"Using {python_exec} for virtual environment...")
        subprocess.check_call([python_exec, "-m", "venv", venv_dir])
        
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
    print("Installing spaCy en_core_web_sm model...")
    # spaCy may delegate installation to uv. When the venv's Python is invoked
    # by absolute path (rather than through an activated shell), uv cannot infer
    # the active environment on macOS unless VIRTUAL_ENV and PATH are explicit.
    venv_env = os.environ.copy()
    venv_env["VIRTUAL_ENV"] = venv_dir
    venv_env["PATH"] = os.path.dirname(venv_python) + os.pathsep + venv_env.get("PATH", "")
    subprocess.check_call(
        [venv_python, "-m", "spacy", "download", "en_core_web_sm"],
        env=venv_env,
    )

    # 4. Build with PyInstaller
    print("Building sidecar executable...")
    # We use --onefile and --name kokoro
    # The output will be in dist/kokoro.exe
    pyinstaller_args = [
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
        "--collect-all", "torch",
        "--collect-all", "loguru",
        "--collect-all", "transformers",
        "--collect-all", "spacy",
        "--collect-all", "en_core_web_sm",
    ]
    if os.name != 'nt':
        # macOS validates code signatures when PyInstaller's onefile bootloader
        # extracts and loads the bundled Python framework. Sign all collected
        # binaries with the same ad-hoc identity so the bootloader and embedded
        # framework are allowed to load together after installation.
        pyinstaller_args.extend([
            "--codesign-identity", "-",
            "--osx-entitlements-file", os.path.join("src-tauri", "sidecar.entitlements.plist"),
        ])
    model_dir = os.path.join("sidecar", "model")
    if (
        os.path.isfile(os.path.join(model_dir, "config.json"))
        and os.path.isfile(os.path.join(model_dir, "kokoro-v1_0.pth"))
    ):
        print("Bundling local Kokoro model weights and voices...")
        pyinstaller_args.extend(["--add-data", f"{model_dir}{os.pathsep}model"])
    pyinstaller_args.append(os.path.join("sidecar", "kokoro_server.py"))

    try:
        subprocess.check_call(pyinstaller_args)
    except Exception as e:
        print(f"Error building with PyInstaller: {e}")
        return

    # 5. Move and rename for Tauri
    # Detect target triple for macOS/Windows
    if os.name == 'nt':
        triple = "x86_64-pc-windows-msvc"
        src = "dist/kokoro.exe"
        dst = f"src-tauri/binaries/kokoro-{triple}.exe"
    else:
        # For macOS, we need to detect architecture
        import platform
        arch = platform.machine()
        if arch == 'arm64':
            triple = "aarch64-apple-darwin"
        else:
            triple = "x86_64-apple-darwin"
        src = "dist/kokoro"
        dst = f"src-tauri/binaries/kokoro-{triple}"
    
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
