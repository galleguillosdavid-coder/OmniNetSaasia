"""
Hermes Foresee Planner: anticipatory, diagnostics-driven planning stage of the
Plan -> Execute -> Reflect cognitive loop.

Foresee converts a goal plus real telemetry (DiagnosticsReport) into an ordered,
dependency-aware plan. Every step declares its predicted effect and a verifiable
success criterion, a risk level, and whether a Zero NetLoss snapshot is required.
Strategies that Reflect recorded as repeatedly failing are excluded (closed loop).
"""

from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from netopt.models import DiagnosticsReport, HealthState

BAD_BUFFERBLOAT_GRADES = ("C", "D", "F")
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")


@dataclass
class PlanStep:
    step_id: str
    strategy: str              # Stable identifier used by Reflect to learn (e.g. "dns_failover")
    tool: str                  # Tool name registered in the Hermes harness
    args: Dict[str, Any]
    rationale: str
    predicted_effect: str
    success_criterion: str     # Human readable criterion verified by Reflect
    risk: str = "LOW"          # LOW / MEDIUM / HIGH
    mutating: bool = False     # True if the step changes system state
    requires_snapshot: bool = False
    critical: bool = False     # Failure aborts the remaining dependent steps
    depends_on: List[str] = field(default_factory=list)


@dataclass
class ForeseePlan:
    plan_id: str
    goal: str
    created_at: float
    health_before: str
    steps: List[PlanStep]
    excluded_strategies: List[str] = field(default_factory=list)
    risk_summary: str = "LOW"
    reasoning: List[str] = field(default_factory=list)

    @property
    def mutating_steps(self) -> List[PlanStep]:
        return [s for s in self.steps if s.mutating]


class ForeseePlanner:
    """Deterministic, evidence-based planner (no LLM required, no invented telemetry)."""

    def __init__(self, failure_threshold: int = 2, max_latency_ms: float = 120.0):
        self.failure_threshold = failure_threshold
        self.max_latency_ms = max_latency_ms

    # ------------------------------------------------------------------
    def blocked_strategies(self, reflections: Optional[Dict[str, Any]]) -> Set[str]:
        """Strategies whose consecutive failures reached the threshold (learned by Reflect)."""
        blocked: Set[str] = set()
        for name, stats in (reflections or {}).get("strategies", {}).items():
            if int(stats.get("consecutive_failures", 0)) >= self.failure_threshold:
                blocked.add(name)
        return blocked

    def _candidate_steps(self, goal: str, diag: DiagnosticsReport) -> List[PlanStep]:
        low = (goal or "").lower()
        cands: List[PlanStep] = []

        def add(strategy: str, tool: str, rationale: str, effect: str, criterion: str,
                risk: str = "LOW", mutating: bool = False, critical: bool = False,
                args: Optional[Dict[str, Any]] = None) -> None:
            cands.append(PlanStep(
                step_id="", strategy=strategy, tool=tool, args=args or {},
                rationale=rationale, predicted_effect=effect, success_criterion=criterion,
                risk=risk, mutating=mutating, requires_snapshot=mutating, critical=critical
            ))

        worst_latency = max((m.avg_ms for m in diag.latency_metrics.values()), default=0.0)
        worst_loss = max((m.packet_loss_percent for m in diag.latency_metrics.values()), default=0.0)

        # L1-L3 connectivity failures take precedence (hierarchical triage)
        if not diag.gateway_reachable or not diag.internet_reachable:
            add("triage_repair", "hermes_triage_repair",
                f"Gateway alcanzable={diag.gateway_reachable}, Internet alcanzable={diag.internet_reachable}.",
                "Restablecer conectividad L1-L3 mediante triage jerárquico.",
                "La reparación no reporta acciones fallidas y la salud posterior no es DOWN.",
                risk="HIGH", mutating=True, critical=True)
        if not diag.dns_resolving or "dns" in low:
            add("dns_failover", "hermes_apply_optimization_plan",
                f"Resolución DNS activa={diag.dns_resolving}.",
                "Migrar a resolvers Anycast más rápidos verificados por benchmark.",
                "execute_plan retorna éxito y dns_resolving=True tras la verificación.",
                risk="MEDIUM", mutating=True)
        route_terms = ("ruta", "gateway", "route")
        if any(t in low for t in route_terms) or any(t in a.lower() for a in diag.anomalies for t in route_terms):
            add("route_pruning", "hermes_prune_duplicate_gateways",
                "Auditoría de rutas 0.0.0.0/0 duplicadas (Windows 11 24H2).",
                "Eliminar rutas por defecto obsoletas que causan cortes intermitentes.",
                "No quedan acciones de poda fallidas.",
                risk="MEDIUM", mutating=True)
        if (diag.bufferbloat_grade in BAD_BUFFERBLOAT_GRADES or worst_latency > self.max_latency_ms
                or any(k in low for k in ("juego", "gaming", "latencia", "lag", "videollamada"))):
            add("gaming_l4s_qos", "hermes_gaming_l4s_qos",
                f"Bufferbloat {diag.bufferbloat_grade}, peor latencia {round(worst_latency, 1)} ms, pérdida {worst_loss}%.",
                "Reducir jitter/bufferbloat con QoS DSCP, L4S/ECN y throttling index.",
                "gaming_mode_active=True y commands_failed=0.",
                risk="MEDIUM", mutating=True)
        if any(k in low for k in ("radar", "intruso", "seguridad", "spoof", "arp")):
            add("lan_radar", "hermes_lan_radar",
                "Auditoría Zero-Trust de dispositivos LAN solicitada.",
                "Detectar intrusos y suplantación ARP del gateway.",
                "gateway_impersonation_detected=False.")
        return cands

    # ------------------------------------------------------------------
    def foresee(self, goal: str, diag: DiagnosticsReport,
                reflections: Optional[Dict[str, Any]] = None,
                extra_excluded: Optional[Set[str]] = None) -> ForeseePlan:
        blocked = self.blocked_strategies(reflections) | set(extra_excluded or set())
        reasoning = [f"Salud observada: {diag.overall_health.value}."]

        steps: List[PlanStep] = [PlanStep(
            step_id="s1", strategy="baseline", tool="hermes_capture_baseline", args={},
            rationale="Medir línea base antes de cualquier cambio (Zero NetLoss).",
            predicted_effect="Línea base de latencia/pérdida registrada.",
            success_criterion="Baseline capturado sin excepción.", critical=True
        )]
        excluded: List[str] = []
        seen: Set[str] = set()
        for cand in self._candidate_steps(goal, diag):
            if cand.strategy in seen:
                continue
            seen.add(cand.strategy)
            if cand.strategy in blocked:
                excluded.append(cand.strategy)
                reasoning.append(f"Estrategia '{cand.strategy}' excluida por fallos previos registrados por Reflect.")
                continue
            cand.step_id = f"s{len(steps) + 1}"
            cand.depends_on = ["s1"]
            steps.append(cand)

        if len(steps) == 1:
            reasoning.append("Sin cuellos de botella accionables; el plan se limita a medir y verificar.")
        steps.append(PlanStep(
            step_id=f"s{len(steps) + 1}", strategy="verify", tool="hermes_verify_health", args={},
            rationale="Puerta de verificación post-acción contra la línea base.",
            predicted_effect="Confirmar que no hubo degradación.",
            success_criterion="verify_post_action_health aprobada.",
            depends_on=["s1"]
        ))

        risk = "LOW"
        for s in steps:
            if RISK_LEVELS.index(s.risk) > RISK_LEVELS.index(risk):
                risk = s.risk
        return ForeseePlan(
            plan_id=f"foresee-{uuid.uuid4().hex[:8]}", goal=goal, created_at=time.time(),
            health_before=diag.overall_health.value if isinstance(diag.overall_health, HealthState) else str(diag.overall_health),
            steps=steps, excluded_strategies=excluded, risk_summary=risk, reasoning=reasoning
        )
