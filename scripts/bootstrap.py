"""
OmniNet Universal Bootstrap & Environment Verifier.
Ensures Python runtime availability, checks privileges, and launches the OmniNet agent.
"""

from __future__ import annotations
import sys
import os
import platform
import subprocess
import urllib.request
import zipfile
import shutil


def check_python_environment() -> dict:
    return {
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "executable": sys.executable,
        "is_64bit": sys.maxsize > 2**32
    }


def verify_execution_readiness():
    print("=" * 60)
    print("       OMNINET UNIVERSAL BOOTSTRAP ENVIRONMENT CHECK")
    print("=" * 60)
    env = check_python_environment()
    for k, v in env.items():
        print(f"  {k:<18}: {v}")
    print("-" * 60)

    # Check administrative elevation
    is_admin = False
    if env["platform"] == "Windows":
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
    else:
        is_admin = (os.geteuid() == 0) if hasattr(os, "geteuid") else False

    print(f"  Administrative Rights : {'GRANTED (Full Tuning Available)' if is_admin else 'USER MODE (Simulations & Diagnostics)'}")
    print("=" * 60)
    return is_admin


def run():
    verify_execution_readiness()
    import main
    main.main()


if __name__ == "__main__":
    run()

