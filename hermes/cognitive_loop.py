"""
Hermes Cognitive Loop: Foresee (plan) -> Executor (act) -> Reflect (evaluate),
with bounded re-planning that excludes strategies Reflect marked as failed.
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from netopt.hal import get_hal
from netopt.models import DiagnosticsReport
from netopt.diagnostics import run_full_diagnostics

from .foresee import ForeseePlanner, ForeseePlan
from .executor import HermesExecutor, ExecutionReport
from .reflect import ReflectEvaluator, Reflection
from .self_improvement import HermesMemory


@dataclass
class CognitiveIteration:
    iteration: int
    plan: ForeseePlan
    execution: ExecutionReport
    reflection: Reflection


@dataclass
class CognitiveCycleReport:
    cycle_id: str
    goal: str
    executed_for_real: bool
    iterations: List[CognitiveIteration] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def final_verdict(self) -> str:
        return self.iterations[-1].reflection.verdict if self.iterations else "FAIL"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "goal": self.goal,
            "executed_for_real": self.executed_for_real,
            "final_verdict": self.final_verdict,
            "duration_ms": self.duration_ms,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "plan_id": it.plan.plan_id,
                    "risk": it.plan.risk_summary,
                    "steps": [{"id": s.step_id, "strategy": s.strategy, "tool": s.tool, "risk": s.risk}
                              for s in it.plan.steps],
                    "excluded_strategies": it.plan.excluded_strategies,
                    "results": [{"id": r.step_id, "strategy": r.strategy, "status": r.status,
                                 "criterion_met": r.criterion_met, "error": r.error}
                                for r in it.execution.step_results],
                    "snapshot_id": it.execution.snapshot_id,
                    "rolled_back": it.execution.rolled_back,
                    "verdict": it.reflection.verdict,
                    "score": it.reflection.score,
                    "lessons": it.reflection.lessons,
                }
                for it in self.iterations
            ],
        }


class HermesCognitiveLoop:
    def __init__(self, hal=None, memory: Optional[HermesMemory] = None,
                 planner: Optional[ForeseePlanner] = None):
        self.hal = hal or get_hal(dry_run=True)
        self.memory = memory or HermesMemory()
        self.planner = planner or ForeseePlanner()
        self.executor = HermesExecutor(self.hal)
        self.evaluator = ReflectEvaluator(self.memory)

    def run(self, goal: str, execute: bool = False, max_iterations: int = 2,
            diag: Optional[DiagnosticsReport] = None) -> CognitiveCycleReport:
        t0 = time.perf_counter()
        report = CognitiveCycleReport(cycle_id=f"cog-{uuid.uuid4().hex[:8]}", goal=goal,
                                      executed_for_real=False)
        excluded: Set[str] = set()
        current = diag
        for i in range(1, max(1, max_iterations) + 1):
            current = current or run_full_diagnostics()
            plan = self.planner.foresee(goal, current, self.evaluator.reflections_state(), excluded)
            exe = self.executor.execute(plan, diag=current, execute=execute)
            report.executed_for_real = report.executed_for_real or exe.executed_for_real
            # Only re-measure after real changes; in dry-run the state is unchanged by definition
            after = run_full_diagnostics() if exe.executed_for_real else current
            refl = self.evaluator.evaluate(plan, exe, health_after=after.overall_health.value)
            report.iterations.append(CognitiveIteration(i, plan, exe, refl))
            if not refl.should_replan:
                break
            excluded |= set(refl.failed_strategies)
            current = after
        report.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        return report

