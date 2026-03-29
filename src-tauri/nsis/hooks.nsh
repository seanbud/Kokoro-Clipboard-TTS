; NSIS hooks for Kokoro Clipboard TTS installer
; This script runs before the installer copies new files, ensuring
; the main app and its sidecar process are fully terminated first.
; Without this, the installer fails with "file in use" errors because
; the kokoro.exe sidecar keeps running even after the main app exits.

!macro NSIS_HOOK_PREINSTALL
    DetailPrint "Stopping any running Kokoro TTS processes..."

    ; Kill the main Tauri app
    nsExec::ExecToLog 'taskkill /f /im "kokoro-clipboard-tts.exe" /t'
    
    ; Kill the sidecar binary (release mode name)
    nsExec::ExecToLog 'taskkill /f /im "kokoro-x86_64-pc-windows-msvc.exe" /t'
    nsExec::ExecToLog 'taskkill /f /im "kokoro.exe" /t'
    
    ; Kill anything holding port 8790 (the sidecar HTTP server)
    nsExec::ExecToLog 'powershell -Command "Get-NetTCPConnection -LocalPort 8790 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"'

    ; Brief pause to let file handles release
    Sleep 1000
!macroend
