# =============================================================================
# Makefile for Tauri FastAPI Full Stack Template
# =============================================================================

.PHONY: setup dev build dev-frontend fastapi init-db clean generate-client build-backend

# Project root directory
PROJECT_ROOT := $(shell pwd)

# =============================================================================
# Setup
# =============================================================================

##@ Setup 📦

# Install all dependencies (Rust, Frontend, Backend)
setup:
	@echo "==> 📦 Installing dependencies..."
	@echo "  - 🔧 Installing Tauri CLI..."
	cargo install tauri-cli
	@echo "  - ⚛️  Installing frontend dependencies (bun)..."
	cd frontend && bun install
	@echo "  - 🐍 Installing backend dependencies (uv)..."
	cd fastapi && uv sync
	@echo "==> ✅ Setup complete!"

# =============================================================================
# Development
# =============================================================================

##@ Development 🚀

# Run the full app in development mode (Tauri + Frontend dev server)
# Uses embedded Python for backend, no pre-built sidecar binary needed
dev:
	@echo "==> 🚀 Starting Tauri development mode..."
	TAURI_CONFIG='{"bundle":{"externalBin":[]}}' cargo tauri dev

# Run only the frontend dev server (useful when backend is already running)
dev-frontend:
	@echo "==> ⚛️  Starting frontend dev server on http://localhost:1420..."
	cd frontend && bun run dev

# Run only the FastAPI backend (for development/debugging)
fastapi:
	@echo "==> 🐍 Starting FastAPI backend on http://localhost:1430..."
	cd fastapi && DATA_DIR=$(PROJECT_ROOT)/.data uv run uvicorn app.main:app --reload --port 1430

# =============================================================================
# Code Generation
# =============================================================================

##@ Code Generation 🔮

# Generate API clients (TypeScript + Rust) from FastAPI OpenAPI schema
# This reads the backend models and generates typed client code
generate-client:
	@./scripts/generate-client.sh

# =============================================================================
# Database
# =============================================================================

##@ Database 🗄️

# Initialize database (run migrations + create default user)
init-db:
	@echo "==> 🗄️  Initializing database..."
	cd fastapi && DATA_DIR=$(PROJECT_ROOT)/.data uv run python -m app.prestart
	@echo "==> ✅ Database initialized!"

# =============================================================================
# Build
# =============================================================================

##@ Build 📦

# Build the FastAPI sidecar binary (PyInstaller)
build-backend:
	@echo "==> 🔨 Building FastAPI sidecar binary..."
	cd fastapi && uv run --with build build.py

# Build the desktop application for production
# This will create platform-specific installers in tauri/target/release/bundle/
build: build-backend
	@echo "==> 📦 Building Tauri desktop bundle..."
	cargo tauri build
	@echo "==> ✅ Build complete! Check tauri/target/release/bundle/ for output."

# =============================================================================
# Maintenance
# =============================================================================

##@ Maintenance 🧹

# Clean all build artifacts and local database
clean:
	@echo "==> 🧹 Cleaning build artifacts..."
	@echo "  - 🔨 Cleaning Rust cargo builds..."
	cd tauri && cargo clean 2>/dev/null || true
	@echo "  - ⚛️  Cleaning frontend dist and node_modules..."
	rm -rf frontend/dist frontend/node_modules
	@echo "  - 🐍 Cleaning Python venv, data, and PyInstaller build..."
	rm -rf fastapi/.venv fastapi/.data fastapi/build
	@echo "  - 🔧 Cleaning Tauri binaries..."
	rm -rf tauri/binaries/fastapi-server*
	@echo "  - 🗄️  Cleaning local databases..."
	rm -rf .data/*.db* .data/*.db-wal .data/*.db-shm
	@echo "  - 📄 Cleaning generated openapi.json..."
	rm -f frontend/openapi.json openapi.json
	@echo "==> ✅ Clean complete!"

# =============================================================================
# Help
# =============================================================================

##@ Help ❓

# Display this help message
help:
	@echo ""
	@echo "  🦀 Tauri FastAPI Full Stack Template"
	@echo ""
	@echo "  Usage: make [target]"
	@echo ""
	@echo "  Setup 📦"
	@echo "    setup              Install all dependencies"
	@echo ""
	@echo "  Development 🚀"
	@echo "    dev                Run Tauri development mode"
	@echo "    dev-frontend       Run frontend dev server only"
	@echo "    fastapi            Run FastAPI backend only"
	@echo ""
	@echo "  Code Generation 🔮"
	@echo "    generate-client    Generate TypeScript + Rust API clients"
	@echo ""
	@echo "  Database 🗄️"
	@echo "    init-db            Initialize database"
	@echo ""
	@echo "  Build 📦"
	@echo "    build              Build production bundle"
	@echo ""
	@echo "  Maintenance 🧹"
	@echo "    clean              Clean build artifacts"
	@echo ""
