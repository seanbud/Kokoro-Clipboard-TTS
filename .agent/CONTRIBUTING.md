# Contributing to Kokoro Clipboard TTS

This is the human-facing path from a GitHub issue to a tested, signed release.
Agents should additionally follow `.codex/skills/kokoro-issue-to-release/SKILL.md`.

## Development setup

Prerequisites: Node.js 20+, stable Rust, Python 3.10+, and on macOS
`brew install portaudio libsndfile`.

```bash
npm ci
python3 -m venv .sidecar-venv
source .sidecar-venv/bin/activate       # Windows: .sidecar-venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python scripts/build_local_sidecar.py
npm run tauri dev
```

## Issue-to-PR workflow

1. Read the whole issue and write observable acceptance criteria.
2. Start from updated `main` on a `codex/<issue>-<slug>` branch.
3. Reproduce and diagnose before editing. Add a regression test when possible.
4. Keep OS-specific changes scoped to that OS and manually inspect the affected
   window/audio behavior. Record unavailable platform testing honestly.
5. Run the local CI-equivalent gate:

```bash
python3 .codex/skills/kokoro-issue-to-release/scripts/verify.py
```

6. Open a draft PR with `Fixes #<issue>`, root cause, test evidence, manual test
   evidence, and residual risk. All Windows x64, macOS Apple Silicon, and macOS
   Intel CI jobs must pass before merge.

## Release workflow

Use a separate release PR after functional work is merged.

1. Update `package.json`, both root package versions in `package-lock.json`,
   `src-tauri/Cargo.toml`, the app package in `src-tauri/Cargo.lock`,
   `src-tauri/tauri.conf.json`, and `CHANGELOG.md`.
2. Run both local gates (replace `X.Y.Z`):

```bash
python3 .codex/skills/kokoro-issue-to-release/scripts/release_gate.py X.Y.Z
python3 .codex/skills/kokoro-issue-to-release/scripts/verify.py
```

3. Merge the passing release PR, update local `main`, and push an annotated
   `vX.Y.Z` tag. The tag triggers `.github/workflows/release.yml`; do not create a
   second manual release.
4. After the workflow succeeds, verify the public installers and signed updater:

```bash
python3 .codex/skills/kokoro-issue-to-release/scripts/release_gate.py X.Y.Z --published
```

5. For packaging, audio, or updater changes, complete the applicable frozen
   sidecar/install/update smoke tests in `RELEASE_TESTING.md` before announcing.

The release workflow downloads the pinned Kokoro model, builds the native Sonic
DSP and standalone Python sidecar, packages Windows and both macOS architectures,
publishes installers plus `latest.json`, and verifies all updater signatures.
