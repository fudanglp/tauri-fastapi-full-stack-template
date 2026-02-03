#!/usr/bin/env python
"""Build script for PyInstaller."""

import os
import shutil
import subprocess
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FASTAPI_DIR = PROJECT_ROOT / "fastapi"


def main():
    """Build the FastAPI server binary with PyInstaller."""
    # Determine output directory based on platform
    import platform
    system = platform.system().lower()
    machine = platform.machine().lower()

    # PyInstaller directories
    dist_path = PROJECT_ROOT / "tauri" / "binaries"

    print(f"Building FastAPI server binary...")
    print(f"  System: {system}")
    print(f"  Machine: {machine}")
    print(f"  Output: {dist_path}")

    # Ensure output directory exists
    dist_path.mkdir(parents=True, exist_ok=True)

    # Build with PyInstaller (run from fastapi directory for relative paths)
    result = subprocess.run(
        [
            "uv",
            "run",
            "pyinstaller",
            "specs/fastapi-server.spec",
            "--distpath",
            str(dist_path),
            "--workpath",
            str(FASTAPI_DIR / "build"),
            "--noconfirm",
        ],
        cwd=FASTAPI_DIR,
        check=False,
    )

    if result.returncode != 0:
        print("Build failed!")
        sys.exit(1)

    # PyInstaller with onefile creates the executable directly in dist_path
    # The binary is at: dist_path/fastapi-server
    exe_name = "fastapi-server"
    source = dist_path / exe_name
    if system == "windows":
        exe_name += ".exe"
        source = dist_path / exe_name

    target_name = f"fastapi-server-{machine}-{system}"
    if system == "windows":
        target_name += ".exe"

    target = dist_path / target_name

    if source.exists():
        # Rename to platform-specific name
        source.rename(target)
        print(f"✅ Build complete: {target}")
    else:
        print(f"❌ Build failed: executable not found at {source}")
        sys.exit(1)


if __name__ == "__main__":
    main()
