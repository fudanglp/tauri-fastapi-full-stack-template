mod config;
mod socket_server;

use std::sync::Mutex;
use std::thread;
use std::time::Instant;
use tauri::Manager;
use tauri::AppHandle;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;

#[cfg(not(debug_assertions))]
use std::collections::HashMap;
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

use config::{Settings, SETTINGS};
use socket_server::run_socket_server;

// Global state to hold the sidecar process handle
struct SidecarState {
    #[allow(dead_code)]  // Only used in non-debug builds
    child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
}

unsafe impl Send for SidecarState {}
unsafe impl Sync for SidecarState {}

/// Wait for the backend to be ready by polling the health endpoint.
/// Returns Ok(()) when backend is ready, Err after timeout.
fn wait_for_backend() -> Result<(), String> {
    let backend_url = SETTINGS.backend_url();
    let health_endpoint = SETTINGS.health_endpoint();
    let timeout = SETTINGS.health_check_timeout();
    let interval = SETTINGS.health_check_interval();

    log::info!("Waiting for backend at {}...", backend_url);
    let start = Instant::now();

    while start.elapsed() < timeout {
        match ureq::get(&health_endpoint).call() {
            Ok(response) if response.status() == 200 => {
                log::info!("Backend is ready (took {:?})", start.elapsed());
                return Ok(());
            }
            Ok(response) => {
                log::debug!("Health check returned status {}", response.status());
            }
            Err(e) => {
                log::debug!("Health check failed: {}", e);
            }
        }
        thread::sleep(interval);
    }

    Err(format!(
        "Backend not ready after {:?}. Is it running? Try: make fastapi",
        timeout
    ))
}

/// Start the FastAPI backend.
/// - In development: assumes backend is running separately (uvicorn --reload)
/// - In production: spawns the bundled sidecar binary
#[allow(unused_variables)]
fn start_backend(app: &tauri::AppHandle) -> Result<(), String> {
    if Settings::is_dev_mode() {
        log::info!("Dev mode: expecting FastAPI backend at {}", SETTINGS.backend_url());
        log::info!("Run: make fastapi");
    } else {
        #[cfg(not(debug_assertions))]
        {
            // Get app data directory
            let data_dir = app
                .path()
                .app_data_dir()
                .map_err(|e| format!("Failed to get app data dir: {}", e))?;

            // Ensure directory exists
            std::fs::create_dir_all(&data_dir)
                .map_err(|e| format!("Failed to create data dir: {}", e))?;

            log::info!("Starting FastAPI sidecar with DATA_DIR={:?}", data_dir);

            // Set environment variables for the sidecar
            let mut env: HashMap<String, String> = HashMap::new();
            env.insert("DATA_DIR".into(), data_dir.to_string_lossy().to_string());
            env.insert("HOST".into(), SETTINGS.host.clone());
            env.insert("PORT".into(), SETTINGS.port.to_string());

            // Spawn the sidecar
            let (_rx, child) = app
                .shell()
                .sidecar("fastapi-server")
                .map_err(|e| format!("Failed to create sidecar command: {}", e))?
                .envs(env)
                .spawn()
                .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

            // Store the child handle for cleanup
            let state = app.state::<SidecarState>();
            *state.child.lock().unwrap() = Some(child);

            log::info!("FastAPI sidecar spawned");
        }
    }

    // Wait for backend to be ready (both dev and prod)
    wait_for_backend()
}

/// Stop the FastAPI sidecar gracefully.
#[allow(unused_variables)]
fn stop_backend(app: &tauri::AppHandle) {
    if Settings::is_dev_mode() {
        log::info!("Dev mode: no sidecar to stop");
        return;
    }

    #[cfg(not(debug_assertions))]
    {
        let state = app.state::<SidecarState>();
        let mut child_guard = state.child.lock().unwrap();

        if let Some(child) = child_guard.take() {
            log::info!("Stopping FastAPI sidecar...");

            let pid = child.pid();

            // Try graceful shutdown first (SIGTERM)
            // Note: CommandChild.kill() consumes self, so we get PID first
            #[cfg(unix)]
            {
                use std::process::{Command, Stdio};

                // Send SIGTERM for graceful shutdown
                if let Err(e) = Command::new("kill")
                    .args(["-TERM", &pid.to_string()])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .status()
                {
                    log::warn!("Failed to send SIGTERM: {}", e);
                } else {
                    // Wait up to 2 seconds for graceful shutdown
                    for _ in 0..20 {
                        thread::sleep(std::time::Duration::from_millis(100));
                        // Check if process is still running
                        if Command::new("kill")
                            .args(["-0", &pid.to_string()])
                            .stdout(Stdio::null())
                            .stderr(Stdio::null())
                            .status()
                            .is_err()
                        {
                            log::info!("FastAPI sidecar stopped gracefully");
                            return;
                        }
                    }
                    // Process still running, force kill
                    log::warn!("Sidecar still running, sending SIGKILL");
                    let _ = Command::new("kill")
                        .args(["-9", &pid.to_string()])
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .status();
                }
            }

            #[cfg(windows)]
            {
                use std::process::{Command, Stdio};

                // On Windows, just use Taskkill with /TERM (graceful)
                let _ = Command::new("taskkill")
                    .args(["/PID", &pid.to_string(), "/T"])
                    .stdout(Stdio::null())
                    .stderr(Stdio::null())
                    .status();
            }

            log::info!("FastAPI sidecar stopped");
        }
    }
}

/// Get the app data directory path
#[tauri::command]
fn get_data_dir(app: tauri::AppHandle) -> Result<String, String> {
    app.path()
        .app_data_dir()
        .map(|p| p.to_string_lossy().to_string())
        .map_err(|e| e.to_string())
}

/// Check if running in development mode
#[tauri::command]
fn is_dev_mode() -> bool {
    Settings::is_dev_mode()
}

/// Toggle window maximize/restore
#[tauri::command]
fn toggle_window_maximize(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        let is_maximized = window.is_maximized().map_err(|e| e.to_string())?;

        if is_maximized {
            window.unmaximize().map_err(|e| e.to_string())?;
        } else {
            window.maximize().map_err(|e| e.to_string())?;
        }
        Ok(())
    } else {
        Err("Main window not found".to_string())
    }
}

/// Create the system tray with menu items
fn create_system_tray(app: &AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    // Create menu items
    let show_item = MenuItem::with_id(app, "show", "Show", true, None::<&str>)?;
    let hide_item = MenuItem::with_id(app, "hide", "Hide", true, None::<&str>)?;
    let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;

    // Create the menu
    let menu = Menu::with_items(app, &[&show_item, &hide_item, &quit_item])?;

    // Create the tray icon using the 32x32 icon
    let _tray = TrayIconBuilder::new()
        .menu(&menu)
        .tooltip("Tauri FastAPI Template")
        .icon(app.default_window_icon().unwrap().clone())
        .build(app)?;

    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .manage(SidecarState {
            child: Mutex::new(None),
        })
        .setup(|app| {
            // Start backend on app setup
            if let Err(e) = start_backend(app.handle()) {
                log::error!("Failed to start backend: {}", e);
                panic!("Failed to start backend: {}", e);
            }

            // Create system tray
            if let Err(e) = create_system_tray(app.handle()) {
                log::error!("Failed to create system tray: {}", e);
            }

            // Start Unix socket server for FastAPI communication
            let app_handle = app.handle().clone();

            thread::spawn(move || {
                let rt = tokio::runtime::Runtime::new()
                    .expect("Failed to create tokio runtime");

                rt.block_on(async {
                    if let Err(e) = run_socket_server(app_handle).await {
                        log::error!("Socket server error: {}", e);
                    }
                });
            });

            Ok(())
        })
        .on_menu_event(|app, event| {
            match event.id.as_ref() {
                "show" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
                "hide" => {
                    if let Some(window) = app.get_webview_window("main") {
                        let _ = window.hide();
                    }
                }
                "quit" => {
                    stop_backend(app.app_handle());
                    app.exit(0);
                }
                _ => {}
            }
        })
        .on_window_event(|app, event| {
            // Handle window close event
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                log::info!("Window close requested, stopping sidecar...");
                stop_backend(app.app_handle());
            }
        })
        .invoke_handler(tauri::generate_handler![get_data_dir, is_dev_mode, toggle_window_maximize])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
