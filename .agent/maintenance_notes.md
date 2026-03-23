# Kokoro TTS Development & Maintenance Notes

This document captures critical lessons learned during the stabilization of the Kokoro Clipboard TTS application, specifically regarding Windows development and audio sidecar management.

## 1. Zombie Process Management (Windows)

### The Problem
During development (`npm run tauri dev`), stopping the application via `Ctrl+C` in the terminal hard-kills the Rust process. This prevents Tauri's cleanup hooks and Rust's `Drop` implementations from running. Consequently, the Python sidecar remains alive as an orphaned "zombie" process.
- These zombies hold locks on the network port (e.g., 8790).
- They maintain an active handle to the audio hardware, preventing new instances from playing sound.

### The Solution: "Zombie Slayer" Architecture
A multi-layered approach is required for stability:
1. **Aggressive Port Clearing (Rust)**: In `sidecar.rs`, before spawning the sidecar, run a PowerShell command to forcefully terminate any process currently listening on the target port.
   ```powershell
   Get-NetTCPConnection -LocalPort 8790 ... | Stop-Process -Force
   ```
2. **PID Self-Cleanup (Python)**: The sidecar writes its PID to `kokoro.pid`. On startup, it checks this file and kills its predecessor.
3. **Avoid Brittle Watchdogs**: Don't rely on third-party libraries like `psutil` for basic watchdog functionality unless they are guaranteed to be in the environment, as they can cause silent crashes on startup.

## 2. Audio Pipeline Stability

### Data Types
`sounddevice` is sensitive to data types.
- Always use `np.float32` for audio data.
- **Tensors vs NumPy**: `kokoro` yields PyTorch Tensors. These MUST be converted via `.cpu().numpy()` before any NumPy operations (like `.astype()`) or `sounddevice.play()` calls.

### Volume Scaling
Apply volume scaling *after* converting to NumPy/float32 to avoid potential clipping or precision issues within the Tensor domain.

## 3. UI & Window Management

### Transparent Window Dragging
Standard HTML `data-tauri-drag-region` is often unreliable on Windows when using transparent windows.
- **Recommendation**: Use the JavaScript `startDragging()` API on a `onMouseDown` handler for the designated handle area.
- Add `e.stopPropagation()` to all interactive components within the drag region to prevent accidental window movement.

### Window Sizing
Tauri window dimensions define the *outer* bounds. To achieve a tight "pill" aesthetic, set the window size (e.g., 240x64) to tightly match the CSS-styled component dimensions to eliminate invisible dead space that blocks other desktop interactions.

## 4. Tauri v2 Traits
When using `AppHandle` to emit events or manage windows, ensure the following traits are in scope:
- `tauri::Emitter` (for `.emit()`)
- `tauri::Manager` (for `.get_webview_window()`, etc.)
- Use `app_handle.clone()` to pass owned handles into async blocks.
