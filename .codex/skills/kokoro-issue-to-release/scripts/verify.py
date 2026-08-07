#!/usr/bin/env python3
"""Run the local Kokoro Clipboard TTS pull-request verification gate."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]


def run(*command: str, cwd: Path = ROOT) -> None:
    print(f"\n+ {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def python_with_numpy() -> str:
    candidates = [
        ROOT / ".sidecar-venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"),
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.exists():
            result = subprocess.run(
                [str(candidate), "-c", "import numpy"],
                cwd=ROOT,
                capture_output=True,
            )
            if result.returncode == 0:
                return str(candidate)
    raise SystemExit(
        "No project Python with numpy found. Activate/install requirements in "
        ".sidecar-venv, then rerun this gate."
    )


def ensure_test_sidecar() -> None:
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        target = "aarch64-apple-darwin" if machine in {"arm64", "aarch64"} else "x86_64-apple-darwin"
        path = ROOT / "src-tauri" / "binaries" / f"kokoro-{target}"
    elif os.name == "nt":
        path = ROOT / "src-tauri" / "binaries" / "kokoro-x86_64-pc-windows-msvc.exe"
    else:
        path = ROOT / "src-tauri" / "binaries" / "kokoro-x86_64-unknown-linux-gnu"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        print(f"Created ignored Rust-test sidecar placeholder: {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip native DSP build and production frontend build during iteration.",
    )
    args = parser.parse_args()

    py = python_with_numpy()
    if not args.quick:
        run(py, "scripts/build_sonic_dsp.py")
    run(py, "-m", "unittest", "discover", "-s", "sidecar", "-p", "test_*.py")
    run(py, "-m", "unittest", "discover", "-s", "scripts", "-p", "test_*.py")

    if not (ROOT / "node_modules").exists():
        run("npm", "ci")
    run("npm", "test", "--", "--run")
    if not args.quick:
        run("npm", "run", "build")

    ensure_test_sidecar()
    run("cargo", "fmt", "--check", cwd=ROOT / "src-tauri")
    run("cargo", "test", cwd=ROOT / "src-tauri")
    run("git", "diff", "--check")
    print("\nVerification gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
