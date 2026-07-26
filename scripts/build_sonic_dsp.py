#!/usr/bin/env python3
"""Build the vendored Sonic speech-rate DSP as a small shared library."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "third_party" / "sonic"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "sidecar" / "native"


def library_filename(system: str | None = None) -> str:
    system = system or platform.system()
    if system == "Windows":
        return "sonic_kctts.dll"
    if system == "Darwin":
        return "libsonic_kctts.dylib"
    return "libsonic_kctts.so"


def build(output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / library_filename()
    sonic_c = SOURCE_DIR / "sonic.c"
    wrapper_c = SOURCE_DIR / "sonic_wrapper.c"

    if platform.system() == "Windows":
        compiler = shutil.which("cl")
        if compiler:
            command = [
                compiler,
                "/nologo",
                "/O2",
                "/LD",
                f"/I{SOURCE_DIR}",
                str(sonic_c),
                str(wrapper_c),
                "/link",
                f"/OUT:{output}",
            ]
        else:
            compiler = shutil.which("clang") or shutil.which("gcc")
            if not compiler:
                raise RuntimeError("No Windows C compiler found (cl, clang, or gcc)")
            command = [
                compiler,
                "-O3",
                "-shared",
                f"-I{SOURCE_DIR}",
                str(sonic_c),
                str(wrapper_c),
                "-o",
                str(output),
            ]
    else:
        compiler = shutil.which(os.environ.get("CC", "cc"))
        if not compiler:
            raise RuntimeError("No C compiler found")
        shared_flag = "-dynamiclib" if platform.system() == "Darwin" else "-shared"
        command = [
            compiler,
            "-O3",
            shared_flag,
            "-fPIC",
            f"-I{SOURCE_DIR}",
            str(sonic_c),
            str(wrapper_c),
            "-o",
            str(output),
        ]

    subprocess.check_call(command)
    if not output.is_file():
        raise RuntimeError(f"Compiler did not create {output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    try:
        output = build(args.output_dir.resolve())
    except Exception as error:
        print(f"Sonic DSP build failed: {error}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
