"""
Autonomous Network Sentinel & Auto-Healing Trigger.
Continuously monitors network health, detects degradation, autonomously heals
and optimizes the connection, and produces structured repair incident reports.
"""

from __future__ import annotations
import json
import os
import time
import uuid
import threading
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any

from .models import HealthState, DiagnosticsReport, PlatformType
from .hal import NetworkHAL, get_hal, detect_platform
from .diagnostics import run_full_diagnostics, measure_target_metrics
from .repair import NetworkRepairEngine
from .optimizer import NetworkOptimizer
from .rollback import RollbackManager


INCIDENTS_FILE = os.path.join(os.path.expanduser("~"), ".netopt_state", "incidents.json")


@dataclass
class IncidentReport:
    incident_id: str
    timestamp: float
    trigger_reason: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    status: str  # RESOLVED, MITIGATED, FAILED, IN_PROGRESS
    failure_tier: str  # L1_INTERFACE, L2_DHCP, L3_ROUTING, L4_DNS, L7_CONGESTION
    metrics_before: Dict[str, Any]
    metrics_after: Dict[str, Any]
    actions_taken: List[str]
    snapshot_id: Optional[str] = None
    duration_ms: float = 0.0
    human_summary: str = ""


class AutoSentinel:
    """Autonomous Sentinel that self-heals degraded networks and records reports."""

    def __init__(
        self,
        hal: Optional[NetworkHAL] = None,
        interval_sec: int = 60,
        latency_threshold_ms: float = 240.0,
        loss_threshold_percent: float = 2.0,
        cooldown_sec: int = 600,
        enabled: bool = True
    ):
        self.hal = hal or get_hal(dry_run=False)
        self.interval = interval_sec
        self.latency_threshold = latency_threshold_ms
        self.loss_threshold = loss_threshold_percent
        self.cooldown_sec = cooldown_sec
        self.last_heal_time: float = 0.0
        self.baseline_rtt_ms: Optional[float] = None
        self.enabled = enabled
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.repair_engine = NetworkRepairEngine(self.hal)
        self.optimizer = NetworkOptimizer(self.hal)
        self.rollback_mgr = RollbackManager(self.hal)
        self.incidents: List[IncidentReport] = self._load_incidents()
        self.last_check_time: float = 0.0
        self.last_check_status: str = "INITIALIZING"

    def _load_incidents(self) -> List[IncidentReport]:
        if not os.path.exists(INCIDENTS_FILE):
            return []
        try:
            with open(INCIDENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [IncidentReport(**item) for item in data]
        except Exception:
            return []

    def _save_incidents(self):
        os.makedirs(os.path.dirname(INCIDENTS_FILE), exist_ok=True)
        try:
            with open(INCIDENTS_FILE, "w", encoding="utf-8") as f:
                json.dump([asdict(inc) for inc in self.incidents[-50:]], f, indent=2)
        except Exception:
            pass

    def check_health_and_auto_heal(self) -> Optional[IncidentReport]:
        """Runs a telemetry check. If bad, triggers auto-healing and logs report."""
        self.last_check_time = time.time()
        diag = run_full_diagnostics()
        self.last_check_status = diag.overall_health.value.upper()

        trigger_reasons = []
        severity = "LOW"

        # Check conditions
        if not diag.internet_reachable:
            trigger_reasons.append("Internet inalcanzable (pérdida total 100%)")
            severity = "CRITICAL"
        elif not diag.dns_resolving:
            trigger_reasons.append("Falla total de resolución de nombres DNS")
            severity = "HIGH"
        elif not diag.gateway_reachable:
            trigger_reasons.append(f"Gateway predeterminado {diag.default_gateway or 'Unknown'} inalcanzable")
            severity = "CRITICAL"

        cf_metrics = diag.latency_metrics.get("1.1.1.1")
        if cf_metrics and cf_metrics.packets_received > 0:
            # Update rolling EWMA baseline RTT (adapts to VPN/tunnel base latency ~165ms)
            if self.baseline_rtt_ms is None:
                self.baseline_rtt_ms = cf_metrics.avg_ms
            else:
                self.baseline_rtt_ms = 0.85 * self.baseline_rtt_ms + 0.15 * cf_metrics.avg_ms

            dynamic_lat_limit = max(self.latency_threshold, self.baseline_rtt_ms * 1.45)

            if cf_metrics.packet_loss_percent > self.loss_threshold:
                trigger_reasons.append(f"Pérdida de paquetes elevada: {cf_metrics.packet_loss_percent}% (Umbral: {self.loss_threshold}%)")
                if severity != "CRITICAL":
                    severity = "HIGH"
            if cf_metrics.avg_ms > dynamic_lat_limit:
                trigger_reasons.append(
                    f"Pico real sobre línea base: {cf_metrics.avg_ms}ms (Base túnel: {round(self.baseline_rtt_ms, 1)}ms, Umbral: {round(dynamic_lat_limit, 1)}ms)"
                )
                if severity == "LOW":
                    severity = "MEDIUM"

        if diag.bufferbloat_grade in ["D", "F"]:
            trigger_reasons.append(f"Bufferbloat crítico detectado (Grado {diag.bufferbloat_grade})")
            if severity == "LOW":
                severity = "MEDIUM"

        # If healthy, or non-critical trigger inside 10-minute hysteresis cooldown, skip thrashing
        if not trigger_reasons and diag.overall_health == HealthState.HEALTHY:
            return None
        if severity != "CRITICAL" and (time.time() - self.last_heal_time) < self.cooldown_sec:
            return None

        self.last_heal_time = time.time()

        # Red está mala -> Disparar optimización y autorreparación automática
        t0 = time.perf_counter()
        incident_id = f"inc_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        trigger_str = " | ".join(trigger_reasons)

        metrics_before = {
            "overall_health": diag.overall_health.value,
            "latency_ms": cf_metrics.avg_ms if cf_metrics else 999.0,
            "packet_loss_pct": cf_metrics.packet_loss_percent if cf_metrics else 100.0,
            "jitter_ms": cf_metrics.jitter_ms if cf_metrics else 0.0,
            "gateway_reachable": diag.gateway_reachable,
            "dns_resolving": diag.dns_resolving
        }

        # Step 1: Snapshot de seguridad Zero NetLoss
        snap = self.rollback_mgr.capture_snapshot(description=f"Auto-heal pre-snapshot {incident_id}")

        actions_taken = []
        failure_tier, triage_logs = self.repair_engine.diagnose_and_triage()
        actions_taken.extend([f"Diagnóstico Triage: {failure_tier}"] + triage_logs)

        # Step 2: Ejecutar auto-reparación o afinamiento
        if failure_tier != "HEALTHY":
            repair_acts = self.repair_engine.execute_triage_repair(failure_tier, execute=True)
            for ra in repair_acts:
                actions_taken.append(f"Reparación ejecutada: {ra.description} (status={ra.success})")

        # Step 3: Aplicar optimización TCP / DNS si era problema de rendimiento
        opt_plan = self.optimizer.generate_plan()
        success, opt_logs = self.optimizer.execute_plan(opt_plan, execute=True)
        actions_taken.extend([f"Optimización: {l}" for l in opt_logs])

        # Step 4: Medir métricas posteriores
        time.sleep(1.5)
        after_metrics = measure_target_metrics("1.1.1.1", count=4, port=53)
        post_diag = run_full_diagnostics()

        metrics_after = {
            "overall_health": post_diag.overall_health.value,
            "latency_ms": after_metrics.avg_ms,
            "packet_loss_pct": after_metrics.packet_loss_percent,
            "jitter_ms": after_metrics.jitter_ms,
            "gateway_reachable": post_diag.gateway_reachable,
            "dns_resolving": post_diag.dns_resolving
        }

        # Step 5: Evaluar éxito
        is_recovered = (
            post_diag.overall_health == HealthState.HEALTHY or
            after_metrics.packet_loss_percent < metrics_before["packet_loss_pct"] or
            after_metrics.avg_ms < metrics_before["latency_ms"]
        )

        status = "RESOLVED" if is_recovered else "MITIGATED"
        duration_ms = (time.perf_counter() - t0) * 1000

        summary = (
            f"Se detectó {trigger_str}. El agente ejecutó triage {failure_tier}, "
            f"optimizó la pila TCP y resolvers DNS Anycast. La latencia cambió de "
            f"{metrics_before['latency_ms']}ms a {metrics_after['latency_ms']}ms con "
            f"{metrics_after['packet_loss_pct']}% de pérdida. Estado: {status}."
        )

        report = IncidentReport(
            incident_id=incident_id,
            timestamp=time.time(),
            trigger_reason=trigger_str,
            severity=severity,
            status=status,
            failure_tier=failure_tier,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            actions_taken=actions_taken,
            snapshot_id=snap.snapshot_id,
            duration_ms=round(duration_ms, 2),
            human_summary=summary
        )

        self.incidents.append(report)
        self._save_incidents()
        return report

    def _loop(self):
        while self.running:
            if self.enabled:
                try:
                    self.check_health_and_auto_heal()
                except Exception:
                    pass
            time.sleep(self.interval)

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AutoSentinelThread")
        self._thread.start()

    def stop(self):
        self.running = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "running": self.running,
            "interval_sec": self.interval,
            "latency_threshold_ms": self.latency_threshold,
            "loss_threshold_percent": self.loss_threshold,
            "last_check_time": self.last_check_time,
            "last_check_status": self.last_check_status,
            "total_incidents_recorded": len(self.incidents)
        }


# Global singleton instance
_SENTINEL_INSTANCE: Optional[AutoSentinel] = None


def get_sentinel() -> AutoSentinel:
    global _SENTINEL_INSTANCE
    if _SENTINEL_INSTANCE is None:
        _SENTINEL_INSTANCE = AutoSentinel()
    return _SENTINEL_INSTANCE

