.PHONY: setup dev build dev-frontend fastapi clean

# Install all dependencies
setup:
	cargo install tauri-cli
	cd frontend && bun install
	cd fastapi && uv sync

# Run app in development mode
dev:
	cargo tauri dev

# Build for production
build:
	cargo tauri build

# Run frontend dev server only (without Tauri)
dev-frontend:
	cd frontend && bun run dev

# Run FastAPI backend (for development)
fastapi:
	cd fastapi && DATA_DIR=../.data uv run uvicorn app.main:app --reload --port 1430

# Clean build artifacts
clean:
	cd tauri && cargo clean
	rm -rf frontend/dist
