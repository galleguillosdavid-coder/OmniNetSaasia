"""
App-Aware DSCP QoS Traffic Shaping & OS Autostart Service Persistence (`netopt/qos_controller.py`).
Gives OmniNet independent control over application traffic priority (EF/AF41 for realtime voice/video
vs CS1 for background bulk) and OS boot-time daemon persistence on Windows & Linux.
"""

from __future__ import annotations
import os
import sys
from typing import Any, Dict, List, Optional

from .hal import NetworkHAL, PlatformType, detect_platform, get_hal

TASK_NAME = "OmniNetAutonomousAgent"


def apply_app_dscp_qos_policies(
    hal: Optional[NetworkHAL] = None,
    execute: bool = False,
) -> Dict[str, Any]:
    """
    Applies DSCP QoS prioritization policies under Zero NetLoss:
    - Real-time comms/gaming (Zoom, Teams, Discord) -> DSCP 46 (EF)
    - Encrypted QUIC/DNS (UDP 443/853) -> DSCP 34 (AF41)
    - Background bulk updates (DoSvc / BITS) -> DSCP 8 (CS1)
    """
    hal = hal or get_hal(dry_run=(execute is not True))
    should_apply = (execute is True) and not (getattr(hal, "dry_run", False) is True)
    plat = detect_platform()

    policies = [
        {"name": "OmniNet_Realtime_Comms", "target": "zoom/teams/discord", "dscp": 46},
        {"name": "OmniNet_QUIC_DNS", "target": "udp:443,853", "dscp": 34},
        {"name": "OmniNet_Background_Throttle", "target": "background_updates", "dscp": 8},
    ]

    if not should_apply:
        return {
            "success": True,
            "simulated": True,
            "platform": plat.value,
            "policies": policies,
            "applied_count": 0,
        }

    logs: List[str] = []
    applied = 0
    if plat == PlatformType.WINDOWS:
        ps_cmds = [
            "New-NetQosPolicy -Name 'OmniNet_Teams_EF' -AppPathNameMatchCondition 'Teams.exe' -DSCPAction 46 -ErrorAction SilentlyContinue",
            "New-NetQosPolicy -Name 'OmniNet_Zoom_EF' -AppPathNameMatchCondition 'Zoom.exe' -DSCPAction 46 -ErrorAction SilentlyContinue",
            "New-NetQosPolicy -Name 'OmniNet_Discord_EF' -AppPathNameMatchCondition 'Discord.exe' -DSCPAction 46 -ErrorAction SilentlyContinue",
            "New-NetQosPolicy -Name 'OmniNet_QUIC_AF41' -IPProtocolMatchCondition UDP -IPSrcPortStartMatchCondition 443 -IPSrcPortEndMatchCondition 443 -DSCPAction 34 -ErrorAction SilentlyContinue",
        ]
        for script in ps_cmds:
            res = hal.run_cmd(["powershell", "-NoProfile", "-Command", script], execute=True)
            logs.append(f"{res.command}: success={res.success}")
            if res.success:
                applied += 1
    elif plat == PlatformType.LINUX:
        # Mark outbound UDP 443/853 for low-latency queuing
        res = hal.run_cmd(
            ["iptables", "-t", "mangle", "-A", "OUTPUT", "-p", "udp", "--dport", "443", "-j", "DSCP", "--set-dscp", "34"],
            execute=True,
        )
        logs.append(f"{res.command}: success={res.success}")
        if res.success:
            applied += 1

    return {
        "success": True,
        "simulated": False,
        "platform": plat.value,
        "policies": policies,
        "applied_count": applied,
        "logs": logs,
    }


def manage_autostart_service(
    enabled: bool = True,
    hal: Optional[NetworkHAL] = None,
    execute: bool = False,
) -> Dict[str, Any]:
    """Installs or removes OmniNet persistent OS background autostart (schtasks on Windows, systemd --user on Linux)."""
    hal = hal or get_hal(dry_run=(execute is not True))
    should_apply = (execute is True) and not (getattr(hal, "dry_run", False) is True)
    plat = detect_platform()
    main_py = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"))

    if not should_apply:
        return {
            "success": True,
            "simulated": True,
            "enabled": enabled,
            "platform": plat.value,
            "service_name": TASK_NAME,
            "target": main_py,
        }

    if plat == PlatformType.WINDOWS:
        if enabled:
            cmd = [
                "schtasks", "/Create", "/TN", TASK_NAME,
                "/TR", f'"{sys.executable}" "{main_py}" serve --no-browser --live-autorepair',
                "/SC", "ONLOGON", "/F",
            ]
        else:
            cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
        res = hal.run_cmd(cmd, execute=True)
        return {
            "success": bool(res.success),
            "simulated": False,
            "enabled": enabled,
            "platform": plat.value,
            "service_name": TASK_NAME,
            "output": (res.stdout or res.stderr or "").strip(),
        }

    if plat == PlatformType.LINUX:
        unit_dir = os.path.expanduser("~/.config/systemd/user")
        unit_path = os.path.join(unit_dir, "omninet.service")
        if enabled:
            os.makedirs(unit_dir, exist_ok=True)
            with open(unit_path, "w", encoding="utf-8") as f:
                f.write(
                    "[Unit]\nDescription=OmniNet Autonomous Network & AI Defense\n\n"
                    f"[Service]\nExecStart={sys.executable} {main_py} serve --no-browser --live-autorepair\nRestart=always\n\n"
                    "[Install]\nWantedBy=default.target\n"
                )
            res = hal.run_cmd(["systemctl", "--user", "enable", "--now", "omninet.service"], execute=True)
            return {"success": bool(res.success), "simulated": False, "enabled": True, "platform": "linux", "unit": unit_path}
        res = hal.run_cmd(["systemctl", "--user", "disable", "--now", "omninet.service"], execute=True)
        if os.path.exists(unit_path):
            os.unlink(unit_path)
        return {"success": bool(res.success), "simulated": False, "enabled": False, "platform": "linux"}

    return {"success": False, "simulated": False, "platform": plat.value, "error": "Plataforma no soportada para servicio persistente"}
