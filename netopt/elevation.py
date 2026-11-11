"""
netopt/elevation.py -- Cross-platform privilege elevation module.

Ensures OmniNet AI Agent Pro always runs with administrator/root privileges.
- Windows: triggers UAC prompt via ShellExecuteW (runas verb)
- Linux/macOS: re-executes with sudo / pkexec
- Frozen PyInstaller EXE: same logic, works identically

Skip elevation by passing --no-elevate on the command line (e.g. MCP stdio mode).
"""

from __future__ import annotations

import ctypes
import os
import platform
import sys


# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

def _is_admin_windows() -> bool:
    """Return True if the current process has Windows admin privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _elevate_windows() -> None:
    """
    Re-launch this process with UAC elevation (runas verb).
    The current (unprivileged) process exits immediately after.
    """
    # When frozen (PyInstaller EXE), sys.executable IS sys.argv[0], so only pass sys.argv[1:]
    raw_args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    args = " ".join(f'"{a}"' for a in raw_args)
    # SW_SHOWNORMAL = 1
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,          # hwnd
        "runas",       # verb -- triggers UAC dialog
        sys.executable,
        args,
        None,          # working directory (keep current)
        1,             # nShowCmd: SW_SHOWNORMAL
    )
    if ret <= 32:
        # User declined UAC or UAC unavailable: continue running without elevation so UI still works
        print(f"[OmniNet] Continuando sin elevación UAC (código {ret}).", flush=True)
        return
    sys.exit(0)


# ---------------------------------------------------------------------------
# POSIX helpers (Linux + macOS)
# ---------------------------------------------------------------------------

def _is_root_posix() -> bool:
    """Return True if the effective UID is 0 (root)."""
    return getattr(os, "geteuid", lambda: -1)() == 0


def _elevate_posix() -> None:
    """
    Re-execute this process under sudo.
    Uses os.execvp so it *replaces* the current process (no zombie left behind).
    """
    sudo_cmd = ["sudo", sys.executable] + sys.argv
    try:
        os.execvp("sudo", sudo_cmd)
    except FileNotFoundError:
        # sudo not available -- try pkexec (GUI polkit on some Linux distros)
        try:
            os.execvp("pkexec", ["pkexec", sys.executable] + sys.argv)
        except FileNotFoundError:
            raise PermissionError(
                "Could not find 'sudo' or 'pkexec'. "
                "Please re-run OmniNet with root privileges manually:\n"
                f"  sudo {' '.join(sys.argv)}"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_elevated() -> bool:
    """
    Return True if the current process already has admin/root privileges.
    Platform-independent.
    """
    plat = platform.system().lower()
    if plat == "windows":
        return _is_admin_windows()
    return _is_root_posix()


def ensure_elevated(skip_flag: str = "--no-elevate") -> None:
    """
    Check privilege level and re-launch with elevation if needed.

    Call this at the very top of main.py (inside the __main__ guard)
    before doing any real work.

    Args:
        skip_flag: CLI argument that bypasses elevation (default --no-elevate).
                   Useful for MCP stdio mode where elevation is undesirable.
    """
    # Honour explicit opt-out
    if skip_flag in sys.argv:
        return

    plat = platform.system().lower()

    if plat == "windows":
        if not _is_admin_windows():
            print(
                "[OmniNet] Privilegios de administrador requeridos. "
                "Lanzando solicitud UAC...",
                flush=True,
            )
            _elevate_windows()
        # Already admin -- nothing to do
    elif plat in ("linux", "darwin"):
        if not _is_root_posix():
            print(
                "[OmniNet] Se requieren privilegios root. "
                "Reejecutando con sudo...",
                flush=True,
            )
            _elevate_posix()
            # _elevate_posix replaces the process; code below never runs
    else:
        # Unknown platform -- warn but continue
        print(
            f"[OmniNet] Plataforma desconocida '{platform.system()}'. "
            "Continuando sin verificar privilegios.",
            flush=True,
        )


def elevation_status_str() -> str:
    """Return a human-readable ASCII string with the current elevation status."""
    plat = platform.system()
    elevated = is_elevated()
    label = "[Admin/root ACTIVO]" if elevated else "[Sin privilegios elevados]"
    return f"{label} | OS: {plat} | Python: {sys.version.split()[0]}"
