use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_shell::{process::CommandChild, ShellExt};
use std::time::Duration;

/// Manages the lifecycle of the Kokoro TTS sidecar process.
///
/// The sidecar is a PyInstaller-built Python executable that runs a local
/// HTTP server on port 8787. This struct wraps spawning and killing it
/// to ensure we never leave ghost processes behind.
pub struct SidecarManager {
    child: Option<CommandChild>,
    pub status: Arc<Mutex<String>>,
}

impl SidecarManager {
    pub fn new() -> Self {
        Self { 
            child: None,
            status: Arc::new(Mutex::new("disconnected".into())),
        }
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
            // Kill by image name (for bundled builds)
            let _ = std::process::Command::new("taskkill")
                .args(["/F", "/IM", "kokoro-x86_64-pc-windows-msvc.exe", "/T"])
                .output();
            let _ = std::process::Command::new("taskkill")
                .args(["/F", "/IM", "kokoro.exe", "/T"])
                .output();
                
            // Aggressive: Kill anything holding port 8790 (where our sidecar lives)
            // This is the definitive way to clear a zombie python.exe in dev mode.
            let _ = std::process::Command::new("powershell")
                .args(["-Command", "Get-NetTCPConnection -LocalPort 8790 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"])
                .output();
        }

        {
            let mut s = self.status.lock().unwrap();
            *s = "starting".into();
        }
        let _ = app.emit("sidecar-status", "starting");

        println!("[Kokoro] Attempting to spawn sidecar...");

        // ─── Development vs Production Spawning ───
        
        let (mut rx, child) = if cfg!(debug_assertions) {
            println!("[Kokoro] DEBUG MODE: Spawning sidecar from source using venv...");
            
            // Resolve project root robustly
            let mut project_root = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
            
            // If we are currently in src-tauri, go up one level
            if project_root.ends_with("src-tauri") {
                project_root = project_root.parent().unwrap().to_path_buf();
            }

            let mut python_path = if cfg!(target_os = "windows") {
                project_root.join(".sidecar-venv").join("Scripts").join("python.exe")
            } else {
                project_root.join(".sidecar-venv").join("bin").join("python")
            };
            
            let script_path = project_root.join("sidecar").join("kokoro_server.py");

            // If not found at current_dir, try a few levels up (sometimes dev runners change CWD)
            if !python_path.exists() {
               if let Ok(exe_path) = std::env::current_exe() {
                   let mut p = exe_path.clone();
                   // Try to find the root by looking for .sidecar-venv
                   for _ in 0..10 {
                       if p.join(".sidecar-venv").exists() {
                           project_root = p;
                           python_path = if cfg!(target_os = "windows") {
                               project_root.join(".sidecar-venv").join("Scripts").join("python.exe")
                           } else {
                               project_root.join(".sidecar-venv").join("bin").join("python")
                           };
                           break;
                       }
                       if let Some(parent) = p.parent() {
                           p = parent.to_path_buf();
                       } else {
                           break;
                       }
                   }
               }
            }

            println!("[Kokoro] Final Project Root: {:?}", project_root);
            println!("[Kokoro] Venv Python: {:?}", python_path);

            if !python_path.exists() {
                return Err(format!("Python venv not found. Tried looking in {:?} and path {:?}", project_root, python_path));
            }

            let cmd = app.shell().command(python_path.to_string_lossy().to_string())
                .args([script_path.to_string_lossy().to_string()]);
            
            cmd.spawn().map_err(|e| format!("Failed to spawn python source: {e}"))?
        } else {
            println!("[Kokoro] RELEASE MODE: Spawning bundled sidecar binary...");
            let sidecar = app.shell()
                .sidecar("kokoro")
                .map_err(|e| format!("Failed to create sidecar command: {e}"))?;

            sidecar.spawn().map_err(|e| format!("Failed to spawn sidecar binary: {e}"))?
        };

        let handle_for_stdout = app.clone();
        tauri::async_runtime::spawn(async move {
            use tauri_plugin_shell::process::CommandEvent;
            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(line) => {
                        let line_str = String::from_utf8_lossy(&line);
                        // Emit events based on sidecar logs for the frontend
                        if line_str.contains("Chunk 0") {
                            let _ = handle_for_stdout.emit("tts-speaking", ());
                        } else if line_str.contains("[STATUS] FINISHED") {
                            let _ = handle_for_stdout.emit("tts-finished", ());
                        } else if line_str.contains("[STATUS] ERROR") {
                            let _ = handle_for_stdout.emit("tts-error", line_str.replace("[STATUS] ERROR:", "").trim());
                        }
                        print!("{}", line_str);
                    }
                    CommandEvent::Stderr(line) => {
                        eprint!("{}", String::from_utf8_lossy(&line));
                    }
                    CommandEvent::Terminated(payload) => {
                        println!("[Kokoro] Sidecar terminated with payload: {:?}", payload);
                        let _ = handle_for_stdout.emit("tts-finished", ());
                    }
                    CommandEvent::Error(err) => {
                        eprintln!("[Kokoro] Sidecar event error: {}", err);
                        let _ = handle_for_stdout.emit("tts-error", err.to_string());
                    }
                    _ => {}
                }
            }
        });

        self.child = Some(child);
        
        // ─── Health Check Polling ───
        let handle_for_health = app.clone();
        let status_arc = Arc::clone(&self.status);
        tauri::async_runtime::spawn(async move {
            let client = reqwest::Client::builder()
                .timeout(Duration::from_millis(500))
                .build()
                .unwrap_or_default();
            
            let mut attempts = 0;
            let max_attempts = 100; // ~50 seconds total
            
            while attempts < max_attempts {
                match client.get("http://127.0.0.1:8790/health").send().await {
                    Ok(res) if res.status().is_success() => {
                        println!("[Kokoro] Sidecar is healthy and ready.");
                        {
                            let mut s = status_arc.lock().unwrap();
                            *s = "ready".into();
                        }
                        let _ = handle_for_health.emit("sidecar-status", "ready");
                        break;
                    }
                    _ => {
                        attempts += 1;
                        if attempts % 10 == 0 {
                            println!("[Kokoro] Waiting for sidecar health check... (attempt {})", attempts);
                        }
                        tokio::time::sleep(Duration::from_millis(500)).await;
                    }
                }
            }
            
            if attempts >= max_attempts {
                eprintln!("[Kokoro] Sidecar health check timed out.");
                {
                    let mut s = status_arc.lock().unwrap();
                    *s = "error:timeout".into();
                }
                let _ = handle_for_health.emit("sidecar-status", "error:timeout");
            }
        });

        Ok(())
    }

    /// Kill the sidecar process. Safe to call multiple times.
    pub fn kill(&mut self) {
        if let Some(child) = self.child.take() {
            let pid = child.pid();
            match child.kill() {
                Ok(()) => {
                    println!("[Kokoro] Sidecar killed (PID: {})", pid);
                    let mut s = self.status.lock().unwrap();
                    *s = "disconnected".into();
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
