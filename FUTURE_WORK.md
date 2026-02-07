# Future Work

> This document tracks potential improvements and features for the Tauri + FastAPI Full Stack Template.
>
> **Status**: Integration is complete. The template is functional with:
> - FastAPI backend with SQLite and optional auth
> - React frontend with TanStack Router and shadcn/ui
> - Tauri desktop app with PyInstaller sidecar packaging
> - OpenAPI codegen for TypeScript + Rust

## Completed

- [x] Backend setup with SQLite and optional auth
- [x] Frontend migration with TanStack Router and shadcn/ui
- [x] API client generation (TypeScript + Rust via openapi-generator)
- [x] Makefile with dev/build/clean commands
- [x] Database location defaults to `project_root/.data` in development
- [x] PyInstaller spec file for packaging Python backend
- [x] Graceful shutdown with SIGTERM/SIGKILL handling
- [x] Full build pipeline (AppImage, .deb, .rpm tested on Linux)
- [x] README with setup and customization instructions

---

## Remaining Tasks

### Medium Priority

| Task | Description |
|------|-------------|
| **Password recovery routes** | Remove or redesign `recover-password.tsx` and `reset-password.tsx` (email system was removed) |
| **Operation ID cleanup** | Shorten FastAPI operation IDs for cleaner client codegen (currently auto-generated long names) |
| **Route cleanup** | Remove unused password recovery routes from backend |

### Low Priority

| Task | Description |
|------|-------------|
| **Multi-platform testing** | Test build on macOS and Windows |
| **User settings page** | UI for enabling/disabling auth, changing port, etc. |
| **Better error handling** | Show user-friendly error messages when backend fails to start |
| **File-based logging** | Write sidecar logs to file in production (currently console only) |
| **Settings persistence** | Allow users to configure and save preferences |
| **Auto-update** | Integrate Tauri's updater plugin |

---

## Reference Architecture

For reference, the original integration plan is preserved below:

### Sidecar Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      Tauri Application                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    Rust Core (Tauri)                     │ │
│  │                                                         │ │
│  │  • Spawn FastAPI sidecar on app start                   │ │
│  │  • Monitor sidecar health (port 1430)                   │ │
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
│  │  • Runs on 127.0.0.1:1430                              │ │
│  │  • SQLite database in app_data_dir                      │ │
│  │  • Receives config via env vars (DATA_DIR, HOST, PORT)  │ │
│  │  • Health endpoint: /api/v1/health                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                            ▲                                  │
│                    HTTP requests                              │
│                            │                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                  React Frontend (Webview)               │ │
│  │                                                         │ │
│  │  • TanStack Router for routing                          │ │
│  │  • TanStack Query for server state                     │ │
│  │  • shadcn/ui components                                │ │
│  │  • API calls to http://127.0.0.1:1430                  │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### Development vs Production

| Aspect | Development | Production |
|--------|-------------|------------|
| **Backend** | Runs via `uvicorn --reload` (separate terminal) | Bundled PyInstaller binary spawned by Tauri |
| **Frontend** | Vite dev server (HMR) | Built static files |
| **Database** | `.data/app.db` (project root) | `~/.local/share/com.example.tauri-fastapi-full-stack-template/app.db` |
| **Auth** | Optional (AUTH_REQUIRED=false) | Optional (AUTH_REQUIRED=false) |

### Data Model Flow

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  FastAPI Models │  →   │  OpenAPI Schema │  →   │  TypeScript &   │
│  (SQLModel)     │      │  (openapi.json) │      │  Rust Types     │
└─────────────────┘      └─────────────────┘      │  (auto-gen)     │
                                                   └─────────────────┘
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_REQUIRED` | `false` | Enable authentication requirement |
| `SECRET_KEY` | auto-generated | JWT signing key |
| `HOST` | `127.0.0.1` | Backend bind address |
| `PORT` | `1430` | Backend port |
| `DATA_DIR` | `.data` (dev) / app_data_dir (prod) | Database location |
