fn main() {
    #[cfg(windows)]
    {
        let _ = std::process::Command::new("taskkill")
            .args(["/F", "/IM", "kokoro-x86_64-pc-windows-msvc.exe", "/T"])
            .output();
        let _ = std::process::Command::new("taskkill")
            .args(["/F", "/IM", "kokoro-clipboard-tts.exe", "/T"])
            .output();
    }
    tauri_build::build()
}
