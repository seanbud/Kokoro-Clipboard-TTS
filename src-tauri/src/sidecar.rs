use tauri::AppHandle;
use tauri_plugin_shell::{process::CommandChild, ShellExt};

/// Manages the lifecycle of the Kokoro TTS sidecar process.
///
/// The sidecar is a PyInstaller-built Python executable that runs a local
/// HTTP server on port 8787. This struct wraps spawning and killing it
/// to ensure we never leave ghost processes behind.
pub struct SidecarManager {
    child: Option<CommandChild>,
}

impl SidecarManager {
    pub fn new() -> Self {
        Self { child: None }
    }

    /// Spawn the Kokoro sidecar binary.
    ///
    /// The binary is expected at `src-tauri/binaries/kokoro{.exe}` and
    /// configured via `bundle.externalBin` in `tauri.conf.json`.
    pub fn spawn(&mut self, app: &AppHandle) -> Result<(), String> {
        // If already running, don't double-spawn
        if self.is_running() {
            return Ok(());
        }

        // On Windows, if the developer forcefully stops the Tauri dev server (Ctrl+C),
        // the Rust app dies instantly without running its Exit handler, leaving the sidecar
        // orphaned in the background locking files and ports. Let's kill any ghosts first.
        #[cfg(target_os = "windows")]
        {
            let _ = std::process::Command::new("taskkill")
                .args(["/F", "/IM", "kokoro-x86_64-pc-windows-msvc.exe", "/T"])
                .output();
            let _ = std::process::Command::new("taskkill")
                .args(["/F", "/IM", "kokoro.exe", "/T"])
                .output();
        }

        println!("[Kokoro] Attempting to spawn sidecar: kokoro");
        
        let sidecar = app.shell()
            .sidecar("kokoro")
            .map_err(|e| format!("Failed to create sidecar command: {e}"))?;

        let (mut rx, child) = sidecar.spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {e}"))?;

        tauri::async_runtime::spawn(async move {
            use tauri_plugin_shell::process::CommandEvent;
            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(line) => {
                        print!("{}", String::from_utf8_lossy(&line));
                    }
                    CommandEvent::Stderr(line) => {
                        eprint!("{}", String::from_utf8_lossy(&line));
                    }
                    CommandEvent::Terminated(payload) => {
                        println!("[Kokoro] Sidecar terminated with payload: {:?}", payload);
                    }
                    CommandEvent::Error(err) => {
                        eprintln!("[Kokoro] Sidecar event error: {}", err);
                    }
                    _ => {}
                }
            }
        });

        println!("[Kokoro] Sidecar spawned successfully");

        self.child = Some(child);
        Ok(())
    }

    /// Kill the sidecar process. Safe to call multiple times.
    pub fn kill(&mut self) {
        if let Some(child) = self.child.take() {
            let pid = child.pid();
            match child.kill() {
                Ok(()) => {
                    println!("[Kokoro] Sidecar killed (PID: {})", pid);
                }
                Err(e) => {
                    eprintln!("[Kokoro] Failed to kill sidecar: {e}");
                }
            }
        }
    }

    pub fn is_running(&mut self) -> bool {
        self.child.is_some()
    }
}

impl Drop for SidecarManager {
    fn drop(&mut self) {
        self.kill();
    }
}
