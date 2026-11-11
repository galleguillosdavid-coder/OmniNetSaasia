"""
Hermes Reflect Evaluator: closes the Plan -> Execute -> Reflect loop.

Grades an ExecutionReport against the ForeseePlan success criteria and the observed
health transition, produces lessons, decides whether to re-plan, and persists
per-strategy outcomes in HermesMemory so Foresee can avoid repeated failures.

Honesty rules (hallucination-control):
- SIMULATED steps are never counted as verified improvements and never update
  the learned strategy statistics.
- A rollback or a failed critical step always yields verdict FAIL.
"""

from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .foresee import ForeseePlan
from .executor import ExecutionReport, SUCCEEDED, FAILED, SIMULATED, SKIPPED
from .self_improvement import HermesMemory

HEALTH_RANK = {"healthy": 0, "degraded": 1, "critical": 2, "down": 3}
NON_LEARNABLE = ("baseline", "verify")


@dataclass
class Reflection:
    plan_id: str
    verdict: str                 # PASS / PARTIAL / FAIL / SIMULATED
    score: int                   # 0-100, verified steps only
    health_before: str
    health_after: str
    health_regressed: bool
    verified_steps: List[str]
    failed_strategies: List[str]
    lessons: List[str]
    should_replan: bool
    timestamp: float = field(default_factory=time.time)


class ReflectEvaluator:
    def __init__(self, memory: Optional[HermesMemory] = None, history_limit: int = 50):
        self.memory = memory or HermesMemory()
        self.history_limit = history_limit

    def reflections_state(self) -> Dict[str, Any]:
        return self.memory.state.setdefault("reflections", {"strategies": {}, "history": []})

    def evaluate(self, plan: ForeseePlan, report: ExecutionReport,
                 health_after: Optional[str] = None, persist: bool = True) -> Reflection:
        steps_by_id = {s.step_id: s for s in plan.steps}
        results = report.step_results
        verified = [r.step_id for r in results if r.status == SUCCEEDED and r.criterion_met]
        failed = [r for r in results if r.status == FAILED or (r.status == SUCCEEDED and not r.criterion_met)]
        simulated = [r for r in results if r.status == SIMULATED]
        skipped = [r for r in results if r.status == SKIPPED]

        h_before = (plan.health_before or "unknown").lower()
        h_after = (health_after or h_before).lower()
        regressed = HEALTH_RANK.get(h_after, 0) > HEALTH_RANK.get(h_before, 0)
        critical_failed = any(steps_by_id.get(r.step_id) and steps_by_id[r.step_id].critical
                              and r.status == FAILED for r in results)

        if report.rolled_back or critical_failed or (report.executed_for_real and regressed):
            verdict = "FAIL"
        elif not failed and not skipped and not simulated:
            verdict = "PASS"
        elif not failed and not skipped and simulated and not report.executed_for_real:
            verdict = "SIMULATED"
        else:
            verdict = "PARTIAL"

        score = round(100 * len(verified) / len(results)) if results else 0

        lessons: List[str] = []
        for r in failed:
            why = r.error or ("criterio de éxito no cumplido" if r.status == SUCCEEDED else "fallo sin detalle")
            lessons.append(f"Estrategia '{r.strategy}' ({r.tool}) no cumplió: {why}.")
        for r in skipped:
            lessons.append(f"Paso {r.step_id} '{r.strategy}' omitido: {r.error}.")
        if simulated:
            lessons.append(f"{len(simulated)} paso(s) solo simulados (dry-run); sin evidencia de mejora real.")
        if report.rolled_back:
            lessons.append(f"Snapshot {report.snapshot_id} restaurado por fallo de verificación Zero NetLoss.")
        if regressed:
            lessons.append(f"Salud empeoró de '{h_before}' a '{h_after}'.")
        if verdict == "PASS":
            lessons.append("Todas las estrategias verificadas con evidencia real.")

        failed_strategies = sorted({r.strategy for r in failed if r.strategy not in NON_LEARNABLE})
        should_replan = verdict in ("FAIL", "PARTIAL") and report.executed_for_real and bool(failed_strategies)

        refl = Reflection(
            plan_id=plan.plan_id, verdict=verdict, score=score, health_before=h_before,
            health_after=h_after, health_regressed=regressed, verified_steps=verified,
            failed_strategies=failed_strategies, lessons=lessons, should_replan=should_replan
        )
        if persist:
            self._persist(plan, report, refl)
        return refl

    def _persist(self, plan: ForeseePlan, report: ExecutionReport, refl: Reflection) -> None:
        state = self.reflections_state()
        strategies = state.setdefault("strategies", {})
        if report.executed_for_real:
            for r in report.step_results:
                if r.strategy in NON_LEARNABLE or r.status in (SIMULATED, SKIPPED):
                    continue
                st = strategies.setdefault(r.strategy, {"success_count": 0, "failure_count": 0, "consecutive_failures": 0})
                if r.status == SUCCEEDED and r.criterion_met:
                    st["success_count"] += 1
                    st["consecutive_failures"] = 0
                    if refl.verdict == "PASS":
                        step = next((s for s in plan.steps if s.step_id == r.step_id), None)
                        self.memory.distill_skill(
                            name=f"foresee_{r.strategy}",
                            trigger=step.rationale if step else r.strategy,
                            action=step.predicted_effect if step else r.tool
                        )
                else:
                    st["failure_count"] += 1
                    st["consecutive_failures"] += 1
                st["last_outcome_at"] = refl.timestamp
        history = state.setdefault("history", [])
        history.append({
            "plan_id": refl.plan_id, "goal": plan.goal, "verdict": refl.verdict, "score": refl.score,
            "executed_for_real": report.executed_for_real, "failed_strategies": refl.failed_strategies,
            "timestamp": refl.timestamp
        })
        state["history"] = history[-self.history_limit:]
        self.memory.save()

