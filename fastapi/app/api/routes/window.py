import json
import os
import socket
import sys
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class WindowStateRequest(BaseModel):
    """Request model for window state control."""

    action: str  # "maximize", "restore", "toggle"


IS_WINDOWS = sys.platform == "win32"


def get_socket_path() -> str:
    """Get the IPC endpoint file for Tauri communication.

    Linux/macOS: the Unix socket itself.
    Windows: a file holding the loopback TCP port the Tauri server bound
    (AF_UNIX is not available there). Must match tauri/src/socket_server.rs.
    """
    runtime_dir = (
        os.environ.get("XDG_RUNTIME_DIR")
        or os.environ.get("TMP")
        or os.environ.get("TEMP")
        or "/tmp"
    )
    name = "tauri-fastapi.port" if IS_WINDOWS else "tauri-fastapi.sock"
    return os.path.join(runtime_dir, name)


def _connect(endpoint: str, timeout: float) -> socket.socket:
    """Open a stream connection to the Tauri IPC server."""
    if IS_WINDOWS:
        with open(endpoint, encoding="utf-8") as f:
            port = int(f.read().strip())
        return socket.create_connection(("127.0.0.1", port), timeout=timeout)

    sock_obj = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock_obj.settimeout(timeout)
    try:
        sock_obj.connect(endpoint)
    except BaseException:
        sock_obj.close()
        raise
    return sock_obj


@router.post("/window", status_code=status.HTTP_200_OK)
async def toggle_window_state(
    request: Annotated[WindowStateRequest, "Window state request payload"],
) -> dict[str, str]:
    """
    Toggle window maximize/restore state via Unix socket to Tauri.

    This endpoint communicates with the Rust backend through a Unix socket
    to control the window state (maximize/restore).
    """
    socket_path = get_socket_path()

    # Check if socket file exists
    if not os.path.exists(socket_path):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Tauri socket not found at {socket_path}. Is the Tauri app running?",
        )

    try:
        sock_obj = _connect(socket_path, timeout=1.0)

        try:
            # Create HTTP POST request
            window_data = {"action": request.action}

            # Convert to JSON bytes
            body_bytes = json.dumps(window_data).encode()

            # Build HTTP request
            http_request = (
                f"POST /window HTTP/1.1\r\n"
                f"Host: localhost\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                f"\r\n".encode()
            )

            # Send request
            sock_obj.sendall(http_request + body_bytes)

            # Read response
            response = sock_obj.recv(4096).decode()

            # Check if we got a successful response
            if "200 OK" in response:
                return {"status": "success", "message": "Window state changed"}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Unexpected response: {response}",
                )

        finally:
            sock_obj.close()

    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Tauri socket not found at {socket_path}",
        )
    except ConnectionRefusedError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connection refused. Is the Tauri socket server running?",
        )
    except TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Request timed out",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change window state: {str(e)}",
        )


@router.get("/health")
async def window_health_check() -> dict[str, str]:
    """
    Check if the Tauri window socket server is available.
    """
    socket_path = get_socket_path()

    if not os.path.exists(socket_path):
        return {
            "status": "unavailable",
            "socket_path": socket_path,
            "message": "Socket file not found",
        }

    try:
        _connect(socket_path, timeout=0.5).close()

        return {
            "status": "available",
            "socket_path": socket_path,
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "socket_path": socket_path,
            "message": str(e),
        }
