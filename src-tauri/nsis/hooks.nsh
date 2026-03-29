; NSIS hooks for Kokoro Clipboard TTS installer
; This script runs before the installer copies new files, ensuring
; the main app and its sidecar process are fully terminated first.
; Without this, the installer fails with "file in use" errors because
; the kokoro.exe sidecar keeps running even after the main app exits.

!macro NSIS_HOOK_PREINSTALL
    DetailPrint "Stopping any running Kokoro TTS processes..."

    ; First pass: kill the main Tauri app and sidecar
    nsExec::ExecToLog 'taskkill /f /im "kokoro-clipboard-tts.exe" /t'
    nsExec::ExecToLog 'taskkill /f /im "kokoro-x86_64-pc-windows-msvc.exe" /t'
    nsExec::ExecToLog 'taskkill /f /im "kokoro.exe" /t'

    ; Kill anything holding port 8790 (the sidecar HTTP server)
    nsExec::ExecToLog 'powershell -Command "Get-NetTCPConnection -LocalPort 8790 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"'

    ; Wait for file handles to release before second pass
    Sleep 2000

    ; Second pass: catch any processes that survived or restarted during shutdown
    nsExec::ExecToLog 'taskkill /f /im "kokoro-clipboard-tts.exe" /t'
    nsExec::ExecToLog 'taskkill /f /im "kokoro-x86_64-pc-windows-msvc.exe" /t'
    nsExec::ExecToLog 'taskkill /f /im "kokoro.exe" /t'

    ; Final pause to ensure all file handles have been released
    Sleep 1500
!macroend
