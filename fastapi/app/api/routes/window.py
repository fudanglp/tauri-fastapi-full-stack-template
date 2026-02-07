import os
from typing import Annotated

import httpx
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter()


class WindowStateRequest(BaseModel):
    """Request model for window state control."""

    action: str  # "maximize", "restore", "toggle"


def get_socket_path() -> str:
    """Get the Unix socket path for Tauri communication."""
    # Use XDG_RUNTIME_DIR or fallback to temp directory
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMP", "/tmp")
    return os.path.join(runtime_dir, "tauri-fastapi.sock")


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
        import socket as sock

        # Create Unix socket
        sock_obj = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        sock_obj.settimeout(1.0)  # 1 second timeout

        try:
            # Connect to socket
            sock_obj.connect(socket_path)

            # Create HTTP POST request
            window_data = {"action": request.action}

            # Convert to JSON bytes
            import json

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
        import socket as sock

        sock_obj = sock.socket(sock.AF_UNIX, sock.SOCK_STREAM)
        sock_obj.settimeout(0.5)
        sock_obj.connect(socket_path)
        sock_obj.close()

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
