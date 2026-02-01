.PHONY: setup dev build dev-frontend clean

# Install all dependencies
setup:
	cargo install tauri-cli
	cd frontend && bun install

# Run app in development mode
dev:
	cargo tauri dev

# Build for production
build:
	cargo tauri build

# Run frontend dev server only (without Tauri)
dev-frontend:
	cd frontend && bun run dev

# Clean build artifacts
clean:
	cd tauri && cargo clean
	rm -rf frontend/dist
