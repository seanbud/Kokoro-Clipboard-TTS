# Kokoro Clipboard TTS repository map

## Main layers

- `src/`: React UI, reader controls, text planning, startup/update presentation.
- `src-tauri/src/`: Tauri lifecycle, windows, tray, shortcuts, updater, sidecar bridge.
- `sidecar/`: local Kokoro generation, audio playback, live speed, protocol.
- `scripts/`: native DSP build and benchmark/analysis tools.
- `tests/fixtures/reader_quality_v1.json`: long-form speech-planning quality corpus.
- `.github/workflows/ci.yml`: Windows x64, macOS Apple Silicon, macOS Intel PR gate.
- `.github/workflows/release.yml`: tag-triggered offline model packaging, signed
  installers, GitHub release, `latest.json`, and updater signature verification.

## Version sources

All must match before tagging:

- `package.json`: `version`
- `package-lock.json`: top-level `version`
- `package-lock.json`: root package `packages[""].version`
- `src-tauri/Cargo.toml`: package `version`
- `src-tauri/Cargo.lock`: `kokoro-clipboard-tts` package `version`
- `src-tauri/tauri.conf.json`: `version`
- `CHANGELOG.md`: `## X.Y.Z — YYYY-MM-DD`

`src-tauri/tauri.conf.json` must retain `bundle.createUpdaterArtifacts: true` and
the updater public key/endpoints. A pushed `vX.Y.Z` tag is the only release trigger.

## Required evidence by change type

| Change | Automated evidence | Manual evidence |
|---|---|---|
| React/planning | Vitest regression + build | Relevant window/reader behavior |
| Tauri/window/tray | Rust test where possible + CI matrix | Changed OS plus unchanged peer OS |
| Sidecar/audio | Python regression + CI matrix | Playback, pause, speed, cancellation |
| Packaging/updater | Full CI + release gate | Clean install/update from prior release |
| Optional engine | Benchmarks, size/license audit | Opt-in UX, removal, offline behavior |

Use `RELEASE_TESTING.md` for the frozen-sidecar and release smoke procedures.
