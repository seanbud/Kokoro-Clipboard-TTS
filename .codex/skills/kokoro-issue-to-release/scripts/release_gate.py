#!/usr/bin/env python3
"""Validate synchronized versions and optionally the published updater release."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
REPO = "seanbud/Kokoro-Clipboard-TTS"


def fail(message: str) -> None:
    raise SystemExit(f"Release gate failed: {message}")


def cargo_toml_version(path: Path) -> str:
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', path.read_text())
    if not match:
        fail(f"could not read version from {path.relative_to(ROOT)}")
    return match.group(1)


def cargo_lock_version(path: Path) -> str:
    text = path.read_text()
    match = re.search(
        r'\[\[package\]\]\s*\nname = "kokoro-clipboard-tts"\s*\nversion = "([^"]+)"',
        text,
    )
    if not match:
        fail("could not read app version from src-tauri/Cargo.lock")
    return match.group(1)


def local_gate(version: str) -> None:
    package = json.loads((ROOT / "package.json").read_text())
    lock = json.loads((ROOT / "package-lock.json").read_text())
    tauri = json.loads((ROOT / "src-tauri/tauri.conf.json").read_text())
    actual = {
        "package.json": package["version"],
        "package-lock.json": lock["version"],
        'package-lock.json packages[""]': lock["packages"][""]["version"],
        "src-tauri/Cargo.toml": cargo_toml_version(ROOT / "src-tauri/Cargo.toml"),
        "src-tauri/Cargo.lock": cargo_lock_version(ROOT / "src-tauri/Cargo.lock"),
        "src-tauri/tauri.conf.json": tauri["version"],
    }
    mismatches = [f"{name}={value}" for name, value in actual.items() if value != version]
    if mismatches:
        fail("version mismatch: " + ", ".join(mismatches))
    if tauri.get("bundle", {}).get("createUpdaterArtifacts") is not True:
        fail("Tauri signed updater artifacts are disabled")
    updater = tauri.get("plugins", {}).get("updater", {})
    if not updater.get("pubkey") or not updater.get("endpoints"):
        fail("Tauri updater public key or endpoint is missing")
    changelog = (ROOT / "CHANGELOG.md").read_text()
    if not re.search(rf"(?m)^## {re.escape(version)} — \d{{4}}-\d{{2}}-\d{{2}}$", changelog):
        fail(f"CHANGELOG.md has no dated {version} heading")
    print(f"Local release metadata is synchronized at {version}.")


def published_gate(version: str) -> None:
    tag = f"v{version}"
    result = subprocess.run(
        ["gh", "release", "view", tag, "--repo", REPO, "--json", "isDraft,tagName,url"],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        fail(result.stderr.strip() or f"GitHub release {tag} was not found")
    release = json.loads(result.stdout)
    if release["isDraft"] or release["tagName"] != tag:
        fail(f"{tag} is missing or still a draft")

    url = f"https://github.com/{REPO}/releases/download/{tag}/latest.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            latest = json.load(response)
    except Exception as exc:
        fail(f"could not fetch public latest.json: {exc}")
    if latest.get("version") != version:
        fail(f"latest.json reports {latest.get('version')!r}, expected {version!r}")
    required = {"darwin-aarch64", "darwin-x86_64", "windows-x86_64"}
    platforms = latest.get("platforms", {})
    for name in sorted(required):
        metadata = platforms.get(name, {})
        if not metadata.get("url") or not metadata.get("signature"):
            fail(f"latest.json lacks signed updater metadata for {name}")
    print(f"Published signed updater release verified: {release['url']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version", help="Release version without the v prefix")
    parser.add_argument("--published", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", args.version):
        fail("version must be semantic version text without a v prefix")
    local_gate(args.version)
    if args.published:
        published_gate(args.version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
