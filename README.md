# Tauri + FastAPI Full Stack Template

> A **template** for building desktop applications with Tauri (Rust), FastAPI (Python), and React (TypeScript).

This is a **starter template** designed to be customized for your own application. It provides a complete full-stack desktop app foundation with optional authentication.

## Features

- **Frontend**: React + TypeScript with Vite, TanStack Router, TanStack Query, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI with SQLite, SQLModel, Alembic migrations, Pydantic settings
- **Desktop**: Tauri 2 with sidecar architecture (FastAPI runs as bundled binary)
- **Auth**: Optional - disabled by default for local desktop use
- **Build**: PyInstaller bundles Python backend into single binary, Tauri creates native installers

## Quick Start

```bash
# Install dependencies
make setup

# Run in development mode (uses embedded Python, no pre-built binary needed)
make dev
```

The app opens at http://localhost:1420 with the backend API at http://localhost:1430.

## Development

```bash
# Run full app (Tauri + frontend dev server + separate backend)
make dev

# Run only frontend dev server (if backend is already running)
make dev-frontend

# Run only backend (for debugging)
make fastapi

# Initialize/reset database
make init-db

# Generate API clients from backend OpenAPI schema
make generate-client
```

## Building for Production

```bash
# Build everything (frontend + backend binary + Tauri app)
make build

# Or build step by step:
make build-backend    # PyInstaller: tauri/binaries/fastapi-server-{arch}-{os}
cargo tauri build     # Creates .deb, .rpm, .AppImage (Linux)
```

Output: `tauri/target/release/bundle/`

## Customizing This Template ("Second Dev")

This is a **template** - you'll need to customize it for your application:

### 1. Rename the App

Edit `tauri/tauri.conf.json`:

```json
{
  "productName": "your-app-name",
  "identifier": "com.yourcompany.your-app-name",
  "title": "Your App Name"
}
```

### 2. Update Backend Config

Edit `fastapi/app/core/config.py`:

```python
PROJECT_NAME: str = "Your App Name"
AUTH_REQUIRED: bool = False  # Set to True to enable authentication
```

### 3. Update Frontend

- Edit `frontend/src/routes/_layout.tsx` - change page title, branding
- Replace shadcn/ui components in `frontend/src/components/`
- Add your routes in `frontend/src/routes/`

### 4. Update Database Models

- Edit `fastapi/app/models/` - add your SQLModel models
- Create migration: `cd fastapi && uv run alembic revision --autogenerate -m "description"`
- Run migrations: `uv run alembic upgrade head`

### 5. Update API Routes

- Add routes in `fastapi/app/api/deps/` (per-feature modules)
- Import in `fastapi/app/api/main.py`

### 6. Regenerate API Clients

After changing backend models/routes:

```bash
make generate-client
```

This regenerates TypeScript and Rust clients from the OpenAPI schema.

## Project Structure

```
├── frontend/          # React + TypeScript + Vite
│   ├── src/
│   │   ├── routes/   # TanStack Router file-based routing
│   │   ├── components/
│   │   ├── services/ # API client (auto-generated)
│   │   └── hooks/    # React hooks (useAuth, etc.)
│   └── openapi.json  # OpenAPI schema (auto-generated)
├── fastapi/          # Python FastAPI backend
│   ├── app/
│   │   ├── api/      # API routes
│   │   ├── core/     # Config, DB, logging
│   │   ├── models/   # SQLModel database models
│   │   └── crud/     # Database operations
│   └── alembic/      # Database migrations
├── tauri/            # Rust desktop app
│   ├── src/
│   │   ├── lib.rs    # Main app, sidecar management
│   │   └── config.rs # Rust config from env vars
│   └── binaries/     # Bundled sidecar binary (generated)
└── scripts/          # Utility scripts (generate-client, etc.)
```

## Architecture

### Sidecar Pattern

The FastAPI backend runs as a separate process (sidecar) that Tauri spawns:

- **Development**: Backend runs separately via `uvicorn` (make dev starts both)
- **Production**: Backend is bundled as PyInstaller binary, Tauri spawns it with `DATA_DIR` set to app data directory

### Database Location

- **Dev**: `.data/app.db` (project root)
- **Production (Linux)**: `~/.local/share/com.glp.tauri-fastapi-full-stack-template/app.db`
- **Production (macOS)**: `~/Library/Application Support/com.glp.tauri-fastapi-full-stack-template/app.db`
- **Production (Windows)**: `%APPDATA%\com.glp.tauri-fastapi-full-stack-template\app.db`

### Auth (Optional)

Authentication is **disabled by default**. To enable:

```python
# fastapi/app/core/config.py
AUTH_REQUIRED: bool = True
```

Then the app will require login and use JWT tokens.

## Make Targets

```bash
make setup          # Install all dependencies
make dev            # Run development mode
make dev-frontend   # Frontend only
make fastapi        # Backend only
make init-db        # Initialize database
make generate-client # Generate API clients
make build-backend  # Build PyInstaller binary
make build          # Build production bundles
make clean          # Clean all build artifacts
make help           # Show all targets
```

## Requirements

- **Rust** (via rustup) - Tauri
- **Node.js** + **bun** - Frontend
- **Python 3.11+** + **uv** - Backend
- **System**: Linux, macOS, or Windows

## License

MIT - use this template for anything you want.
