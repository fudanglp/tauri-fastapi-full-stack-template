.PHONY: setup dev build dev-frontend fastapi init-db clean

# Project root directory
PROJECT_ROOT := $(shell pwd)

# Install all dependencies
setup:
	cargo install tauri-cli
	cd frontend && bun install
	cd fastapi && uv sync

# Run app in development mode (no sidecar binary needed)
dev:
	TAURI_CONFIG='{"bundle":{"externalBin":[]}}' cargo tauri dev

# Build for production
build:
	cargo tauri build

# Run frontend dev server only (without Tauri)
dev-frontend:
	cd frontend && bun run dev

# Run FastAPI backend (for development)
fastapi:
	cd fastapi && DATA_DIR=$(PROJECT_ROOT)/.data uv run uvicorn app.main:app --reload --port 1430

# Initialize database (run migrations + seed data)
init-db:
	cd fastapi && DATA_DIR=$(PROJECT_ROOT)/.data uv run python -m app.prestart

# Clean build artifacts
clean:
	cd tauri && cargo clean
	rm -rf frontend/dist
	rm -rf .data/*.db*
