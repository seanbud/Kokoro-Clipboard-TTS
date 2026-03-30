; NSIS hooks for Kokoro Clipboard TTS installer
; This script runs before the installer copies new files, ensuring
; the main app and its sidecar process are fully terminated first.
; Without this, the installer fails with "file in use" errors because
; the kokoro.exe sidecar keeps running even after the main app exits.

!macro NSIS_HOOK_PREINSTALL
    DetailPrint "Preparing for update: Closing running Kokoro TTS instances..."

    ; 1. Surgical Port Targeting (100% Safe):
    ; Kills ANY process holding the sidecar port (8790). 
    ; The installer never uses this port, so this will only hit the sidecar.
    nsExec::ExecToLog 'powershell -Command "Get-NetTCPConnection -LocalPort 8790 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"'

    ; 2. Exact Image Matching (Safe):
    ; Uses exact names to ensure the installer (...-setup.exe) is never targeted.
    nsExec::ExecToLog 'taskkill /F /IM "kokoro-clipboard-tts.exe" /T'
    nsExec::ExecToLog 'taskkill /F /IM "kokoro.exe" /T'

    ; 3. Handle the Tauri 2 specific sidecar naming:
    nsExec::ExecToLog 'taskkill /F /IM "kokoro-x86_64-pc-windows-msvc.exe" /T'

    ; Pause to ensure file handles are fully released by the OS
    Sleep 2000
!macroend
