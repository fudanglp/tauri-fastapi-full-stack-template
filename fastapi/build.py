#!/usr/bin/env python
"""Build script for PyInstaller."""

import os
import shutil
import subprocess
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
FASTAPI_DIR = PROJECT_ROOT / "fastapi"


def get_target_triple() -> tuple[str, str, str]:
    """Get the Rust target triple for the current platform.

    Returns:
        (arch, vendor, os) tuple like ("x86_64", "unknown", "linux-gnu")
    """
    import platform

    system = platform.system().lower()
    machine = platform.machine().lower()

    # Map to Rust naming conventions
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "aarch64": "aarch64",
        "arm64": "aarch64",
    }
    arch = arch_map.get(machine, machine)

    if system == "linux":
        vendor = "unknown"
        os_suffix = "linux-gnu"
    elif system == "darwin":
        vendor = "apple"
        os_suffix = "darwin"
    elif system == "windows":
        vendor = "pc"
        os_suffix = "windows-gnu"
    else:
        vendor = "unknown"
        os_suffix = system

    return arch, vendor, os_suffix


def main():
    """Build the FastAPI server binary with PyInstaller."""
    arch, vendor, os_suffix = get_target_triple()
    target_triple = f"{arch}-{vendor}-{os_suffix}"

    # PyInstaller directories
    dist_path = PROJECT_ROOT / "tauri" / "binaries"

    print(f"Building FastAPI server binary...")
    print(f"  Target triple: {target_triple}")
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
    if os_suffix.endswith("windows"):
        exe_name += ".exe"
        source = dist_path / exe_name

    target_name = f"fastapi-server-{target_triple}"
    if os_suffix.endswith("windows"):
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
