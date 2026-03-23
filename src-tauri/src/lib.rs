use std::sync::Mutex;
use tauri::{
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
    AppHandle, Emitter, Manager, RunEvent, WebviewUrl, WebviewWindowBuilder,
};

mod sidecar;

use sidecar::SidecarManager;

/// State shared across the application.
pub struct AppState {
    pub sidecar: Mutex<SidecarManager>,
}

// ─── Tauri Commands ───────────────────────────────────────────────────────────

#[tauri::command]
async fn send_to_tts(
    text: String,
    speed: f32,
    voice: String,
) -> Result<String, String> {
    let client = reqwest::Client::new();
    let payload = serde_json::json!({
        "text": text,
        "speed": speed,
        "voice": voice,
    });

    let res = client
        .post("http://127.0.0.1:8787/tts")
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("TTS request failed: {e}"))?;

    if res.status().is_success() {
        Ok("ok".into())
    } else {
        Err(format!("TTS server returned {}", res.status()))
    }
}

#[tauri::command]
async fn stop_tts() -> Result<String, String> {
    let client = reqwest::Client::new();
    client
        .post("http://127.0.0.1:8787/stop")
        .send()
        .await
        .map_err(|e| format!("Stop request failed: {e}"))?;
    Ok("stopped".into())
}

#[tauri::command]
async fn move_reader_window(app: AppHandle, x: f64, y: f64) -> Result<(), String> {
    if let Some(win) = app.get_webview_window("reader") {
        win.set_position(tauri::Position::Physical(tauri::PhysicalPosition {
            x: x as i32,
            y: y as i32,
        }))
        .map_err(|e| e.to_string())?;
        win.show().map_err(|e| e.to_string())?;
        win.set_focus().map_err(|e| e.to_string())?;
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
    let settings_item = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
    let updates_item =
        MenuItem::with_id(app, "check_updates", "Check for Updates", true, None::<&str>)?;
    let tutorial_item = MenuItem::with_id(app, "tutorial", "Tutorial", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "Exit", true, None::<&str>)?;

    let menu = Menu::with_items(
        app,
        &[&settings_item, &updates_item, &tutorial_item, &quit_item],
    )?;

    let _tray = TrayIconBuilder::with_id("main-tray")
        .menu(&menu)
        .on_menu_event(move |app, event| match event.id.as_ref() {
            "settings" => {
                if let Some(win) = app.get_webview_window("settings") {
                    let _ = win.show();
                    let _ = win.set_focus();
                } else {
                    let _ = WebviewWindowBuilder::new(
                        app,
                        "settings",
                        WebviewUrl::App("/".into()),
                    )
                    .title("Kokoro TTS — Settings")
                    .inner_size(480.0, 420.0)
                    .resizable(false)
                    .center()
                    .build();
                }
            }
            "check_updates" => {
                let _ = app.emit("check-for-updates", ());
            }
            "tutorial" => {
                if let Some(win) = app.get_webview_window("tutorial") {
                    let _ = win.show();
                    let _ = win.set_focus();
                } else {
                    let _ = WebviewWindowBuilder::new(
                        app,
                        "tutorial",
                        WebviewUrl::App("/".into()),
                    )
                    .title("Welcome to Kokoro TTS")
                    .inner_size(440.0, 360.0)
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

    Ok(())
}

// ─── App Entry ────────────────────────────────────────────────────────────────

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            sidecar: Mutex::new(SidecarManager::new()),
        })
        .invoke_handler(tauri::generate_handler![
            send_to_tts,
            stop_tts,
            move_reader_window,
            hide_reader_window,
        ])
        .setup(|app| {
            let handle = app.handle().clone();

            // ── Spawn TTS sidecar ──
            {
                let state = handle.state::<AppState>();
                let mut mgr = state.sidecar.lock().unwrap();
                if let Err(e) = mgr.spawn(&handle) {
                    eprintln!("[Kokoro] Failed to spawn TTS sidecar: {e}");
                    // Non-fatal: the app can run, TTS calls will fail gracefully
                }
            }

            // ── Setup System Tray ──
            setup_tray(&handle)?;

            // ── Register default global shortcut ──
            // The shortcut trigger is handled on the frontend via the JS plugin API
            // so the frontend can read clipboard + position the reader window.
            // We emit an event that the frontend listens to.

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
