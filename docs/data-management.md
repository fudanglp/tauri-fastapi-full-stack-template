# Data Management

## Overview

This app uses SQLite for local data storage, with the database file stored in the platform-specific app data directory managed by Tauri.

## Directory Locations

| Platform | Path |
|----------|------|
| **Linux** | `~/.local/share/com.glp.tauri-fastapi-full-stack-template/` |
| **macOS** | `~/Library/Application Support/com.glp.tauri-fastapi-full-stack-template/` |
| **Windows** | `C:\Users\<user>\AppData\Roaming\com.glp.tauri-fastapi-full-stack-template\` |

The identifier comes from `tauri.conf.json` → `identifier`.

## Files

```
{app_data_dir}/
└── app.db          # SQLite database (WAL mode)
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Tauri Application                        │
│                                                             │
│  ┌─────────────────┐         ┌─────────────────────────┐   │
│  │   Rust Core     │         │    React Frontend       │   │
│  │                 │         │                         │   │
│  │ • Get app_data  │         │ • HTTP to localhost     │   │
│  │ • Spawn sidecar │         │ • Display data          │   │
│  │ • Pass DATA_DIR │         │                         │   │
│  └────────┬────────┘         └────────────┬────────────┘   │
│           │                               │                 │
│           │ env: DATA_DIR                 │ HTTP :1430      │
│           ▼                               ▼                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              FastAPI Sidecar (Python)                 │  │
│  │                                                       │  │
│  │  • Reads DATA_DIR from environment                    │  │
│  │  • SQLite database at {DATA_DIR}/app.db               │  │
│  │  • WAL mode for concurrent reads                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Environment Variables

The FastAPI backend is configured via environment variables (set by Tauri when spawning the sidecar):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATA_DIR` | Yes | - | Directory for SQLite database |
| `HOST` | No | `127.0.0.1` | Server bind address |
| `PORT` | No | `1430` | Server port |
| `AUTH_REQUIRED` | No | `false` | Enable authentication |
| `DATABASE_NAME` | No | `app.db` | SQLite filename |

## Development vs Production

### Development

Run backend and frontend separately:

```bash
# Terminal 1: FastAPI with hot reload
cd fastapi
DATA_DIR=./data uv run uvicorn app.main:app --reload --port 1430

# Terminal 2: Tauri dev (frontend only)
cargo tauri dev
```

The Rust code detects `debug_assertions` and skips spawning the sidecar, expecting the backend to be running externally.

### Production

Tauri automatically:
1. Gets `app_data_dir()` for the platform
2. Creates the directory if needed
3. Spawns the PyInstaller-bundled sidecar with `DATA_DIR` env var

## SQLite Configuration

The database is configured for desktop app use:

```python
# WAL mode: allows concurrent reads while writing
PRAGMA journal_mode=WAL

# Foreign key enforcement (off by default in SQLite)
PRAGMA foreign_keys=ON

# Wait up to 5 seconds if database is locked
PRAGMA busy_timeout=5000

# Balance of safety and speed
PRAGMA synchronous=NORMAL
```

## Backup & Migration

### Manual Backup

```bash
# Linux
cp ~/.local/share/com.glp.tauri-fastapi-full-stack-template/app.db ~/backup/

# macOS
cp ~/Library/Application\ Support/com.glp.tauri-fastapi-full-stack-template/app.db ~/backup/
```

### Database Reset

Delete the database file to reset (app will recreate on next launch):

```bash
# Linux
rm ~/.local/share/com.glp.tauri-fastapi-full-stack-template/app.db*
```

## Tauri Path API

From frontend JavaScript:

```typescript
import { appDataDir } from '@tauri-apps/api/path';

const dataDir = await appDataDir();
console.log(dataDir); // Platform-specific path
```

From Rust:

```rust
let data_dir = app.path().app_data_dir()?;
```
