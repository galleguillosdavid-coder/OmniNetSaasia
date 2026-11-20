"""
System Tray desktop wrapper for OmniNet AI Agent Pro (`netopt/tray.py`).
Provides a lightweight system tray icon with quick actions to open the Dashboard,
check status, or exit cleanly without keeping a console window open.
"""

from __future__ import annotations
import os
import threading
import webbrowser
from typing import Optional, Callable


def create_tray_icon_image(size: int = 64):
    """Generates a clean OmniNet emblem icon in memory using Pillow."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (11, 17, 32, 255))
    draw = ImageDraw.Draw(img)
    pad = max(4, size // 10)
    draw.ellipse((pad, pad, size - pad, size - pad), fill=(37, 99, 235, 255), outline=(96, 165, 250, 255), width=3)
    inner = size // 4
    draw.ellipse((inner, inner, size - inner, size - inner), outline=(248, 250, 252, 230), width=2)
    center = size // 2
    r = max(3, size // 12)
    draw.ellipse((center - r, center - r, center + r, center + r), fill=(16, 185, 129, 255))
    return img


def run_tray_app(
    port: int = 8877,
    server_starter: Optional[Callable[[int, bool], None]] = None,
    live_autorepair: bool = False,
) -> None:
    """Starts the OmniNet local server in background and attaches a System Tray icon."""
    import pystray

    if live_autorepair:
        os.environ["OMNINET_ALLOW_LIVE_AUTOREPAIR"] = "1"

    url = f"http://127.0.0.1:{port}"

    if server_starter is not None:
        srv_thread = threading.Thread(target=server_starter, args=(port, False), daemon=True)
        srv_thread.start()

    def on_open_dashboard(icon, item):
        webbrowser.open(url)

    def on_run_quick_check(icon, item):
        try:
            from .telemetry import run_real_device_empirical_probes
            probe = run_real_device_empirical_probes()
            icon.notify(
                f"Ping {probe.get('ping_avg_ms')} ms | Bufferbloat {probe.get('bufferbloat_grade')} | Loss {probe.get('packet_loss_pct')}%",
                "OmniNet Estado Rápido",
            )
        except Exception as exc:
            icon.notify(f"Error al verificar red: {exc}", "OmniNet")

    def on_exit(icon, item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Abrir Dashboard OmniNet", on_open_dashboard, default=True),
        pystray.MenuItem("Diagnóstico Rápido", on_run_quick_check),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Salir", on_exit),
    )

    icon = pystray.Icon(
        "omninet",
        create_tray_icon_image(),
        f"OmniNet AI Agent Pro ({url})",
        menu,
    )
    webbrowser.open(url)
    icon.run()
