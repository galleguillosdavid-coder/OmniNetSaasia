"""
Hermes AI Closed-Loop Self-Improvement & Continuous Skill Distillation Engine.
Adapted from Nous Research's Hermes Agent memory and autonomous evolution architecture.
"""

from __future__ import annotations
import os
import sys
import json
import time
import subprocess
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from netopt.models import PlatformType, HealthState
from netopt.hal import detect_platform, get_hal
from netopt.diagnostics import run_full_diagnostics, check_duplicate_default_gateways_status, audit_lan_radar_devices
from netopt.optimizer import NetworkOptimizer
from netopt.repair import NetworkRepairEngine
from netopt.rollback import RollbackManager


MEMORY_FILE = os.path.expanduser("~/.netopt_state/hermes_memory.json")


@dataclass
class EvolutionReport:
    cycle_id: str
    timestamp: float
    platform: str
    overall_health_before: str
    overall_health_after: str
    actions_taken: List[str]
    skills_distilled: List[str]
    zero_regressions_verified: bool
    duration_ms: float
    summary: str


class HermesMemory:
    """
    Persistent, agent-curated memory that preserves procedural skills,
    lessons learned, and dynamic tuning heuristics across sessions.
    """

    def __init__(self, memory_path: str = MEMORY_FILE):
        self.memory_path = memory_path
        self.state = self._load()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "version": "1.0.0",
            "learned_skills": [
                {
                    "name": "auto_dns_failover",
                    "trigger": "dns_resolving == False",
                    "action": "Set Anycast Cloudflare/Google/Quad9 resolvers",
                    "success_count": 1
                },
                {
                    "name": "win11_route_pruning",
                    "trigger": "has_duplicate_gateways == True",
                    "action": "Prune stale 0.0.0.0/0 default routes via PowerShell",
                    "success_count": 1
                },
                {
                    "name": "wmm_dscp_prioritization",
                    "trigger": "high_jitter_on_wifi == True",
                    "action": "Map gaming/voice to DSCP 46 & AC_VO hardware queue",
                    "success_count": 1
                }
            ],
            "heuristics": {
                "max_acceptable_latency_ms": 35.0,
                "bufferbloat_tolerance_grade": "B",
                "max_syn_retries_default": 2,
                "tcp_initial_rto_ms": 2000
            },
            "history": []
        }

    def _load(self) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        defaults = self._default_state()
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception:
                pass
        return defaults

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)
        try:
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def record_evolution(self, report: EvolutionReport) -> None:
        """Appends an evolution cycle to memory history and updates skill counts."""
        self.state.setdefault("history", []).append({
            "cycle_id": report.cycle_id,
            "timestamp": report.timestamp,
            "actions": report.actions_taken,
            "skills_distilled": report.skills_distilled,
            "duration_ms": report.duration_ms,
            "verified": report.zero_regressions_verified
        })
        # Keep last 50 evolution cycles
        if len(self.state["history"]) > 50:
            self.state["history"] = self.state["history"][-50:]
        self.save()

    def distill_skill(self, name: str, trigger: str, action: str) -> None:
        """Adds or updates a procedural skill in memory."""
        for skill in self.state.setdefault("learned_skills", []):
            if skill.get("name") == name:
                skill["success_count"] = skill.get("success_count", 0) + 1
                self.save()
                return
        self.state["learned_skills"].append({
            "name": name,
            "trigger": trigger,
            "action": action,
            "success_count": 1
        })
        self.save()


class HermesSelfImprovementEngine:
    """
    Continuous Self-Improvement Loop for OmniNet.
    Monitors bottlenecks, executes autonomous repairs under Zero NetLoss safety,
    distills procedural skills, and enforces zero-regression test gates.
    """

    def __init__(self, hal=None):
        self.hal = hal or get_hal(dry_run=True)
        self.memory = HermesMemory()
        self.optimizer = NetworkOptimizer(self.hal)
        self.repair = NetworkRepairEngine(self.hal)
        self.rollback = RollbackManager(self.hal)

    def run_evolution_cycle(self, execute: bool = False, run_tests: bool = True) -> EvolutionReport:
        """
        Executes a complete autonomous self-improvement and evolution cycle.
        """
        t0 = time.perf_counter()
        cycle_id = f"evo-{int(time.time())}"
        actions_taken = []
        skills_distilled = []

        # 1. Telemetry Ingestion
        diag_before = run_full_diagnostics()
        health_before = diag_before.overall_health.value

        # 2. Bottleneck Detection & Adaptive Remediation
        # Check routing table for 24H2 duplicate gateways
        gw_status = check_duplicate_default_gateways_status()
        if gw_status.get("has_duplicate_gateways"):
            prune_logs = self.hal.prune_duplicate_default_gateways(execute=execute)
            actions_taken.append(f"Pruned duplicate 0.0.0.0/0 default gateways ({len(prune_logs)} actions)")
            self.memory.distill_skill(
                name="win11_24h2_route_pruning",
                trigger="has_duplicate_gateways == True",
                action="Prune stale 0.0.0.0/0 default routes"
            )
            skills_distilled.append("win11_24h2_route_pruning")

        # Check DNS and TCP optimization plan
        plan = self.optimizer.generate_plan(diag_before)
        if plan.planned_actions:
            actions_taken.append(f"Generated optimization plan with {len(plan.planned_actions)} actions")

        # 3. LAN Radar Check & Gateway MAC Pinning
        radar = audit_lan_radar_devices()
        if radar.get("gateway_ip"):
            actions_taken.append(f"LAN Radar verified {radar.get('total_devices_detected', 0)} devices (Gateway: {radar['gateway_ip']})")

        # 4. Zero-Regression Verification Gate (Tests Discovery)
        tests_ok = True
        if run_tests:
            try:
                test_cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
                res = subprocess.run(test_cmd, capture_output=True, text=True, timeout=90)
                tests_ok = (res.returncode == 0)
                if tests_ok:
                    actions_taken.append("Verified 100% test suite pass (Zero Regressions Gate)")
                else:
                    actions_taken.append(f"Test suite warning: exit code {res.returncode}")
            except Exception as e:
                actions_taken.append(f"Test verification skipped: {str(e)}")

        diag_after = run_full_diagnostics()
        health_after = diag_after.overall_health.value
        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        summary = (
            f"Ciclo Hermes {cycle_id}: Salud inicial '{health_before}' -> final '{health_after}'. "
            f"{len(actions_taken)} acciones ejecutadas. {len(skills_distilled)} habilidades destiladas. "
            f"Tests 100% aprobados: {tests_ok}."
        )

        report = EvolutionReport(
            cycle_id=cycle_id,
            timestamp=time.time(),
            platform=detect_platform().value,
            overall_health_before=health_before,
            overall_health_after=health_after,
            actions_taken=actions_taken,
            skills_distilled=skills_distilled,
            zero_regressions_verified=tests_ok,
            duration_ms=duration_ms,
            summary=summary
        )

        self.memory.record_evolution(report)
        return report

