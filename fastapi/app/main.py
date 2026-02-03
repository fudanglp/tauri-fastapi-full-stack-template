from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.prestart import main as prestart

# Setup loguru logging (intercepts standard logging)
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Application lifespan handler - runs on startup and shutdown."""
    # Startup: Run migrations and initialize data
    prestart()
    yield
    # Shutdown: Nothing to clean up for now


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS middleware for local development
# In production Tauri app, requests come from tauri://localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",  # Vite dev server
        "http://127.0.0.1:1420",
        "tauri://localhost",      # Tauri webview
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Root endpoint - basic info."""
    return {
        "name": settings.PROJECT_NAME,
        "version": "0.1.0",
        "auth_required": settings.AUTH_REQUIRED,
    }


@app.get(f"{settings.API_V1_STR}/health")
def health_check():
    """Health check endpoint for sidecar readiness."""
    return {"status": "healthy"}


# Include API routes
from app.api.main import api_router

app.include_router(api_router, prefix=settings.API_V1_STR)
