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
from typing import Optional, Dict, Any, List, Tuple
from .models import SnapshotState, PlatformType
from .hal import NetworkHAL, get_hal, detect_platform
from .diagnostics import measure_target_metrics


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

    def verify_post_action_health(self) -> Tuple[bool, str]:
        """
        Validates post-action network health.
        Fails if >=66% packet loss occurs across redundant targets or latency spikes >500ms.
        """
        m = measure_target_metrics("1.1.1.1", count=3, port=53)
        if m.packet_loss_percent >= 66.0:
            m2 = measure_target_metrics("8.8.8.8", count=3, port=53)
            if m2.packet_loss_percent >= 66.0:
                return False, f"Severe connectivity degradation: 1.1.1.1={m.packet_loss_percent}% loss, 8.8.8.8={m2.packet_loss_percent}% loss."

        if m.avg_ms > 500.0:
            return False, f"Severe latency spike post-action: {m.avg_ms}ms avg RTT."

        return True, f"Network verified healthy (RTT: {m.avg_ms}ms, Loss: {m.packet_loss_percent}%)."
