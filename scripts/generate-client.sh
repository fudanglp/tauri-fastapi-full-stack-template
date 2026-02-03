#!/usr/bin/env bash

set -e

# Generate OpenAPI schema from FastAPI app
cd fastapi
uv run python -c "import app.main; import json; print(json.dumps(app.main.app.openapi()))" > ../openapi.json
cd ..
mv openapi.json frontend/

# Generate TypeScript client from OpenAPI schema
cd frontend
bun run generate-client
cd ..

# Format generated files
cd frontend
bun run lint
cd ..

echo "Client generated successfully"
