"""
Persistent Monitoring, Drift Detection and Self-Healing Daemon.
Continuously samples network SLA, checks for configuration drift, and triggers auto-healing.
"""

from __future__ import annotations
import json
import os
import time
from typing import Optional, Dict, Any, Callable
from .models import HealthState, DiagnosticsReport
from .hal import NetworkHAL, get_hal
from .diagnostics import run_full_diagnostics
from .repair import NetworkRepairEngine
from .optimizer import NetworkOptimizer
from .rollback import RollbackManager


STATE_DIR = os.path.join(os.path.expanduser("~"), ".netopt_state")
TELEMETRY_LOG = os.path.join(STATE_DIR, "telemetry.jsonl")


class NetworkDaemon:
    """Persistent background sentinel for network health and drift defense."""

    def __init__(
        self,
        hal: Optional[NetworkHAL] = None,
        poll_interval_sec: int = 60,
        max_acceptable_latency_ms: float = 120.0,
        max_acceptable_loss_percent: float = 2.0,
        auto_heal: bool = False
    ):
        self.hal = hal or get_hal(dry_run=True)
        self.poll_interval = poll_interval_sec
        self.max_latency = max_acceptable_latency_ms
        self.max_loss = max_acceptable_loss_percent
        self.auto_heal = auto_heal
        self.running = False
        self.repair_engine = NetworkRepairEngine(self.hal)
        self.optimizer = NetworkOptimizer(self.hal)
        self.rollback_mgr = RollbackManager(self.hal)
        os.makedirs(STATE_DIR, exist_ok=True)

    def log_telemetry(self, diag: DiagnosticsReport):
        """Appends metric sample to rotating telemetry log."""
        record = {
            "timestamp": diag.timestamp,
            "overall_health": diag.overall_health.value,
            "gateway_reachable": diag.gateway_reachable,
            "internet_reachable": diag.internet_reachable,
            "dns_resolving": diag.dns_resolving,
            "bufferbloat_grade": diag.bufferbloat_grade,
            "anomalies": diag.anomalies,
            "latency": {k: v.avg_ms for k, v in diag.latency_metrics.items()},
            "packet_loss": {k: v.packet_loss_percent for k, v in diag.latency_metrics.items()}
        }

        # Rotate if > 10MB
        if os.path.exists(TELEMETRY_LOG) and os.path.getsize(TELEMETRY_LOG) > 10 * 1024 * 1024:
            try:
                os.replace(TELEMETRY_LOG, f"{TELEMETRY_LOG}.bak")
            except Exception:
                pass

        try:
            with open(TELEMETRY_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    def check_and_heal_once(self) -> Dict[str, Any]:
        """Runs a single iteration of SLA verification and auto-remediation."""
        diag = run_full_diagnostics()
        self.log_telemetry(diag)
        do_exec = not (getattr(self.hal, "dry_run", False) is True)

        status: Dict[str, Any] = {
            "timestamp": diag.timestamp,
            "health": diag.overall_health.value,
            "dry_run": not do_exec,
            "snapshot_id": None,
            "actions_taken": []
        }

        # Check for SLA violations
        sla_violation = False
        for target, m in diag.latency_metrics.items():
            if m.packet_loss_percent > self.max_loss:
                sla_violation = True
                status["actions_taken"].append(f"SLA Violation: {target} packet loss {m.packet_loss_percent}% > {self.max_loss}%")
            if m.avg_ms > self.max_latency:
                sla_violation = True
                status["actions_taken"].append(f"SLA Violation: {target} latency {m.avg_ms}ms > {self.max_latency}ms")

        # Trigger auto-heal if enabled and health is degraded or down
        if self.auto_heal and (diag.overall_health in [HealthState.DOWN, HealthState.DEGRADED] or sla_violation):
            failure_type, triage_logs = self.repair_engine.diagnose_and_triage(diag=diag)
            if failure_type == "HEALTHY" and sla_violation:
                failure_type = "L7_HIGH_LOSS_OR_DEGRADED"
            status["actions_taken"].append(f"Triage diagnosis: {failure_type}")
            if failure_type != "HEALTHY":
                if do_exec:
                    snap = self.rollback_mgr.capture_snapshot(
                        description=f"NetworkDaemon pre-heal snapshot ({failure_type})"
                    )
                    status["snapshot_id"] = snap.snapshot_id
                repair_actions = self.repair_engine.execute_triage_repair(failure_type, execute=do_exec)
                for act in repair_actions:
                    status["actions_taken"].append(
                        f"Auto-Heal action: {act.description} (success={act.success}, dry_run={act.is_dry_run})"
                    )

        return status

    def run_loop(self, max_cycles: Optional[int] = None, callback: Optional[Callable] = None):
        """Starts monitoring loop."""
        self.running = True
        cycles = 0
        while self.running:
            res = self.check_and_heal_once()
            if callback:
                callback(res)
            cycles += 1
            if max_cycles and cycles >= max_cycles:
                break
            time.sleep(self.poll_interval)

    def stop(self):
        self.running = False

