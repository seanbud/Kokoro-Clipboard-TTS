# Changelog

## 0.8.3 — 2026-07-30

### Changed

- Use a dedicated monochrome Shiba template icon in the macOS menu bar while retaining the full-color application icon.

### Fixed

- Remove the thin native-window frame around the floating widget on Windows while preserving the pill shadow and macOS window appearance.

## 0.8.2 — 2026-07-28

### Fixed

- Restore the floating widget's visible close button after the Replay control widened the toolbar.
- Keep Control+Option+R as the explicit first-run and Reset default on macOS.
- Add a layout regression test that budgets enough native-window width for every widget control and its shadow padding.

## 0.8.1 — 2026-07-28

### Fixed

- Generate and sign the platform-specific updater bundles required by Tauri's in-app updater.
- Fail the release workflow if updater signatures or any macOS/Windows entry in `latest.json` are missing.

### Verification release

This patch is intentionally small so an installed v0.8.0 build can verify the full signed download, install, and restart path before updater support is considered production-ready.

## 0.8.0 — 2026-07-27

### Highlights

- Replay the sentence currently being heard, then continue forward; use Option+Left on macOS or Alt+Left on Windows.
- Preview the selected voice and volume directly in Settings.
- Read common chat shorthand, technical initialisms, dates, times, money, percentages, versions, links, email addresses, paths, and inline code more deliberately.
- Preserve a useful pause when a copied line break separates complete thoughts.
- Keep Kokoro inference deterministic by explicitly running the model in evaluation mode.
- Show the app version, cold-start milestones, and better first-audio wait feedback.
- Restore customized global shortcuts correctly after an app restart.
- Bootstrap signed in-app updates with download, install, and restart progress.

### Packaging decision

The default remains the compact, fully offline Kokoro package (approximately 500 MB on Apple Silicon). A pre-extracted runtime approached 1 GB installed and was rejected despite faster repeat launches. Unused ONNX and test modules were removed without changing the model or speech quality.

### Update note

v0.7.1 cannot authenticate an in-app update because it predates the signed release channel. Install v0.8.0 manually from GitHub Releases once; v0.8.1 will be the first end-to-end updater verification release.
