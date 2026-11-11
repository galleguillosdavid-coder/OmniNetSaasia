"""
Hermes Executor: executes a ForeseePlan step-by-step through the Hermes harness
tool dispatcher under Zero NetLoss invariants.

- Dry-run honesty: mutating steps never touch the OS unless execute=True AND the HAL
  is not in dry-run; such steps are reported as SIMULATED (never SUCCEEDED).
- A single RollbackManager snapshot is captured before the first real mutation.
- Dependencies are respected; a failed critical step aborts the remaining steps.
- If the post-action verification fails after real changes, the snapshot is restored.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from netopt.hal import get_hal
from netopt.models import DiagnosticsReport
from netopt.diagnostics import audit_lan_radar_devices, check_duplicate_default_gateways_status
from netopt.optimizer import NetworkOptimizer
from netopt.repair import NetworkRepairEngine
from netopt.rollback import RollbackManager

from .harness import HermesAgentHarness
from .foresee import ForeseePlan, PlanStep

# Step statuses
SUCCEEDED, FAILED, SIMULATED, SKIPPED = "SUCCEEDED", "FAILED", "SIMULATED", "SKIPPED"


@dataclass
class StepResult:
    step_id: str
    strategy: str
    tool: str
    status: str
    criterion_met: bool = False
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class ExecutionReport:
    plan_id: str
    executed_for_real: bool
    step_results: List[StepResult]
    snapshot_id: Optional[str] = None
    rolled_back: bool = False
    rollback_log: List[str] = field(default_factory=list)
    aborted: bool = False
    duration_ms: float = 0.0

    def by_status(self, status: str) -> List[StepResult]:
        return [r for r in self.step_results if r.status == status]


class HermesExecutor:
    """Binds OmniNet engines as Hermes harness tools and runs Foresee plans."""

    def __init__(self, hal=None, harness: Optional[HermesAgentHarness] = None):
        self.hal = hal or get_hal(dry_run=True)
        self.harness = harness or HermesAgentHarness()
        self.optimizer = NetworkOptimizer(self.hal)
        self.repair = NetworkRepairEngine(self.hal)
        self.rollback_mgr = RollbackManager(self.hal)
        self._ctx: Dict[str, Any] = {}
        self._register_tools()

    # ------------------------------------------------------------------
    # Tool bindings (each returns success + criterion_met honestly)
    # ------------------------------------------------------------------
    def _register_tools(self) -> None:
        reg = self.harness.register_tool
        reg("hermes_capture_baseline", "Captura línea base de salud de red.", {}, self._tool_baseline)
        reg("hermes_triage_repair", "Triage jerárquico L1-L7 y reparación.", {}, self._tool_triage)
        reg("hermes_apply_optimization_plan", "Genera y aplica plan DNS/TCP.", {}, self._tool_opt_plan)
        reg("hermes_prune_duplicate_gateways", "Poda rutas 0.0.0.0/0 duplicadas.", {}, self._tool_prune)
        reg("hermes_gaming_l4s_qos", "Modo juego: QoS DSCP + L4S/ECN.", {}, self._tool_gaming)
        reg("hermes_lan_radar", "Radar Zero-Trust de dispositivos LAN.", {}, self._tool_radar)
        reg("hermes_system_resource_audit", "Auditoría de recursos del host (CPU, RAM, sockets).", {}, self._tool_resource_audit)
        reg("hermes_verify_health", "Verificación Zero NetLoss post-acción.", {}, self._tool_verify)

    def _do_exec(self) -> bool:
        return bool(self._ctx.get("do_exec", False))

    def _tool_baseline(self) -> Dict[str, Any]:
        base = self.rollback_mgr.capture_baseline()
        self._ctx["baseline"] = base
        return {"success": True, "criterion_met": True,
                "avg_latency_ms": round(base.avg_latency_ms, 2),
                "packet_loss_percent": round(base.packet_loss_percent, 2)}

    def _tool_triage(self) -> Dict[str, Any]:
        failure, logs = self.repair.diagnose_and_triage(diag=self._ctx.get("diag"))
        if failure == "HEALTHY":
            return {"success": True, "criterion_met": True, "failure_type": failure, "actions": 0}
        acts = self.repair.execute_triage_repair(failure, execute=self._do_exec())
        failed = [a.description for a in acts if not a.success and not a.is_dry_run]
        ok = not failed
        return {"success": ok, "criterion_met": ok, "failure_type": failure,
                "actions": len(acts), "failed_actions": failed}

    def _tool_opt_plan(self) -> Dict[str, Any]:
        plan = self.optimizer.generate_plan(self._ctx.get("diag"))
        if not plan.planned_actions:
            return {"success": True, "criterion_met": True, "actions": 0, "detail": "Sin acciones DNS/TCP necesarias."}
        ok, logs = self.optimizer.execute_plan(plan, execute=self._do_exec())
        return {"success": bool(ok), "criterion_met": bool(ok), "actions": len(plan.planned_actions),
                "plan_status": plan.status, "logs": list(logs)[:10]}

    def _tool_prune(self) -> Dict[str, Any]:
        status = check_duplicate_default_gateways_status()
        if not status.get("has_duplicate_gateways"):
            return {"success": True, "criterion_met": True, "pruned": 0}
        acts = self.hal.prune_duplicate_default_gateways(execute=self._do_exec())
        failed = [a.command for a in acts if not a.success and not a.is_dry_run]
        return {"success": not failed, "criterion_met": not failed, "pruned": len(acts), "failed_actions": failed}

    def _tool_gaming(self) -> Dict[str, Any]:
        res = self.optimizer.optimize_gaming_and_l4s_qos(execute=self._do_exec())
        ok = bool(res.get("gaming_mode_active")) and int(res.get("commands_failed", 0) or 0) == 0
        return {"success": ok, "criterion_met": ok, "summary": res.get("summary", "")}

    def _tool_radar(self) -> Dict[str, Any]:
        radar = audit_lan_radar_devices()
        impersonation = bool(radar.get("gateway_impersonation_detected", False))
        return {"success": True, "criterion_met": not impersonation,
                "devices": radar.get("total_devices_detected", 0),
                "gateway_impersonation_detected": impersonation,
                "anomalies": radar.get("anomalies", [])}

    def _tool_resource_audit(self) -> Dict[str, Any]:
        try:
            from netopt.adapters import SystemResourceAdapter
            telemetry = SystemResourceAdapter.get_cpu_and_memory_telemetry()
            top_procs = SystemResourceAdapter.get_top_network_processes(limit=5)
            io_counters = SystemResourceAdapter.get_interface_io_counters()
            disk = SystemResourceAdapter.get_disk_telemetry()
            return {
                "success": True,
                "criterion_met": True,
                "cpu_percent": telemetry.get("cpu_percent", 0.0),
                "ram_total_mb": telemetry.get("ram_total_mb", 0),
                "ram_available_mb": telemetry.get("ram_available_mb", 0),
                "memory_pressure": bool(telemetry.get("memory_pressure", False)),
                "disk_free_gb": disk.get("free_gb", 0.0),
                "disk_used_percent": disk.get("used_percent", 0.0),
                "top_processes_count": len(top_procs),
                "interfaces_monitored": len(io_counters.get("interfaces", {}))
            }
        except Exception as e:
            return {"success": False, "criterion_met": False, "error": str(e)}

    def _tool_verify(self) -> Dict[str, Any]:
        ok, msg = self.rollback_mgr.verify_post_action_health(baseline=self._ctx.get("baseline"))
        return {"success": bool(ok), "criterion_met": bool(ok), "message": msg}

    # ------------------------------------------------------------------
    def execute(self, plan: ForeseePlan, diag: Optional[DiagnosticsReport] = None,
                execute: bool = False) -> ExecutionReport:
        t0 = time.perf_counter()
        do_exec = bool(execute) and not (getattr(self.hal, "dry_run", False) is True)
        self._ctx = {"diag": diag, "do_exec": do_exec, "baseline": None}
        report = ExecutionReport(plan_id=plan.plan_id, executed_for_real=do_exec, step_results=[])
        satisfied: set = set()

        for step in plan.steps:
            if report.aborted:
                report.step_results.append(StepResult(step.step_id, step.strategy, step.tool, SKIPPED,
                                                      error="Plan abortado por fallo de paso crítico previo."))
                continue
            missing = [d for d in step.depends_on if d not in satisfied]
            if missing:
                report.step_results.append(StepResult(step.step_id, step.strategy, step.tool, SKIPPED,
                                                      error=f"Dependencias no satisfechas: {missing}"))
                continue

            if step.mutating and step.requires_snapshot and do_exec and report.snapshot_id is None:
                try:
                    snap = self.rollback_mgr.capture_snapshot(description=f"Hermes pre-plan {plan.plan_id}")
                    report.snapshot_id = snap.snapshot_id
                except Exception as e:
                    report.step_results.append(StepResult(step.step_id, step.strategy, step.tool, FAILED,
                                                          error=f"Snapshot Zero NetLoss falló: {e}"))
                    report.aborted = True
                    continue

            res = self._run_step(step, do_exec)
            report.step_results.append(res)
            if res.status in (SUCCEEDED, SIMULATED):
                satisfied.add(step.step_id)
            elif step.critical:
                report.aborted = True

        verify = next((r for r in report.step_results if r.strategy == "verify"), None)
        if do_exec and report.snapshot_id and (verify is None or verify.status != SUCCEEDED):
            report.rollback_log = self.rollback_mgr.rollback(report.snapshot_id, execute=True)
            report.rolled_back = True

        report.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        return report

    def _run_step(self, step: PlanStep, do_exec: bool) -> StepResult:
        disp = self.harness.dispatch_tool(step.tool, dict(step.args))
        inner = disp.get("result") if isinstance(disp.get("result"), dict) else {}
        ok = bool(disp.get("success"))
        if not ok:
            status = FAILED
        elif step.mutating and not do_exec:
            status = SIMULATED
        else:
            status = SUCCEEDED
        return StepResult(
            step_id=step.step_id, strategy=step.strategy, tool=step.tool, status=status,
            criterion_met=bool(ok and inner.get("criterion_met", ok)),
            output=inner, error=disp.get("error") or (inner.get("message") if not ok else None),
            duration_ms=float(disp.get("duration_ms", 0.0))
        )

