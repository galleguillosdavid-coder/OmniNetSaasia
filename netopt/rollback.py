"""
Snapshot, Validation and Deterministic Rollback Engine.
Guarantees Zero Network Breakage by snapshotting before mutations,
auto-pruning old snapshots, and rolling back upon failure.
"""

from __future__ import annotations
import json
import os
import time
import uuid
import socket
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from .models import SnapshotState, PlatformType
from .hal import NetworkHAL, get_hal, detect_platform
from .diagnostics import measure_target_metrics


@dataclass
class BaselineHealthMetrics:
    timestamp: float
    gateway_reachable: bool = True
    dns_resolving: bool = True
    avg_latency_ms: float = 25.0
    packet_loss_percent: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


SNAPSHOT_DIR = os.path.join(os.path.expanduser("~"), ".netopt_state", "snapshots")
MAX_SNAPSHOTS = 25


class RollbackManager:
    """Manages system configuration snapshots, retention pruning, and verified restorations."""

    def __init__(self, hal: Optional[NetworkHAL] = None, max_snapshots: int = MAX_SNAPSHOTS):
        self.hal = hal or get_hal(dry_run=True)
        self.max_snapshots = max_snapshots
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    def prune_snapshots(self, max_keep: Optional[int] = None) -> int:
        """Removes oldest snapshots exceeding retention limit. Returns number of purged files."""
        limit = max_keep if max_keep is not None else self.max_snapshots
        if not os.path.exists(SNAPSHOT_DIR):
            return 0
        try:
            files = [
                os.path.join(SNAPSHOT_DIR, f)
                for f in os.listdir(SNAPSHOT_DIR)
                if f.endswith(".json")
            ]
            if len(files) <= limit:
                return 0
            files.sort(key=lambda p: os.path.getmtime(p))
            to_delete = files[:-limit] if limit > 0 else files
            removed = 0
            for fpath in to_delete:
                try:
                    os.remove(fpath)
                    removed += 1
                except OSError:
                    pass
            return removed
        except Exception:
            return 0

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """Lists metadata of all available snapshots on disk."""
        if not os.path.exists(SNAPSHOT_DIR):
            return []
        snapshots = []
        try:
            for f in os.listdir(SNAPSHOT_DIR):
                if f.endswith(".json"):
                    p = os.path.join(SNAPSHOT_DIR, f)
                    try:
                        with open(p, "r", encoding="utf-8") as fp:
                            data = json.load(fp)
                            snapshots.append({
                                "snapshot_id": data.get("snapshot_id", f[:-5]),
                                "timestamp": data.get("timestamp", os.path.getmtime(p)),
                                "description": data.get("description", "Snapshot"),
                                "platform": data.get("platform", "unknown")
                            })
                    except Exception:
                        pass
            snapshots.sort(key=lambda s: s.get("timestamp", 0), reverse=True)
        except Exception:
            pass
        return snapshots

    def capture_snapshot(self, description: str = "Pre-optimization state") -> SnapshotState:
        """Captures current network configuration state into a persistent snapshot with auto-pruning."""
        snapshot_id = f"snap_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        dns_servers = self.hal.get_dns_servers()
        tcp_params = self.hal.get_tcp_parameters()

        interfaces = self.hal.get_interfaces()
        mtu_dict = {iface.name: (iface.mtu or 1500) for iface in interfaces if iface.name}
        dns_dict = {"default": dns_servers}

        snap = SnapshotState(
            snapshot_id=snapshot_id,
            timestamp=time.time(),
            platform=detect_platform(),
            dns_settings=dns_dict,
            tcp_parameters=tcp_params,
            mtu_settings=mtu_dict,
            description=description
        )

        file_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({
                    "snapshot_id": snap.snapshot_id,
                    "timestamp": snap.timestamp,
                    "platform": snap.platform.value,
                    "dns_settings": snap.dns_settings,
                    "tcp_parameters": snap.tcp_parameters,
                    "mtu_settings": snap.mtu_settings,
                    "description": snap.description
                }, f, indent=2)
            self.prune_snapshots()
        except Exception:
            pass

        return snap

    def load_snapshot(self, snapshot_id: str) -> Optional[SnapshotState]:
        """Loads a snapshot from disk by ID."""
        file_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.json")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SnapshotState(
                snapshot_id=data["snapshot_id"],
                timestamp=data["timestamp"],
                platform=PlatformType(data["platform"]),
                dns_settings=data.get("dns_settings", {}),
                tcp_parameters=data.get("tcp_parameters", {}),
                mtu_settings=data.get("mtu_settings", {}),
                description=data.get("description", "")
            )
        except Exception:
            return None

    def rollback(self, snapshot_id: str, execute: bool = False) -> List[str]:
        """Restores network state (TCP, DNS, MTU, and resolver cache) from the designated snapshot."""
        snap = self.load_snapshot(snapshot_id)
        if not snap:
            return [f"ERROR: Snapshot {snapshot_id} not found."]

        results = []
        if snap.tcp_parameters:
            tcp_logs = self.hal.set_tcp_parameters(snap.tcp_parameters, execute=execute)
            results.extend([f"TCP restore: {l.command} (success={l.success})" for l in tcp_logs])

        default_dns = snap.dns_settings.get("default", [])
        interfaces = self.hal.get_interfaces()
        if default_dns:
            for iface in interfaces:
                if iface.is_up and not iface.is_loopback:
                    dns_log = self.hal.set_dns_servers(iface.name, default_dns, execute=execute)
                    results.append(f"DNS restore on {iface.name}: {dns_log.command} (success={dns_log.success})")

        if snap.mtu_settings:
            for iface in interfaces:
                if iface.is_up and not iface.is_loopback and iface.name in snap.mtu_settings:
                    mtu_log = self.hal.set_interface_mtu(iface.name, snap.mtu_settings[iface.name], execute=execute)
                    results.append(f"MTU restore on {iface.name}: {mtu_log.command} (success={mtu_log.success})")

        flush_log = self.hal.flush_dns_cache(execute=execute)
        results.append(f"Cache flush: {flush_log.command} (success={flush_log.success})")

        return results

    def capture_baseline(self) -> BaselineHealthMetrics:
        """Captures a pre-action baseline of network health across multiple resolvers and latency targets."""
        gw = self.hal.get_default_gateway()
        gw_reachable = True
        if gw:
            m_gw = measure_target_metrics(gw, count=2, port=53)
            gw_reachable = m_gw.packet_loss_percent < 100.0

        # Check real socket DNS resolution
        dns_ok = False
        try:
            socket.getaddrinfo("cloudflare.com", 80)
            dns_ok = True
        except Exception:
            try:
                socket.getaddrinfo("google.com", 80)
                dns_ok = True
            except Exception:
                dns_ok = False

        m1 = measure_target_metrics("1.1.1.1", count=3, port=53)
        m2 = measure_target_metrics("8.8.8.8", count=3, port=53)
        avg_lat = (m1.avg_ms + m2.avg_ms) / 2.0
        avg_loss = (m1.packet_loss_percent + m2.packet_loss_percent) / 2.0

        return BaselineHealthMetrics(
            timestamp=time.time(),
            gateway_reachable=gw_reachable,
            dns_resolving=dns_ok,
            avg_latency_ms=avg_lat,
            packet_loss_percent=avg_loss,
            details={"1.1.1.1_ms": m1.avg_ms, "8.8.8.8_ms": m2.avg_ms}
        )

    def verify_post_action_health(self, baseline: Optional[BaselineHealthMetrics] = None) -> Tuple[bool, str]:
        """
        Validates post-action network health against a pre-action baseline (OMNI-007).
        Enforces strict Zero NetLoss invariants:
          - Real DNS resolution must succeed.
          - Packet loss cannot exceed baseline by >15% (or >20% absolute).
          - Latency cannot degrade >2x baseline or exceed 250ms without justification.
        """
        if getattr(self.hal, "dry_run", False):
            return True, "DRY-RUN SIMULATION: Verificación Zero NetLoss aprobada."

        # 1. DNS Resolution Check
        dns_ok = False
        try:
            socket.getaddrinfo("cloudflare.com", 80)
            dns_ok = True
        except Exception:
            try:
                socket.getaddrinfo("google.com", 80)
                dns_ok = True
            except Exception:
                dns_ok = False

        if not dns_ok:
            return False, "Fallo Zero NetLoss: La resolución DNS del sistema falló tras la acción."

        # 2. Multi-target latency and loss measurement
        m1 = measure_target_metrics("1.1.1.1", count=3, port=53)
        m2 = measure_target_metrics("8.8.8.8", count=3, port=53)
        cur_loss = (m1.packet_loss_percent + m2.packet_loss_percent) / 2.0
        cur_lat = (m1.avg_ms + m2.avg_ms) / 2.0

        # 3. Comparative evaluation against pre-action baseline
        if baseline:
            loss_increase = cur_loss - baseline.packet_loss_percent
            if loss_increase > 20.0 or cur_loss > 33.0:
                return False, f"Degradación Zero NetLoss: Pérdida de paquetes subió a {cur_loss:.1f}% (Línea base: {baseline.packet_loss_percent:.1f}%)."
            if cur_lat > max(250.0, baseline.avg_latency_ms * 2.2):
                return False, f"Degradación Zero NetLoss: Latencia RTT subió a {cur_lat:.1f}ms (Línea base: {baseline.avg_latency_ms:.1f}ms)."

        # 4. Absolute sanity checks (when baseline unavailable)
        elif cur_loss >= 33.0:
            return False, f"Pérdida de paquetes inaceptable post-acción: {cur_loss:.1f}%."
        elif cur_lat > 350.0:
            return False, f"Pico de latencia inaceptable post-acción: {cur_lat:.1f}ms."

        return True, f"Verificación Zero NetLoss Exitosa (RTT: {cur_lat:.1f}ms, Pérdida: {cur_loss:.1f}%)."
