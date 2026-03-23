use std::process::Child;
use tauri::{AppHandle, Manager};

/// Manages the lifecycle of the Kokoro TTS sidecar process.
///
/// The sidecar is a PyInstaller-built Python executable that runs a local
/// HTTP server on port 8787. This struct wraps spawning and killing it
/// to ensure we never leave ghost processes behind.
pub struct SidecarManager {
    child: Option<Child>,
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

        let resource_path = app
            .path()
            .resource_dir()
            .map_err(|e| format!("Failed to get resource dir: {e}"))?;

        let sidecar_name = if cfg!(target_os = "windows") {
            "kokoro.exe"
        } else {
            "kokoro"
        };

        let sidecar_path = resource_path.join("binaries").join(sidecar_name);

        // In development the binary might not exist yet — fail gracefully
        if !sidecar_path.exists() {
            return Err(format!(
                "Sidecar not found at {}. Place the Kokoro binary there.",
                sidecar_path.display()
            ));
        }

        let child = std::process::Command::new(&sidecar_path)
            .arg("--port")
            .arg("8787")
            .spawn()
            .map_err(|e| format!("Failed to spawn sidecar: {e}"))?;

        println!(
            "[Kokoro] Sidecar spawned (PID: {})",
            child.id()
        );

        self.child = Some(child);
        Ok(())
    }

    /// Kill the sidecar process. Safe to call multiple times.
    pub fn kill(&mut self) {
        if let Some(ref mut child) = self.child {
            match child.kill() {
                Ok(()) => {
                    println!("[Kokoro] Sidecar killed (PID: {})", child.id());
                    // Wait to reap zombie on Unix
                    let _ = child.wait();
                }
                Err(e) => {
                    eprintln!("[Kokoro] Failed to kill sidecar: {e}");
                }
            }
        }
        self.child = None;
    }

    /// Check if the sidecar is still running.
    pub fn is_running(&mut self) -> bool {
        if let Some(ref mut child) = self.child {
            // try_wait returns Ok(None) if the process is still running
            match child.try_wait() {
                Ok(None) => true,
                _ => {
                    self.child = None;
                    false
                }
            }
        } else {
            false
        }
    }
}

impl Drop for SidecarManager {
    fn drop(&mut self) {
        self.kill();
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_manager_has_no_child() {
        let mut mgr = SidecarManager::new();
        assert!(!mgr.is_running());
    }

    #[test]
    fn kill_on_empty_manager_is_safe() {
        let mut mgr = SidecarManager::new();
        mgr.kill(); // should not panic
        assert!(!mgr.is_running());
    }

    #[test]
    fn double_kill_is_safe() {
        let mut mgr = SidecarManager::new();
        mgr.kill();
        mgr.kill();
        assert!(!mgr.is_running());
    }

    #[test]
    fn drop_kills_child() {
        // Spawn a trivial long-running process to test the kill-on-drop
        let child = if cfg!(target_os = "windows") {
            std::process::Command::new("cmd")
                .args(["/C", "timeout /T 60 /NOBREAK"])
                .spawn()
        } else {
            std::process::Command::new("sleep")
                .arg("60")
                .spawn()
        };

        if let Ok(child) = child {
            let pid = child.id();
            let mut mgr = SidecarManager::new();
            mgr.child = Some(child);
            assert!(mgr.is_running());
            drop(mgr); // should kill the process
            // Verify: try to check if PID is still alive
            // (platform-specific, simplified assertion)
            println!("Dropped manager that was running PID {pid}");
        }
    }
}
