mod config;

use std::thread;
use std::time::Instant;
use tauri::Manager;

#[cfg(not(debug_assertions))]
use std::collections::HashMap;
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

use config::{Settings, SETTINGS};

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
            let (_rx, _child) = app
                .shell()
                .sidecar("fastapi-server")
                .map_err(|e| format!("Failed to create sidecar command: {}", e))?
                .envs(env)
                .spawn()
                .map_err(|e| format!("Failed to spawn sidecar: {}", e))?;

            log::info!("FastAPI sidecar spawned");
        }
    }

    // Wait for backend to be ready (both dev and prod)
    wait_for_backend()
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

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // Start backend on app setup
            if let Err(e) = start_backend(app.handle()) {
                log::error!("Failed to start backend: {}", e);
                panic!("Failed to start backend: {}", e);
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![get_data_dir, is_dev_mode])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
