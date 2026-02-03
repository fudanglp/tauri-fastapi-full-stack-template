# FastAPI Sidecar Integration Plan

## Project Overview

Integrate the `full-stack-fastapi-template` backend and frontend into `tauri-fastapi-full-stack-template` as a desktop application with FastAPI running as a sidecar process.

**Key Decisions:**
- **Sidecar packaging:** PyInstaller (single executable)
- **Authentication:** Opt-in (disabled by default)
- **Database:** SQLite in Tauri's `app_data_dir`
- **Features to keep:** Items CRUD, User management
- **Features to remove:** Email system

---

## Part 1: Analysis

### 1.1 Source Project Structure (full-stack-fastapi-template)

```
full-stack-fastapi-template/
├── fastapi/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py          # Dependencies (auth, db session)
│   │   │   ├── main.py          # Router aggregation
│   │   │   └── routes/
│   │   │       ├── items.py     # Items CRUD [KEEP]
│   │   │       ├── login.py     # Auth endpoints [KEEP, make optional]
│   │   │       ├── users.py     # User management [KEEP]
│   │   │       ├── utils.py     # Health check [KEEP], test email [REMOVE]
│   │   │       └── private.py   # Internal routes [KEEP]
│   │   ├── core/
│   │   │   ├── config.py        # Settings [ADAPT for desktop]
│   │   │   ├── db.py            # Database init [ADAPT for SQLite]
│   │   │   └── security.py      # JWT/password [KEEP]
│   │   ├── models.py            # SQLModel models [KEEP]
│   │   ├── crud.py              # CRUD operations [KEEP]
│   │   ├── utils.py             # Email utils [REMOVE]
│   │   ├── main.py              # FastAPI app [ADAPT]
│   │   └── alembic/             # Migrations [ADAPT for SQLite]
│   ├── pyproject.toml           # Dependencies [ADAPT]
│   └── Dockerfile               # [REMOVE - not needed]
├── frontend/
│   ├── src/
│   │   ├── client/              # Auto-generated API client [KEEP]
│   │   ├── routes/              # TanStack Router pages [KEEP]
│   │   ├── components/          # React components [KEEP]
│   │   └── hooks/               # Custom hooks [KEEP]
│   └── ...
└── scripts/
    └── generate-client.sh       # OpenAPI codegen [KEEP]
```

### 1.2 Technology Stack Comparison

| Component | FastAPI Template | Tauri Template | Integration |
|-----------|------------------|----------------|-------------|
| Frontend Framework | React 19 | React 19 | Compatible ✓ |
| Build Tool | Vite 7.3 | Vite 7.0 | Compatible ✓ |
| TypeScript | 5.9 | 5.8 | Compatible ✓ |
| Package Manager | npm | bun | Use bun |
| Routing | TanStack Router | None | Add TanStack Router |
| State | React Query | None | Add React Query |
| Styling | Tailwind + shadcn | Basic CSS | Add Tailwind + shadcn |
| Backend | FastAPI | Rust (Tauri) | Add FastAPI sidecar |
| Database | PostgreSQL | None | SQLite |
| ORM | SQLModel | None | Keep SQLModel |

### 1.3 Database Migration: PostgreSQL → SQLite

**Changes Required:**

| Aspect | PostgreSQL | SQLite | Action |
|--------|------------|--------|--------|
| Connection string | `postgresql+psycopg://...` | `sqlite:///path/to/db.sqlite` | Update config |
| UUID handling | Native UUID type | TEXT (SQLModel handles) | No change needed |
| Boolean | Native BOOLEAN | INTEGER (0/1) | SQLModel handles |
| DateTime | TIMESTAMP WITH TZ | TEXT (ISO format) | SQLModel handles |
| JSON | JSONB | JSON (TEXT) | Works with JSON1 extension |
| Migrations | Full ALTER TABLE | Limited ALTER | Use batch migrations |
| Concurrency | MVCC, multiple writers | Single writer | Enable WAL mode |

**SQLite-specific configuration:**
```python
# Enable WAL mode for better concurrency
# Enable foreign keys (off by default in SQLite)
engine = create_engine(
    "sqlite:///app.db",
    connect_args={"check_same_thread": False},
    pool_pre_ping=True
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

### 1.4 Authentication: Opt-in Strategy

**Current Flow (Required Auth):**
```
Request → OAuth2 Bearer Token → Validate JWT → Get User → Process
```

**New Flow (Optional Auth):**
```
Request → Check AUTH_REQUIRED setting
  ├─ If True:  OAuth2 Bearer Token → Validate JWT → Get User → Process
  └─ If False: Use DEFAULT_USER (or None) → Process
```

**Implementation approach:**
```python
# deps.py
def get_current_user_optional(
    session: SessionDep,
    token: str | None = Depends(oauth2_scheme_optional)
) -> User | None:
    if not settings.AUTH_REQUIRED:
        return get_or_create_default_user(session)
    if not token:
        raise HTTPException(401, "Not authenticated")
    return validate_token_and_get_user(session, token)
```

**Endpoints behavior when AUTH_REQUIRED=False:**
| Endpoint | Behavior |
|----------|----------|
| `POST /login/access-token` | Still works (for when user enables auth) |
| `GET /users/me` | Returns default user |
| `GET /items/` | Returns all items (single user context) |
| `POST /items/` | Creates item owned by default user |
| `POST /users/signup` | Disabled (returns 403) |

### 1.5 Sidecar Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Tauri Application                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    Rust Core (Tauri)                     │ │
│  │                                                         │ │
│  │  • Spawn FastAPI sidecar on app start                   │ │
│  │  • Monitor sidecar health                               │ │
│  │  • Kill sidecar on app close                            │ │
│  │  • Provide app_data_dir path to sidecar                 │ │
│  │  • Handle native OS integrations                        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            │                                  │
│                   spawn/manage                                │
│                            ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              FastAPI Sidecar (PyInstaller)              │ │
│  │                                                         │ │
│  │  • Runs on localhost:8000 (or dynamic port)             │ │
│  │  • SQLite database in app_data_dir                      │ │
│  │  • Receives config via CLI args or env vars             │ │
│  │  • Health endpoint for readiness check                  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            ▲                                  │
│                    HTTP requests                              │
│                            │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  React Frontend (Webview)               │ │
│  │                                                         │ │
│  │  • Served from Tauri (tauri://localhost)                │ │
│  │  • API calls to http://localhost:8000                   │ │
│  │  • Tauri API for native features                        │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Sidecar lifecycle:**

1. **Startup:**
   - Tauri app starts
   - Rust spawns FastAPI sidecar with `--data-dir` argument
   - Rust polls `/api/v1/utils/health-check/` until ready
   - Frontend loads after sidecar is healthy

2. **Runtime:**
   - Frontend makes HTTP requests to `localhost:8000`
   - Sidecar handles all API logic and database operations
   - Tauri handles native features (file dialogs, notifications, etc.)

3. **Shutdown:**
   - User closes app
   - Tauri sends SIGTERM to sidecar
   - Sidecar gracefully shuts down (commits pending transactions)
   - App exits

### 1.6 File System Layout

```
~/.local/share/com.glp.tauri-fastapi-full-stack-template/  (Linux)
~/Library/Application Support/com.glp.tauri-fastapi-full-stack-template/  (macOS)
C:\Users\<user>\AppData\Roaming\com.glp.tauri-fastapi-full-stack-template\  (Windows)
│
├── app.db                    # SQLite database
├── app.db-wal                # WAL file (auto-created)
├── app.db-shm                # Shared memory (auto-created)
├── config.json               # User preferences (optional)
└── logs/
    └── fastapi.log           # Sidecar logs
```

### 1.7 Features to Remove

| Feature | Files | Reason |
|---------|-------|--------|
| Email system | `utils.py`, `email-templates/` | Desktop app doesn't need SMTP |
| Docker | `Dockerfile`, `compose.yml` | Native binary distribution |
| Traefik | `compose.yml` labels | No reverse proxy needed |
| CORS (partial) | `main.py` middleware | Simplified for localhost only |
| Sentry | `main.py` integration | Optional - use local logging instead |
| Password recovery | `login.py` routes | Requires email - remove or redesign |
| Adminer | `compose.yml` | No separate DB admin needed |

---

## Part 2: Implementation Plan

### Phase 1: Project Structure Setup

**1.1 Create directory structure:**
```
tauri-fastapi-full-stack-template/
├── frontend/                 # React frontend (enhanced)
├── fastapi/                  # FastAPI backend (new)
├── tauri/                    # Tauri Rust code (existing)
├── scripts/                  # Build and utility scripts
├── Makefile                  # Updated build commands
└── INTEGRATION_PLAN.md       # This document
```

**1.2 Backend structure:**
```
fastapi/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py           # Auth optional, session management
│   │   ├── main.py           # Router setup
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── items.py
│   │       ├── login.py
│   │       ├── users.py
│   │       └── utils.py      # Health check only
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py         # Desktop-adapted settings
│   │   ├── db.py             # SQLite setup
│   │   └── security.py       # JWT + password hashing
│   ├── __init__.py
│   ├── models.py             # SQLModel models
│   ├── crud.py               # CRUD operations
│   └── main.py               # FastAPI app entry
├── alembic/                  # Database migrations
├── pyproject.toml            # Python dependencies
├── build.py                  # PyInstaller build script
└── fastapi-server.spec       # PyInstaller spec file
```

### Phase 2: Backend Adaptation

**2.1 Copy and adapt backend files:**

| Source File | Destination | Changes |
|-------------|-------------|---------|
| `fastapi/app/models.py` | `fastapi/app/models.py` | Remove email-related fields if any |
| `fastapi/app/crud.py` | `fastapi/app/crud.py` | Keep as-is |
| `fastapi/app/core/security.py` | `fastapi/app/core/security.py` | Keep as-is |
| `fastapi/app/core/config.py` | `fastapi/app/core/config.py` | Major changes (see below) |
| `fastapi/app/core/db.py` | `fastapi/app/core/db.py` | SQLite configuration |
| `fastapi/app/api/deps.py` | `fastapi/app/api/deps.py` | Optional auth logic |
| `fastapi/app/api/routes/*.py` | `fastapi/app/api/routes/*.py` | Remove email routes |
| `fastapi/app/main.py` | `fastapi/app/main.py` | Remove Sentry, simplify CORS |

**2.2 New config.py structure:**
```python
class Settings(BaseSettings):
    # App settings
    PROJECT_NAME: str = "Desktop App"
    API_V1_STR: str = "/api/v1"

    # Auth settings (opt-in)
    AUTH_REQUIRED: bool = False
    SECRET_KEY: str = Field(default_factory=generate_secret)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # Database (SQLite)
    DATA_DIR: Path  # Passed from Tauri

    @computed_field
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"sqlite:///{self.DATA_DIR}/app.db"

    # Server settings
    HOST: str = "127.0.0.1"
    PORT: int = 8000
```

**2.3 Database initialization (db.py):**
```python
from sqlalchemy import event
from sqlmodel import create_engine, Session

def create_db_engine(database_url: str):
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine
```

**2.4 Optional auth dependency (deps.py):**
```python
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False  # Don't raise exception if no token
)

def get_current_user(
    session: SessionDep,
    token: Annotated[str | None, Depends(oauth2_scheme_optional)]
) -> User:
    if not settings.AUTH_REQUIRED:
        # Return or create default local user
        return get_or_create_default_user(session)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # ... existing token validation logic
```

### Phase 3: Tauri Sidecar Integration

**3.1 Update Cargo.toml:**
```toml
[dependencies]
tauri = { version = "2", features = ["shell-sidecar"] }
tauri-plugin-shell = "2"
```

**3.2 Update tauri.conf.json:**
```json
{
  "bundle": {
    "externalBin": [
      "binaries/fastapi-server"
    ]
  },
  "plugins": {
    "shell": {
      "sidecar": true,
      "scope": [
        {
          "name": "binaries/fastapi-server",
          "sidecar": true,
          "args": true
        }
      ]
    }
  }
}
```

**3.3 Update capabilities:**
```json
{
  "permissions": [
    "core:default",
    "shell:allow-spawn",
    "shell:allow-kill",
    "opener:default"
  ]
}
```

**3.4 Rust sidecar management (lib.rs):**
```rust
use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use std::sync::Mutex;

struct AppState {
    sidecar: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
}

#[tauri::command]
async fn start_backend(app: tauri::AppHandle) -> Result<(), String> {
    let data_dir = app.path().app_data_dir()
        .map_err(|e| e.to_string())?;

    std::fs::create_dir_all(&data_dir).map_err(|e| e.to_string())?;

    let sidecar = app.shell()
        .sidecar("fastapi-server")
        .map_err(|e| e.to_string())?
        .args(["--data-dir", data_dir.to_str().unwrap()])
        .spawn()
        .map_err(|e| e.to_string())?;

    // Store sidecar handle for cleanup
    let state = app.state::<AppState>();
    *state.sidecar.lock().unwrap() = Some(sidecar);

    // Wait for health check
    wait_for_backend_ready().await?;

    Ok(())
}

async fn wait_for_backend_ready() -> Result<(), String> {
    let client = reqwest::Client::new();
    for _ in 0..30 {  // 30 attempts, 100ms apart = 3s timeout
        if client.get("http://127.0.0.1:8000/api/v1/utils/health-check/")
            .send().await.is_ok() {
            return Ok(());
        }
        tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
    }
    Err("Backend failed to start".to_string())
}
```

### Phase 4: Frontend Migration

**4.1 Add dependencies:**
```json
{
  "dependencies": {
    "@tanstack/react-query": "^5.90",
    "@tanstack/react-router": "^1.157",
    "axios": "^1.13",
    "react-hook-form": "^7.68",
    "zod": "^4.3",
    "@hookform/resolvers": "^5.0"
  },
  "devDependencies": {
    "@hey-api/openapi-ts": "^0.73",
    "tailwindcss": "^4.1",
    "@tailwindcss/vite": "^4.1"
  }
}
```

**4.2 Copy frontend structure:**
- `src/client/` - API client (regenerate after backend changes)
- `src/routes/` - Page components
- `src/components/` - UI components
- `src/hooks/` - Custom hooks
- `src/lib/` - Utilities

**4.3 Configure API client:**
```typescript
// src/client/config.ts
import { OpenAPI } from "./core/OpenAPI"

export function setupApiClient() {
  // In Tauri, always use localhost
  OpenAPI.BASE = "http://127.0.0.1:8000"

  // Token getter for optional auth
  OpenAPI.TOKEN = async () => {
    return localStorage.getItem("access_token") || ""
  }
}
```

**4.4 Add Tauri integration hook:**
```typescript
// src/hooks/useTauri.ts
import { invoke } from "@tauri-apps/api/core"

export function useTauri() {
  const startBackend = async () => {
    await invoke("start_backend")
  }

  const getAppDataDir = async (): Promise<string> => {
    return await invoke("get_app_data_dir")
  }

  return { startBackend, getAppDataDir }
}
```

**4.5 App initialization:**
```typescript
// src/main.tsx
import { setupApiClient } from "./client/config"
import { invoke } from "@tauri-apps/api/core"

async function initApp() {
  // Start backend sidecar
  await invoke("start_backend")

  // Configure API client
  setupApiClient()

  // Render React app
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  )
}

initApp()
```

### Phase 5: PyInstaller Build

**5.1 PyInstaller spec file:**
```python
# fastapi-server.spec
a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.lifespan.on',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='fastapi-server',
    debug=False,
    strip=False,
    upx=True,
    console=True,  # Set to False for production
)
```

**5.2 Build command structure:**
```bash
# fastapi/build.py
cd fastapi
pyinstaller fastapi-server.spec --distpath ../tauri/binaries/
```

**5.3 Platform-specific naming:**
```
tauri/binaries/
├── fastapi-server-x86_64-unknown-linux-gnu      # Linux
├── fastapi-server-x86_64-apple-darwin           # macOS Intel
├── fastapi-server-aarch64-apple-darwin          # macOS ARM
└── fastapi-server-x86_64-pc-windows-msvc.exe    # Windows
```

### Phase 6: Build System Updates

**6.1 Updated Makefile:**
```makefile
.PHONY: setup dev build clean backend-dev frontend-dev build-backend

# Development
setup:
	cd fastapi && uv sync
	cd frontend && bun install
	cargo install tauri-cli

dev: build-backend
	cargo tauri dev

backend-dev:
	cd fastapi && uv run uvicorn app.main:app --reload --port 8000

frontend-dev:
	cd frontend && bun run dev

# Build
build-backend:
	cd fastapi && uv run pyinstaller fastapi-server.spec --distpath ../tauri/binaries/

build: build-backend
	cargo tauri build

# Utilities
generate-client:
	cd fastapi && uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../frontend/openapi.json
	cd frontend && bun run openapi-ts

clean:
	rm -rf tauri/target
	rm -rf tauri/binaries
	rm -rf frontend/dist
	rm -rf fastapi/__pycache__
```

### Phase 7: Testing & Verification

**7.1 Backend tests:**
```bash
cd fastapi
uv run pytest tests/ -v
```

**7.2 Frontend tests:**
```bash
cd frontend
bun run test
```

**7.3 Integration test checklist:**
- [ ] App launches and backend starts
- [ ] Health check endpoint responds
- [ ] Items CRUD works without auth
- [ ] Items CRUD works with auth enabled
- [ ] User registration/login works when auth enabled
- [ ] Data persists across app restarts
- [ ] App closes cleanly (sidecar terminates)

---

## Part 3: Task Breakdown

### Milestone 1: Backend Setup
1. Create `fastapi/` directory structure
2. Copy and adapt models.py
3. Copy and adapt crud.py
4. Adapt config.py for SQLite and desktop
5. Adapt db.py for SQLite with WAL mode
6. Copy security.py (no changes needed)
7. Adapt deps.py for optional auth
8. Adapt routes (remove email-related endpoints)
9. Adapt main.py (remove Sentry, simplify CORS)
10. Create pyproject.toml with dependencies
11. Setup Alembic for SQLite migrations
12. Test backend standalone

### Milestone 2: Tauri Sidecar Integration
13. Add shell plugin to Cargo.toml
14. Update tauri.conf.json for sidecar
15. Update capabilities for shell permissions
16. Implement sidecar spawn in Rust
17. Implement health check polling
18. Implement graceful shutdown
19. Create PyInstaller spec file
20. Test sidecar lifecycle

### Milestone 3: Frontend Migration
21. Add new dependencies (TanStack, Tailwind, etc.)
22. Setup Tailwind CSS
23. Copy and adapt components
24. Copy and adapt routes
25. Copy and adapt hooks
26. Generate API client from OpenAPI
27. Add Tauri-specific hooks
28. Update main.tsx for initialization
29. Test frontend with backend

### Milestone 4: Build & Polish
30. Update Makefile with all commands
31. Test full build pipeline
32. Test on target platforms
33. Document build/dev process

---

## Appendix A: Dependencies

### Backend (pyproject.toml)
```toml
[project]
name = "fastapi-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.114.0",
    "uvicorn[standard]>=0.30.0",
    "sqlmodel>=0.0.21",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.5.0",
    "pyjwt>=2.9.0",
    "pwdlib[argon2,bcrypt]>=0.2.0",
    "alembic>=1.13.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "httpx>=0.27.0",
    "pyinstaller>=6.0.0",
]
```

### Frontend (package.json additions)
```json
{
  "dependencies": {
    "@tanstack/react-query": "^5.90.0",
    "@tanstack/react-router": "^1.157.0",
    "@tauri-apps/api": "^2.0.0",
    "@tauri-apps/plugin-shell": "^2.0.0",
    "axios": "^1.13.0",
    "react-hook-form": "^7.68.0",
    "zod": "^4.3.0",
    "@hookform/resolvers": "^5.0.0",
    "next-themes": "^0.4.0",
    "sonner": "^2.0.0"
  },
  "devDependencies": {
    "@hey-api/openapi-ts": "^0.73.0",
    "tailwindcss": "^4.1.0",
    "@tailwindcss/vite": "^4.1.0"
  }
}
```

---

## Appendix B: Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_REQUIRED` | `false` | Enable authentication requirement |
| `SECRET_KEY` | auto-generated | JWT signing key (generated on first run) |
| `HOST` | `127.0.0.1` | Backend bind address |
| `PORT` | `8000` | Backend port |
| `LOG_LEVEL` | `info` | Logging verbosity |

These can be set via:
1. CLI arguments to the sidecar
2. Config file in app_data_dir
3. Environment variables (mainly for development)

---

## TODO

### Remaining Tasks

#### High Priority
- [ ] **PyInstaller spec file** - Create `fastapi-server.spec` for packaging Python backend
- [ ] **Graceful shutdown** - Implement sidecar termination on app close
- [ ] **Full build test** - Run `make build` and verify desktop app works

#### Medium Priority
- [ ] **Password recovery routes** - Remove or redesign `recover-password.tsx` and `reset-password.tsx` (email removed)
- [ ] **Operation ID cleanup** - Shorten FastAPI operation IDs for cleaner client codegen
- [ ] **Documentation** - Add README with setup and build instructions

#### Low Priority
- [ ] **Multi-platform testing** - Test build on macOS, Windows
- [ ] **Add user settings page** - Enable/disable auth, change port, etc.
- [ ] **Error handling** - Better error messages when backend fails to start
- [ ] **Logging** - File-based logging for sidecar in production

### Completed
- [x] Backend setup with SQLite and optional auth
- [x] Frontend migration with TanStack Router and shadcn/ui
- [x] API client generation (TypeScript + Rust via openapi-generator)
- [x] Makefile with dev/build/clean commands
- [x] Database location defaults to `project_root/.data` in development
