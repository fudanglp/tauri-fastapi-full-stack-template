# Inter-Process Communication (IPC)

This document describes how the frontend, Tauri (Rust backend), and FastAPI (Python sidecar) communicate with each other.

## Table of Contents

- **[Overview](#overview)**
- **[Why This Architecture?](#why-this-architecture)**
- **[Communication Patterns](#communication-patterns)**
- **[Architecture Overview](#architecture-overview)**
- **[1. Frontend → Tauri (Rust)](#1-frontend--tauri-rust)** - Tauri Commands (IPC)
- **[2. Frontend → FastAPI](#2-frontend--fastapi)** - HTTP REST
- **[3. Tauri (Rust) → FastAPI](#3-tauri-rust--fastapi)** - HTTP (ureq)
- **[4. FastAPI → Tauri (Rust)](#4-fastapi--tauri-rust)** - Unix socket (loopback TCP on Windows)
- **[Summary Table](#summary-table)**
- **[Communication Flow Examples](#communication-flow-examples)**
- **[Recommendations](#recommendations)**

---

## Overview

This template uses a **three-process architecture**:

1. **Frontend (React/TypeScript)** - Runs in Tauri WebView, handles UI and user interactions
2. **Tauri (Rust Backend)** - Desktop app shell, manages native OS features and system integration
3. **FastAPI (Python Sidecar)** - Business logic server, handles database operations and API endpoints

## Why This Architecture?

Each process has a specific purpose:

| Component | Responsibility | Why Separate? |
|-----------|---------------|---------------|
| **Frontend** | UI/UX, user interactions | Web technologies are fast to develop and familiar |
| **Tauri (Rust)** | Native OS access, windows, tray | Rust provides safe, low-level system access |
| **FastAPI (Python)** | Business logic, database | Python ecosystem has excellent libraries for data processing |

## Communication Patterns

The three processes communicate in **four directions**:

1. **Frontend → Tauri** (IPC Commands) - Native operations like file dialogs, windows
2. **Frontend → FastAPI** (HTTP REST) - Database queries, business logic
3. **Tauri → FastAPI** (HTTP) - Health checks during startup
4. **FastAPI → Tauri** (Unix socket, loopback TCP on Windows) - Desktop features like window control

Each direction uses the appropriate method for its use case, balancing performance, security, and developer experience.

---

## Architecture Overview

```mermaid
graph TB
    subgraph "Tauri Desktop App"
        Frontend[Frontend<br/>React/TypeScript]
        Rust[Rust Backend<br/>Tauri]
        Frontend <-->|IPC Commands| Rust
    end

    Frontend -->|HTTP REST<br/>localhost:1420→1430| FastAPI
    FastAPI -->|Unix socket: tauri-fastapi.sock<br/>Windows: 127.0.0.1, port in tauri-fastapi.port| Rust

    subgraph "FastAPI Sidecar"
        FastAPI[FastAPI<br/>Python]
        DB[(SQLite DB)]
        FastAPI --> DB
    end

    style Frontend fill:#61dafb
    style Rust fill:#f74c00
    style FastAPI fill:#009688
    style DB fill:#f0db4f
```

## 1. Frontend → Tauri (Rust)

**Method**: Tauri Commands (IPC)

**Documentation**: https://tauri.app/v2/api/js/namespacecore/#function-invoke

Tauri provides a command-based IPC system. The frontend invokes Rust functions directly using `invoke()`.

### Rust Side
```rust
// tauri/src/lib.rs
#[tauri::command]
fn get_data_dir(app: tauri::AppHandle) -> Result<String, String> {
    app.path()
        .app_data_dir()
        .map(|p| p.to_string_lossy().to_string())
        .map_err(|e| e.to_string())
}

// Register commands
fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            get_data_dir,
            is_dev_mode,
            toggle_window_maximize,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### Frontend Side
```typescript
import { invoke } from '@tauri-apps/api/core';

interface WindowStateResponse {
  success: boolean;
  message: string;
}

// Call Tauri command
export async function toggleWindowMaximize(): Promise<WindowStateResponse> {
  return invoke<WindowStateResponse>('toggle_window_maximize');
}
```

**Use cases**:
- OS-level operations (file system, native dialogs)
- Desktop-specific features (windows, tray)
- Hardware access (USB, Bluetooth, serial ports)
- Performance-critical operations

## 2. Frontend → FastAPI

**Method**: HTTP REST

**Documentation**: https://fastapi.tiangolo.com/

The frontend calls the FastAPI backend using standard HTTP requests. API clients are auto-generated from the OpenAPI schema.

### Frontend Side
```typescript
// frontend/src/services/api.ts - AUTO-GENERATED
import { client } from './client';

export async function getUsers() {
  return client.GET('/api/users/');
}

export async function createUser(data: UserCreate) {
  return client.POST('/api/users/', { body: data });
}
```

### FastAPI Side
```python
# fastapi/app/api/routes/users.py
from fastapi import APIRouter, Depends
from app.models import User, UserCreate
from app.crud import create_user

router = APIRouter()

@router.post("/", response_model=User)
def create_new_user(user: UserCreate, session: Session = Depends(get_session)):
    return create_user(session=session, user=user)
```

**Use cases**:
- Database operations (CRUD)
- Business logic
- Authentication (if enabled)
- Data processing and validation
- Background tasks

## 3. Tauri (Rust) → FastAPI

**Implementation**: HTTP (ureq client)

**Documentation**: https://docs.rs/ureq/

Rust calls FastAPI using synchronous HTTP requests via the `ureq` library. This is used for health checks and initialization.

### Rust Implementation

**Rust Side** (`tauri/src/lib.rs`):
```rust
use ureq;

fn wait_for_backend() -> Result<(), String> {
    let health_endpoint = SETTINGS.health_endpoint(); // "http://localhost:1430/api/v1/health"
    let timeout = SETTINGS.health_check_timeout();
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
        thread::sleep(SETTINGS.health_check_interval());
    }

    Err(format!(
        "Backend not ready after {:?}. Is it running? Try: make fastapi",
        timeout
    ))
}
```

**FastAPI Side** (`fastapi/app/api/main.py`):
```python
@router.get("/health")
async def health_check():
    """Health check endpoint for Rust backend."""
    return {"status": "healthy"}
```

**Use cases**:
- Health checks during startup (implemented)
- Verifying FastAPI is ready before proceeding
- Simple one-way requests from Rust to Python

**Note**: Database operations should stay in FastAPI. Rust should call FastAPI endpoints rather than accessing the database directly.

## 4. FastAPI → Tauri (Rust)

**Implementation**: Axum server over a Unix socket (Linux, macOS) or a loopback TCP port (Windows)

**Documentation**: https://docs.rs/axum/

FastAPI communicates with Tauri through a small Axum HTTP server running in Rust. This is used for desktop-specific features like window state control.

The transport depends on the platform, because `tokio::net::UnixListener` and Python's `socket.AF_UNIX` exist only on Unix:

- **Linux, macOS**: Axum listens on a Unix socket file, `tauri-fastapi.sock`.
- **Windows**: Axum binds `127.0.0.1` on a port the OS assigns, then writes that port number to `tauri-fastapi.port`. FastAPI reads the file and connects over TCP.

The HTTP routes (`GET /health`, `POST /window`) are identical on both transports.

### Rust Side (Axum Server)

**File**: `tauri/src/socket_server.rs`

```rust
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
        fs::remove_file(&socket_path)?; // clear a stale socket left by a crash
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

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    let _ = fs::remove_file(&port_file);
    Ok(())
}
```

### FastAPI Side (Socket Client)

**File**: `fastapi/app/api/routes/window.py`

`_connect()` hides the platform difference, so the route handlers send the same raw HTTP request on either transport:

```python
IS_WINDOWS = sys.platform == "win32"


def _connect(endpoint: str, timeout: float) -> socket.socket:
    """Open a stream connection to the Tauri IPC server."""
    if IS_WINDOWS:
        with open(endpoint, encoding="utf-8") as f:
            port = int(f.read().strip())
        return socket.create_connection(("127.0.0.1", port), timeout=timeout)

    sock_obj = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock_obj.settimeout(timeout)
    sock_obj.connect(endpoint)
    return sock_obj


@router.post("/window")
async def toggle_window_state(request: WindowStateRequest):
    sock_obj = _connect(get_socket_path(), timeout=1.0)
    try:
        body = json.dumps({"action": request.action}).encode()
        http_request = (
            f"POST /window HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"\r\n".encode()
        )
        sock_obj.sendall(http_request + body)
        response = sock_obj.recv(4096).decode()
    finally:
        sock_obj.close()

    return {"status": "success", "message": "Window state changed"}
```

### Example: Window State Control

**Current implementation**:
1. User clicks "Toggle Maximize" button in frontend
2. Frontend calls `POST /api/v1/window`
3. FastAPI forwards the request over the IPC socket
4. Rust Axum server receives and processes request
5. Tauri maximizes/restores the window

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant FastAPI
    participant Socket as IPC socket
    participant Rust as Tauri Rust

    User->>Frontend: Click "Toggle Maximize"
    Frontend->>FastAPI: POST /api/v1/window
    FastAPI->>Socket: POST /window {"action": "toggle"}
    Socket->>Rust: Axum receives request
    Rust->>Rust: Toggle window state
    Rust-->>Socket: 200 OK
    Socket-->>FastAPI: Response
    FastAPI-->>Frontend: {"status": "success"}
    Frontend->>User: Show success toast
```

### Endpoint Location

Both sides resolve the same directory, checking in order: `XDG_RUNTIME_DIR`, `TMP`, `TEMP`, then `/tmp`. Keep `get_runtime_dir()` in Rust and `get_socket_path()` in Python in sync.

| Platform | Endpoint file | What it is |
|----------|---------------|------------|
| Linux | `$XDG_RUNTIME_DIR/tauri-fastapi.sock` (else `/tmp/tauri-fastapi.sock`) | The Unix socket |
| macOS | `/tmp/tauri-fastapi.sock` (or under `$TMP` if set) | The Unix socket |
| Windows | `%TMP%\tauri-fastapi.port`, e.g. `C:\Users\<user>\AppData\Local\Temp\tauri-fastapi.port` | Text file holding the TCP port on `127.0.0.1` |

**Trade-offs**:
- **Unix socket**: no TCP overhead and no port to allocate. Access follows the socket file's permissions.
- **Loopback TCP (Windows)**: the OS-assigned port avoids conflicts, and the server is not reachable from the network. Unlike a socket file, any local process can connect to the port.
- **Stale endpoint after a crash**: on Unix the server deletes a leftover socket at startup. On Windows a leftover `.port` file points at a closed port, so FastAPI answers `503` ("Connection refused") until the app starts again and rewrites the file.

## Summary Table

| Direction | Method | Implementation | Use Cases |
|-----------|--------|----------------|-----------|
| Frontend → Rust | IPC (Tauri Commands) | Built-in, `invoke()` | Native operations, system access |
| Frontend → FastAPI | HTTP REST | Auto-generated clients | Database, business logic, auth |
| FastAPI → Rust | Unix socket (loopback TCP on Windows) | Axum server + Python socket client | Window control, desktop integration |

## Communication Flow Examples

### Example 1: User Login

Frontend checks if running in dev mode (optional), then authenticates with FastAPI:

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant Rust as Tauri (Rust)
    participant FastAPI
    participant DB as SQLite

    User->>Frontend: Enter credentials
    Frontend->>Rust: invoke('is_dev_mode')
    Rust-->>Frontend: true/false
    Frontend->>FastAPI: POST /api/v1/auth/login
    FastAPI->>DB: Query user
    DB-->>FastAPI: User data
    FastAPI->>FastAPI: Verify password
    FastAPI-->>Frontend: Session token
    Frontend->>Frontend: Store token
    Frontend->>User: Redirect to dashboard
```

### Example 2: Toggle Window Maximize

Frontend triggers window state change through FastAPI to Rust:

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant FastAPI
    participant Socket as IPC socket
    participant Rust as Tauri (Rust)

    User->>Frontend: Click "Toggle Maximize"
    Frontend->>FastAPI: POST /api/v1/window {"action": "toggle"}
    FastAPI->>Socket: POST /window {"action": "toggle"}
    Socket->>Rust: Axum receives request
    Rust->>Rust: window.is_maximized()
    Rust->>Rust: window.maximize() or unmaximize()
    Rust-->>Socket: 200 OK
    Socket-->>FastAPI: Response
    FastAPI-->>Frontend: {"status": "success"}
    Frontend->>User: Show success toast
```

### Example 3: Database Query

Frontend fetches data from FastAPI:

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant FastAPI
    participant DB as SQLite

    User->>Frontend: Navigate to /users
    Frontend->>FastAPI: GET /api/v1/users/
    FastAPI->>DB: SELECT * FROM users
    DB-->>FastAPI: User records
    FastAPI->>FastAPI: Serialize to JSON
    FastAPI-->>Frontend: JSON response
    Frontend->>Frontend: Render user table
    Frontend->>User: Display users
```

## Recommendations

1. **Use Tauri commands** for anything native (files, windows, system features)
2. **Keep all database operations in FastAPI** - don't access SQLite directly from Rust
3. **The IPC socket** (Unix socket, or loopback TCP on Windows) for FastAPI → Rust when needing desktop features (window control, tray, etc.)
4. **HTTP (ureq)** for Rust → FastAPI for health checks and simple requests
5. **HTTP REST** for Frontend → FastAPI (standard, testable, auto-generated clients)
