"""
Build script to package OmniNet AI Agent Pro into a standalone Windows executable (.exe)
using PyInstaller with System Tray support.
"""

from __future__ import annotations
import os
import subprocess
import sys


def build_executable() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "OmniNet",
        "--add-data",
        f"config{os.pathsep}config",
        "--hidden-import",
        "pystray",
        "--hidden-import",
        "PIL",
        "--hidden-import",
        "uvicorn",
        "main.py",
    ]
    print("Ejecutando:", " ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(build_executable())
