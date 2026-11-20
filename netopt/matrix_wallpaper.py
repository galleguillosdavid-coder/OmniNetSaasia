"""
Animated Matrix Digital Rain Desktop Wallpaper for Windows & Linux (`netopt/matrix_wallpaper.py`).
Uses Python's built-in tkinter + Win32 WorkerW embedding (Windows) or EWMH desktop window type (Linux)
with zero external dependencies and clean PID-tracked start/stop lifecycle.
"""

from __future__ import annotations
import json
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, Optional

STATE_FILE = os.path.expanduser("~/.netopt_state/matrix_wallpaper.json")

_MATRIX_CHARS = (
    "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ@#$%&*"
)
_HIDDEN_MESSAGES = (
    "e^(i*pi)+1=0",
    "E=mc^2",
    "i*hbar*dpsi/dt=H*psi",
    "S=k*ln(W)",
    "sum(1/n^2)=pi^2/6",
    "nabla x E = -dB/dt",
    "def zero_netloss(): return True",
    "O(log n)",
    "RFC9330::L4S",
    "AI::HANDSHAKE[OK]",
    "HERMES->OMNINET::SYNC",
    "AGENT::VERIFY_TRUTH",
    "MESH::TRUST_OK",
)


def _is_pid_alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == 259  # STILL_ACTIVE
                return True
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _attach_to_windows_desktop(hwnd: int) -> bool:
    """Embeds a window behind Windows 10/11 desktop icons via Progman -> WorkerW."""
    if os.name != "nt" or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowW.restype = wintypes.HWND
        user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowExW.restype = wintypes.HWND
        user32.SendMessageTimeoutW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
            wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD),
        ]
        user32.SendMessageTimeoutW.restype = wintypes.LPARAM
        user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
        user32.SetParent.restype = wintypes.HWND

        progman = user32.FindWindowW("Progman", None)
        if not progman:
            return False

        result = wintypes.DWORD(0)
        user32.SendMessageTimeoutW(progman, 0x052C, 0xD, 0x1, 0, 1000, ctypes.byref(result))

        workerw_target = wintypes.HWND(0)
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _enum_cb(top_hwnd, _lparam):
            shell_view = user32.FindWindowExW(top_hwnd, None, "SHELLDLL_DefView", None)
            if shell_view:
                worker = user32.FindWindowExW(None, top_hwnd, "WorkerW", None)
                if not worker:
                    worker = user32.FindWindowExW(progman, None, "WorkerW", None)
                if worker:
                    workerw_target.value = worker
            return True

        cb = WNDENUMPROC(_enum_cb)
        user32.EnumWindows(cb, 0)
        if not workerw_target.value:
            user32.EnumChildWindows(progman, cb, 0)
        if workerw_target.value:
            user32.SetParent(hwnd, workerw_target.value)
            return True
    except Exception:
        return False
    return False


def run_matrix_desktop_loop(fps_ms: int = 45, font_size: int = 16) -> None:
    """Runs the fullscreen Matrix digital rain animation on the desktop layer."""
    import tkinter as tk

    root = tk.Tk()
    root.title("OmniNet Matrix Desktop")
    root.configure(bg="#000000")
    root.overrideredirect(True)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{sw}x{sh}+0+0")

    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        root.update_idletasks()
        inner_hwnd = root.winfo_id()
        outer_hwnd = ctypes.windll.user32.GetParent(inner_hwnd) or inner_hwnd
        # Make window click-through, non-activating, and pinned to bottom (works on Win10 & Win11 24H2/25H2)
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_NOACTIVATE = 0x08000000
        HWND_BOTTOM = wintypes.HWND(1)
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOACTIVATE = 0x0010
        u32 = ctypes.windll.user32
        ex = u32.GetWindowLongW(outer_hwnd, GWL_EXSTYLE)
        u32.SetWindowLongW(outer_hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        u32.SetWindowPos(outer_hwnd, HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    else:
        try:
            root.wm_attributes("-type", "desktop")
        except Exception:
            root.lower()

    canvas = tk.Canvas(root, width=sw, height=sh, bg="#000000", highlightthickness=0, bd=0)
    canvas.pack(fill="both", expand=True)

    cols = max(10, sw // font_size)
    rows = max(10, sh // font_size)
    drops = [float(random.randint(-rows, 0)) for _ in range(cols)]
    speeds = [random.uniform(0.45, 1.8) for _ in range(cols)]
    col_msgs: Dict[int, tuple] = {}
    trail_len = 16
    tick_counter = [0]

    def _in_silhouette(nx: float, ny: float, scene: int) -> bool:
        if scene == 0:  # Disappearing city skyline
            if ny < 0.34 or ny > 0.96:
                return False
            b = int(nx * 18)
            h = 0.35 + ((b * 37 + 11) % 10) * 0.055
            return ny >= (1.0 - h)
        if scene == 1:  # Silhouette of a woman
            dx, dy = (nx - 0.5) * 1.4, ny - 0.46
            head = ((dx * dx) / (0.055 ** 2) + ((dy + 0.20) ** 2) / (0.085 ** 2)) < 1.0
            torso = abs(dx) < (0.115 - abs(dy - 0.12) * 0.32) and -0.04 <= dy < 0.24
            skirt = abs(dx) < (0.08 + (dy - 0.22) * 0.45) and 0.22 <= dy < 0.48
            return head or torso or skirt
        if ny < 0.38:  # Cyber street perspective
            return False
        p = (ny - 0.38) / 0.62
        half_w = 0.03 + p * 0.44
        return abs(abs(nx - 0.5) - half_w) < 0.025

    def _tick():
        tick_counter[0] += 1
        scene = (tick_counter[0] // 220) % 3
        phase = (tick_counter[0] % 220) / 220.0
        show_ghost = 0.12 < phase < 0.88
        canvas.delete("all")
        for col_idx in range(cols):
            head_row = int(drops[col_idx])
            x = col_idx * font_size + font_size // 2
            nx = x / max(1, sw)
            if col_idx not in col_msgs and random.random() > 0.992:
                col_msgs[col_idx] = (random.choice(_HIDDEN_MESSAGES), 0)
            for offset in range(trail_len):
                r = head_row - offset
                if 0 <= r < rows:
                    y = r * font_size + font_size // 2
                    ny = y / max(1, sh)
                    if offset == 0 and col_idx in col_msgs:
                        msg_txt, msg_pos = col_msgs[col_idx]
                        ch = msg_txt[msg_pos]
                        if msg_pos + 1 >= len(msg_txt):
                            del col_msgs[col_idx]
                        else:
                            col_msgs[col_idx] = (msg_txt, msg_pos + 1)
                        color = "#a7f3d0"
                    elif show_ghost and _in_silhouette(nx, ny, scene):
                        ch = random.choice(_MATRIX_CHARS)
                        color = "#bbf7d0" if offset < 5 else "#4ade80"
                    else:
                        ch = random.choice(_MATRIX_CHARS)
                        if offset == 0:
                            color = "#d8ffd8"
                        elif offset < 4:
                            color = "#00ff41"
                        elif offset < 9:
                            color = "#00b32c"
                        else:
                            color = "#005514"
                    canvas.create_text(x, y, text=ch, fill=color, font=("Consolas", font_size - 2, "bold"))
            drops[col_idx] += speeds[col_idx]
            if drops[col_idx] - trail_len > rows and random.random() > 0.92:
                drops[col_idx] = float(random.randint(-12, 0))
                speeds[col_idx] = random.uniform(0.45, 1.8)
        root.after(fps_ms, _tick)

    root.after(10, _tick)
    root.mainloop()


class MatrixWallpaperManager:
    """Manages starting, stopping, and querying the Matrix animated desktop wallpaper."""

    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = os.path.abspath(state_file)

    def _load_state(self) -> Dict[str, Any]:
        if not os.path.exists(self.state_file):
            return {"running": False, "pid": None}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {"running": False, "pid": None}
        except Exception:
            return {"running": False, "pid": None}

    def _save_state(self, state: Dict[str, Any]) -> None:
        d = os.path.dirname(self.state_file) or "."
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".mx_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            os.replace(tmp, self.state_file)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def status(self) -> Dict[str, Any]:
        st = self._load_state()
        pid = st.get("pid")
        alive = _is_pid_alive(pid) if pid else False
        return {
            "running": alive,
            "pid": pid if alive else None,
            "platform": "windows" if os.name == "nt" else "linux",
            "mode": "workerw_desktop" if os.name == "nt" else "ewmh_desktop",
        }

    def start(self, execute: bool = False) -> Dict[str, Any]:
        cur = self.status()
        if execute is not True:
            return {
                "success": True,
                "simulated": True,
                "action": "start_matrix_wallpaper",
                "platform": cur["platform"],
                "mode": cur["mode"],
            }
        if cur["running"]:
            return {"success": True, "already_running": True, **cur}

        cmd = [sys.executable, "-m", "netopt.matrix_wallpaper", "--run"]
        kwargs: Dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **kwargs)
        state = {"running": True, "pid": proc.pid, "started_at": time.time(), "mode": cur["mode"]}
        self._save_state(state)
        return {"success": True, "simulated": False, "running": True, "pid": proc.pid, "platform": cur["platform"], "mode": cur["mode"]}

    def stop(self, execute: bool = False) -> Dict[str, Any]:
        cur = self.status()
        if execute is not True:
            return {"success": True, "simulated": True, "action": "stop_matrix_wallpaper", **cur}
        pid = cur.get("pid")
        if pid:
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=5)
                else:
                    os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        self._save_state({"running": False, "pid": None, "stopped_at": time.time()})
        return {"success": True, "simulated": False, "running": False, "pid": None, "platform": cur["platform"]}


if __name__ == "__main__":
    if "--run" in sys.argv:
        run_matrix_desktop_loop()
