use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIcon,
    AppHandle, Emitter, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder,
};

mod sidecar;

use sidecar::SidecarManager;

/// State shared across the application.
pub struct AppState {
    pub sidecar: Mutex<SidecarManager>,
    pub tray: Mutex<Option<TrayIcon>>,
}

#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct ClipboardPayload {
    text: Option<String>,
    html: Option<String>,
}

#[tauri::command]
async fn read_clipboard_payload() -> Result<ClipboardPayload, String> {
    tauri::async_runtime::spawn_blocking(|| {
        let mut clipboard = arboard::Clipboard::new().map_err(|error| error.to_string())?;
        let text = clipboard.get_text().ok();
        let html = clipboard.get().html().ok();

        if text.is_none() && html.is_none() {
            return Err("The clipboard does not contain readable text".into());
        }

        Ok(ClipboardPayload { text, html })
    })
    .await
    .map_err(|error| format!("Clipboard read task failed: {error}"))?
}

// ─── Tauri Commands ───────────────────────────────────────────────────────────

#[tauri::command]
async fn send_to_tts(
    text: String,
    speed: f32,
    voice: String,
    volume: f32,
    request_id: String,
    segments: serde_json::Value,
) -> Result<String, String> {
    let client = reqwest::Client::new();
    let payload = serde_json::json!({
        "text": text,
        "speed": speed,
        "voice": voice,
        "volume": volume,
        "request_id": request_id,
        "segments": segments,
    });

    let res = client
        .post("http://127.0.0.1:8790/tts")
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("TTS request failed: {e}"))?;

    if res.status().is_success() {
        Ok(request_id)
    } else {
        Err(format!("TTS server returned {}", res.status()))
    }
}

async fn post_playback_control(path: &str, request_id: String) -> Result<(), String> {
    let client = reqwest::Client::new();
    let res = client
        .post(format!("http://127.0.0.1:8790/{path}"))
        .json(&serde_json::json!({ "request_id": request_id }))
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if res.status().is_success() {
        Ok(())
    } else {
        Err(format!("Playback control returned {}", res.status()))
    }
}

#[tauri::command]
async fn pause_tts(request_id: String) -> Result<(), String> {
    post_playback_control("pause", request_id).await
}

#[tauri::command]
async fn resume_tts(request_id: String) -> Result<(), String> {
    post_playback_control("resume", request_id).await
}

#[tauri::command]
async fn set_tts_speed(request_id: String, speed: f32) -> Result<(), String> {
    if !(0.5..=2.0).contains(&speed) {
        return Err("Playback speed must be between 0.5 and 2.0".into());
    }
    let client = reqwest::Client::new();
    let res = client
        .post("http://127.0.0.1:8790/speed")
        .json(&serde_json::json!({ "request_id": request_id, "speed": speed }))
        .send()
        .await
        .map_err(|e| format!("Speed request failed: {e}"))?;

    if res.status().is_success() {
        Ok(())
    } else {
        Err(format!("Speed control returned {}", res.status()))
    }
}

#[tauri::command]
async fn stop_tts(request_id: String) -> Result<String, String> {
    post_playback_control("stop", request_id)
        .await
        .map_err(|e| format!("Stop request failed: {e}"))?;
    Ok("stopped".into())
}

#[tauri::command]
async fn get_audio_devices() -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let res = client
        .get("http://127.0.0.1:8790/devices")
        .send()
        .await
        .map_err(|e| format!("Failed to get devices: {e}"))?;

    let json: serde_json::Value = res.json().await.map_err(|e| e.to_string())?;
    Ok(json)
}

#[tauri::command]
async fn set_audio_device(id: i32) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::new();
    let payload = serde_json::json!({ "id": id });
    let res = client
        .post("http://127.0.0.1:8790/devices")
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Failed to set device: {e}"))?;

    let json: serde_json::Value = res.json().await.map_err(|e| e.to_string())?;
    Ok(json)
}

#[tauri::command]
async fn test_audio(volume: f32) -> Result<String, String> {
    let client = reqwest::Client::new();
    let payload = serde_json::json!({ "volume": volume });
    client
        .post("http://127.0.0.1:8790/test_audio")
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Audio test failed: {e}"))?;
    Ok("playing".into())
}

#[tauri::command]
async fn get_sidecar_status(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let mgr = state.sidecar.lock().unwrap();
    let status = mgr.status.lock().unwrap();
    Ok(status.clone())
}

#[tauri::command]
async fn get_sidecar_log_path(state: tauri::State<'_, AppState>) -> Result<String, String> {
    let mgr = state.sidecar.lock().unwrap();
    Ok(mgr
        .log_path
        .as_ref()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_default())
}

#[tauri::command]
async fn start_sidecar(app: AppHandle, state: tauri::State<'_, AppState>) -> Result<(), String> {
    let mut mgr = state.sidecar.lock().unwrap();
    mgr.spawn(&app)
}

#[tauri::command]
async fn ensure_reader_visible(app: AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("reader") {
        let is_visible = win.is_visible().unwrap_or(false);
        if !is_visible {
            // Move to cursor and show
            if let Ok(cursor_pos) = app.cursor_position() {
                let size = win.inner_size().unwrap_or(tauri::PhysicalSize {
                    width: 380,
                    height: 140,
                });
                let x = (cursor_pos.x - (size.width as f64 / 2.0)) as i32;
                let y = (cursor_pos.y - (size.height as f64 / 2.0)) as i32;

                win.set_position(tauri::Position::Physical(tauri::PhysicalPosition { x, y }))
                    .map_err(|e| e.to_string())?;
            }
            win.show().map_err(|e| e.to_string())?;
            win.set_focus().map_err(|e| e.to_string())?;
        } else {
            // Already visible, just focus it
            win.set_focus().map_err(|e| e.to_string())?;
        }
    }
    Ok(())
}

#[tauri::command]
async fn hide_reader_window(app: AppHandle) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("reader") {
        win.hide().map_err(|e| e.to_string())?;
    }
    Ok(())
}

fn setup_tray(app: &AppHandle) -> tauri::Result<()> {
    let read_clipboard_item =
        MenuItem::with_id(app, "read_clipboard", "Read Clipboard", true, None::<&str>)?;
    let settings_item = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
    let updates_item = MenuItem::with_id(
        app,
        "check_updates",
        "Check for Updates",
        true,
        None::<&str>,
    )?;
    let tutorial_item = MenuItem::with_id(app, "tutorial", "Tutorial", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "Exit", true, None::<&str>)?;

    let menu = Menu::with_items(
        app,
        &[
            &read_clipboard_item,
            &settings_item,
            &updates_item,
            &tutorial_item,
            &quit_item,
        ],
    )?;

    let tray_builder = tauri::tray::TrayIconBuilder::with_id("main-tray")
        .icon(app.default_window_icon().unwrap().clone())
        .menu(&menu)
        .tooltip("Kokoro Clipboard TTS");

    #[cfg(target_os = "macos")]
    let tray_builder = tray_builder
        .icon_as_template(true)
        .show_menu_on_left_click(true);

    #[cfg(not(target_os = "macos"))]
    let tray_builder = tray_builder.show_menu_on_left_click(false);

    let tray = tray_builder
        .on_menu_event(move |app, event| match event.id.as_ref() {
            "read_clipboard" => {
                let _ = app.emit("shortcut-triggered", ());
            }
            "settings" => {
                if let Some(win) = app.get_webview_window("settings") {
                    let _ = win.show();
                    let _ = win.set_focus();
                } else {
                    let _ = WebviewWindowBuilder::new(app, "settings", WebviewUrl::App("/".into()))
                        .title("Kokoro TTS — Settings")
                        .inner_size(480.0, 600.0)
                        .resizable(false)
                        .center()
                        .build();
                }
            }
            "check_updates" => {
                if let Some(win) = app.get_webview_window("settings") {
                    let _ = win.show();
                    let _ = win.set_focus();
                    let _ = win.emit("check-for-updates", ());
                }
            }
            "tutorial" => {
                if let Some(win) = app.get_webview_window("tutorial") {
                    let _ = win.show();
                    let _ = win.set_focus();
                } else {
                    let _ = WebviewWindowBuilder::new(app, "tutorial", WebviewUrl::App("/".into()))
                        .title("Welcome to Kokoro TTS")
                        .inner_size(520.0, 480.0)
                        .resizable(false)
                        .center()
                        .decorations(false)
                        .build();
                }
            }
            "quit" => {
                // Kill sidecar before exiting
                if let Some(state) = app.try_state::<AppState>() {
                    let mut mgr = state.sidecar.lock().unwrap();
                    mgr.kill();
                }
                app.exit(0);
            }
            _ => {}
        })
        .build(app)?;

    if let Some(state) = app.try_state::<AppState>() {
        let mut t = state.tray.lock().unwrap();
        *t = Some(tray);
    }

    Ok(())
}

// ─── App Entry ────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let mut builder = tauri::Builder::default();

    // ── Single Instance Guard (must be first plugin) ──
    // If the app is already running, focus the existing instance and exit.
    #[cfg(desktop)]
    {
        builder = builder.plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // When a second instance is launched, just show the settings window
            // of the already-running instance so the user knows it's alive.
            if let Some(win) = app.get_webview_window("settings") {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }));
    }

    let builder = builder
        .plugin(tauri_plugin_log::Builder::new().build())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            sidecar: Mutex::new(SidecarManager::new()),
            tray: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            read_clipboard_payload,
            send_to_tts,
            pause_tts,
            resume_tts,
            set_tts_speed,
            stop_tts,
            ensure_reader_visible,
            hide_reader_window,
            get_audio_devices,
            set_audio_device,
            test_audio,
            get_sidecar_status,
            get_sidecar_log_path,
            start_sidecar,
        ])
        .setup(|app| {
            // ── Show splash window IMMEDIATELY ──
            if let Some(splash) = app.get_webview_window("splash") {
                let _ = splash.show();
            }
            let handle = app.handle().clone();

            // ── Setup System Tray ──
            setup_tray(&handle)?;

            // ── Register default global shortcut ──
            use tauri_plugin_global_shortcut::GlobalShortcutExt;
            #[cfg(target_os = "macos")]
            let shortcut = "control+option+r";
            #[cfg(not(target_os = "macos"))]
            let shortcut = "super+shift+q";
            let handle_for_shortcut = handle.clone();
            app.handle().plugin(
                tauri_plugin_global_shortcut::Builder::new()
                    .with_handler(move |_app, _shortcut, event| {
                        if event.state() == tauri_plugin_global_shortcut::ShortcutState::Pressed {
                            let _ = handle_for_shortcut.emit("shortcut-triggered", ());
                        }
                    })
                    .build(),
            )?;
            app.global_shortcut()
                .register(shortcut)
                .map_err(|e| {
                    eprintln!("[Kokoro] Failed to register shortcut: {e}");
                    e
                })
                .ok();

            // ── Background Clipboard Poller ──────────────────────────────────────────
            // Monitors for any global clipboard change without intercepting shortcuts.
            // Helps provide immediate "subtle" feedback when user copies text anywhere.
            use tauri_plugin_clipboard_manager::ClipboardExt;
            let handle_for_polling = handle.clone();
            tauri::async_runtime::spawn(async move {
                // Initialize with current clipboard content to avoid flash on startup
                let mut last_clipboard = handle_for_polling
                    .clipboard()
                    .read_text()
                    .unwrap_or_default();
                loop {
                    tokio::time::sleep(std::time::Duration::from_millis(150)).await;
                    if let Ok(current) = handle_for_polling.clipboard().read_text() {
                        if !current.is_empty() && current != last_clipboard {
                            // Only emit if the reader widget is actually open
                            let is_visible = if let Some(win) =
                                handle_for_polling.get_webview_window("reader")
                            {
                                win.is_visible().unwrap_or(false)
                            } else {
                                false
                            };

                            if is_visible {
                                let _ = handle_for_polling.emit("global-clipboard-change", ());
                            }
                            last_clipboard = current;
                        }
                    }
                }
            });

            Ok(())
        });

    let app = builder
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    // ── Kill-Switch: ensure sidecar dies when the app exits ──
    app.run(|app_handle, event| {
        if let RunEvent::Exit = event {
            if let Some(state) = app_handle.try_state::<AppState>() {
                let mut mgr = state.sidecar.lock().unwrap();
                mgr.kill();
            }
        }
    });
}
