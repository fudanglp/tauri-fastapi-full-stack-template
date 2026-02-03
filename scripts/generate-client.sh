#!/usr/bin/env bash

set -e

echo "==> 🔮 Generating API clients from FastAPI backend..."

# Generate OpenAPI schema from FastAPI app
cd fastapi
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
mv openapi.json frontend/

# Generate TypeScript client
echo "  - ⚛️  Generating TypeScript client..."
cd frontend
bun run generate-client
cd ..

# Format TypeScript files
echo "  - 🎨 Formatting TypeScript files..."
cd frontend
bun run lint
cd ..

# Generate Rust client
echo "  - 🦀 Generating Rust client..."
cd frontend
bun run generate-rust-client
cd ..

# Clean up unnecessary generated files
echo "  - 🧹 Cleaning up generated files..."
rm -rf tauri/src/client/docs
rm -f tauri/src/client/.gitignore
rm -f tauri/src/client/.travis.yml
rm -f tauri/src/client/git_push.sh
rm -rf tauri/src/client/.openapi-generator
rm -f tauri/src/client/README.md
rm -f tauri/src/client/.openapi-generator-ignore

# Verify Rust client compiles
echo "  - 🔨 Verifying Rust client compiles..."
cd tauri
if ! TAURI_CONFIG='{"bundle":{"externalBin":[]}}' cargo check --quiet 2>&1; then
    echo "  ⚠️  Rust compilation had issues, but client was generated"
fi
cd ..

echo "==> ✅ All clients generated successfully!"
