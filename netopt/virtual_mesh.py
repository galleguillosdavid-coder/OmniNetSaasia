"""
Private Virtual Mesh (Wintun / TUN) & Multipath Failover Engine (`netopt/virtual_mesh.py`).
Connects up to 5 user devices over an encrypted virtual mesh and evaluates safe
Wi-Fi <-> Ethernet/USB multipath failover under Zero NetLoss invariants.
"""

from __future__ import annotations
import ipaddress
import os
import shutil
import threading
import time
from typing import Any, Dict, List, Optional

from .hal import NetworkHAL, PlatformType, detect_platform, get_hal
from .keystore import SovereignKeystore


MAX_MESH_PEERS = 5
MESH_SUBNET = ipaddress.IPv4Network("10.77.0.0/24")


class VirtualMeshManager:
    """Manages private P2P mesh peers (up to 5 devices) and Wintun/TUN readiness."""

    def __init__(self, keystore: Optional[SovereignKeystore] = None):
        self.keystore = keystore or SovereignKeystore()
        self._lock = threading.RLock()
        self.peers: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def check_tun_driver_availability() -> Dict[str, Any]:
        plat = detect_platform()
        if plat == PlatformType.WINDOWS:
            candidates = [
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "wintun.dll"),
                os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wintun.dll"),
            ]
            found = next((p for p in candidates if os.path.exists(p)), None)
            return {
                "platform": plat.value,
                "driver": "wintun",
                "available": found is not None,
                "path": found,
            }
        if plat == PlatformType.LINUX:
            has_tun = os.path.exists("/dev/net/tun")
            return {"platform": plat.value, "driver": "tun", "available": has_tun, "path": "/dev/net/tun" if has_tun else None}
        if plat == PlatformType.DARWIN:
            return {"platform": plat.value, "driver": "utun", "available": True, "path": "utun"}
        return {"platform": plat.value, "driver": "unknown", "available": False, "path": None}

    def register_peer(self, peer_id: str, public_key_hex: str, virtual_ip: str) -> Dict[str, Any]:
        clean_id = (peer_id or "").strip()
        if not clean_id:
            raise ValueError("peer_id must be a non-empty string")
        try:
            ip_obj = ipaddress.IPv4Address(virtual_ip.strip())
        except Exception as exc:
            raise ValueError(f"Invalid virtual_ip '{virtual_ip}'") from exc
        if ip_obj not in MESH_SUBNET or ip_obj in (MESH_SUBNET.network_address, MESH_SUBNET.broadcast_address):
            raise ValueError(f"virtual_ip must be a valid host address inside {MESH_SUBNET}")

        with self._lock:
            if clean_id not in self.peers and len(self.peers) >= MAX_MESH_PEERS:
                raise ValueError(f"Maximum mesh peer limit ({MAX_MESH_PEERS}) reached")
            for existing_id, info in self.peers.items():
                if existing_id != clean_id and info["virtual_ip"] == str(ip_obj):
                    raise ValueError(f"virtual_ip {ip_obj} is already assigned to peer '{existing_id}'")
            entry = {
                "peer_id": clean_id,
                "public_key_hex": public_key_hex.strip(),
                "virtual_ip": str(ip_obj),
                "added_at": time.time(),
            }
            self.peers[clean_id] = entry
            return entry

    def get_status(self) -> Dict[str, Any]:
        ident = self.keystore.export_public_identity()
        tun = self.check_tun_driver_availability()
        with self._lock:
            return {
                "local_did": ident["did"],
                "mesh_subnet": str(MESH_SUBNET),
                "max_peers": MAX_MESH_PEERS,
                "peers_count": len(self.peers),
                "peers": list(self.peers.values()),
                "tun_driver": tun,
            }


def evaluate_multipath_failover(
    hal: Optional[NetworkHAL] = None,
    primary_degraded: bool = False,
    execute: bool = False,
) -> Dict[str, Any]:
    """
    Evaluates available UP non-loopback interfaces and recommends (or applies under
    Zero NetLoss) a multipath failover to a healthy secondary interface.
    """
    hal = hal or get_hal(dry_run=True)
    should_apply = (execute is True) and not (getattr(hal, "dry_run", False) is True)
    ifaces = [i for i in hal.get_interfaces() if i.is_up and not i.is_loopback]

    primary = next((i for i in ifaces if "wi-fi" in i.name.lower() or "wlan" in i.name.lower()), ifaces[0] if ifaces else None)
    secondary = next((i for i in ifaces if primary is None or i.name != primary.name), None)

    if not primary or not secondary:
        return {
            "failover_available": False,
            "switched": False,
            "reason": "Se requiere al menos 2 enlaces activos (ej. Wi-Fi + Ethernet/USB) para failover multipath.",
            "active_interfaces": [i.name for i in ifaces],
        }

    if not primary_degraded:
        return {
            "failover_available": True,
            "switched": False,
            "primary": primary.name,
            "secondary": secondary.name,
            "reason": "Enlace primario saludable; respaldo multipath listo.",
        }

    if not should_apply:
        return {
            "failover_available": True,
            "switched": False,
            "simulated": True,
            "primary": primary.name,
            "secondary": secondary.name,
            "reason": f"Simulación Zero NetLoss: listo para priorizar '{secondary.name}' ante degradación en '{primary.name}'.",
        }

    plat = detect_platform()
    if plat == PlatformType.WINDOWS:
        act = hal.run_cmd(
            ["netsh", "interface", "ipv4", "set", "interface", secondary.name, "metric=5"],
            execute=True,
        )
        return {
            "failover_available": True,
            "switched": bool(act.success),
            "primary": primary.name,
            "secondary": secondary.name,
            "command": act.command,
        }

    if plat == PlatformType.LINUX:
        act = hal.run_cmd(
            ["nmcli", "connection", "modify", secondary.name, "ipv4.route-metric", "50"],
            execute=True,
        )
        if not act.success:
            act = hal.run_cmd(
                ["ip", "route", "replace", "default", "dev", secondary.name, "metric", "50"],
                execute=True,
            )
        return {
            "failover_available": True,
            "switched": bool(act.success),
            "primary": primary.name,
            "secondary": secondary.name,
            "command": act.command,
        }

    return {
        "failover_available": True,
        "switched": False,
        "primary": primary.name,
        "secondary": secondary.name,
        "reason": "Conmutación automática multipath disponible en Windows/Linux; en macOS requiere networksetup.",
    }
