use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, Manager};
use tokio::signal;

#[derive(Debug, Deserialize, Serialize)]
pub struct WindowStateRequest {
    pub action: String,
}

#[derive(Debug, Serialize)]
pub struct SocketResponse {
    pub success: bool,
    pub message: String,
}

#[derive(Clone)]
pub struct AppState {
    pub app_handle: Arc<Mutex<Option<AppHandle>>>,
}

async fn health() -> &'static str {
    "OK"
}

async fn toggle_window_state(
    State(state): State<AppState>,
    Json(req): Json<WindowStateRequest>,
) -> Result<Json<SocketResponse>, StatusCode> {
    let handle_guard = state.app_handle.lock().unwrap();
    if let Some(app_handle) = handle_guard.as_ref() {
        if let Some(window) = app_handle.get_webview_window("main") {
            match req.action.as_str() {
                "toggle" => {
                    let is_maximized = window.is_maximized().unwrap_or(false);
                    if is_maximized {
                        window.unmaximize().map_err(|e| {
                            log::error!("Failed to unmaximize window: {}", e);
                            StatusCode::INTERNAL_SERVER_ERROR
                        })?;
                        return Ok(Json(SocketResponse {
                            success: true,
                            message: "Window restored".to_string(),
                        }));
                    } else {
                        window.maximize().map_err(|e| {
                            log::error!("Failed to maximize window: {}", e);
                            StatusCode::INTERNAL_SERVER_ERROR
                        })?;
                        return Ok(Json(SocketResponse {
                            success: true,
                            message: "Window maximized".to_string(),
                        }));
                    }
                }
                "maximize" => {
                    window.maximize().map_err(|e| {
                        log::error!("Failed to maximize window: {}", e);
                        StatusCode::INTERNAL_SERVER_ERROR
                    })?;
                    return Ok(Json(SocketResponse {
                        success: true,
                        message: "Window maximized".to_string(),
                    }));
                }
                "restore" | "unmaximize" => {
                    window.unmaximize().map_err(|e| {
                        log::error!("Failed to unmaximize window: {}", e);
                        StatusCode::INTERNAL_SERVER_ERROR
                    })?;
                    return Ok(Json(SocketResponse {
                        success: true,
                        message: "Window restored".to_string(),
                    }));
                }
                _ => {
                    return Err(StatusCode::BAD_REQUEST);
                }
            }
        } else {
            log::error!("Main window not found");
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
    } else {
        Err(StatusCode::SERVICE_UNAVAILABLE)
    }
}

fn create_router(state: AppState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/window", post(toggle_window_state))
        .with_state(state)
}

fn get_runtime_dir() -> PathBuf {
    let runtime_dir = std::env::var("XDG_RUNTIME_DIR")
        .or_else(|_| std::env::var("TMP"))
        .or_else(|_| std::env::var("TEMP"))
        .unwrap_or_else(|_| "/tmp".to_string());

    PathBuf::from(runtime_dir)
}

/// Unix socket path used on Linux/macOS.
#[cfg(unix)]
pub fn get_socket_path() -> PathBuf {
    get_runtime_dir().join("tauri-fastapi.sock")
}

/// On Windows (no AF_UNIX support in tokio), the server listens on a loopback
/// TCP port and writes that port number to this file for FastAPI to read.
#[cfg(not(unix))]
pub fn get_port_file_path() -> PathBuf {
    get_runtime_dir().join("tauri-fastapi.port")
}

pub async fn run_socket_server(app_handle: AppHandle) -> Result<(), Box<dyn std::error::Error>> {
    let state = AppState {
        app_handle: Arc::new(Mutex::new(Some(app_handle))),
    };

    serve(create_router(state)).await
}

#[cfg(unix)]
async fn serve(app: Router) -> Result<(), Box<dyn std::error::Error>> {
    use tokio::net::UnixListener;

    let socket_path = get_socket_path();

    if socket_path.exists() {
        fs::remove_file(&socket_path)?;
    }

    let listener = UnixListener::bind(&socket_path)?;

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    let _ = fs::remove_file(&socket_path);

    Ok(())
}

#[cfg(not(unix))]
async fn serve(app: Router) -> Result<(), Box<dyn std::error::Error>> {
    use tokio::net::TcpListener;

    // Port 0 lets the OS pick a free port, avoiding collisions.
    let listener = TcpListener::bind(("127.0.0.1", 0)).await?;
    let port = listener.local_addr()?.port();

    let port_file = get_port_file_path();
    fs::write(&port_file, port.to_string())?;
    log::info!("IPC server listening on 127.0.0.1:{} ({})", port, port_file.display());

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    let _ = fs::remove_file(&port_file);

    Ok(())
}

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("failed to install signal handler")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
}
