"""
Tests for the Hermes Foresee (planner) -> Executor -> Reflect (evaluator) cognitive loop.
"""

import os
import tempfile
import shutil
import unittest
from unittest.mock import MagicMock, patch

from netopt.hal import WindowsHAL
from netopt.models import (
    DiagnosticsReport, PlatformType, HealthState, LatencyMetrics, OrchestrationPlan, AgentActionLog
)
from netopt.rollback import BaselineHealthMetrics
from hermes import (
    ForeseePlanner, HermesExecutor, ReflectEvaluator, HermesCognitiveLoop, HermesMemory
)
from hermes.executor import SIMULATED, FAILED, SUCCEEDED


def make_diag(health=HealthState.DEGRADED, dns=False, grade="D", latency=180.0):
    return DiagnosticsReport(
        timestamp=1000.0, platform=PlatformType.WINDOWS, overall_health=health,
        default_gateway="192.168.1.1", gateway_reachable=True, internet_reachable=True,
        dns_resolving=dns, dns_benchmarks=[],
        latency_metrics={"1.1.1.1": LatencyMetrics("1.1.1.1", 4, 4, 0.0, latency, latency + 5, latency + 10, 3.0)},
        detected_pmtu=1500, bufferbloat_grade=grade, active_interface="Wi-Fi"
    )


BASELINE = BaselineHealthMetrics(timestamp=1.0, avg_latency_ms=20.0, packet_loss_percent=0.0)


class TestHermesCognitiveLoop(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.memory = HermesMemory(memory_path=os.path.join(self.tmp, "mem.json"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stub_engines(self, executor, gaming_ok=True, verify_ok=True):
        executor.rollback_mgr.capture_baseline = MagicMock(return_value=BASELINE)
        executor.rollback_mgr.verify_post_action_health = MagicMock(return_value=(verify_ok, "verify"))
        executor.rollback_mgr.capture_snapshot = MagicMock(return_value=MagicMock(snapshot_id="snap_cog_1"))
        executor.rollback_mgr.rollback = MagicMock(return_value=["restored"])
        plan = OrchestrationPlan(planned_actions=[AgentActionLog(description="dns")])
        executor.optimizer.generate_plan = MagicMock(return_value=plan)
        executor.optimizer.execute_plan = MagicMock(return_value=(True, ["ok"]))
        executor.optimizer.optimize_gaming_and_l4s_qos = MagicMock(return_value={
            "gaming_mode_active": gaming_ok, "commands_failed": 0 if gaming_ok else 2, "summary": "x"})

    def test_foresee_plan_structure_and_learned_exclusion(self):
        planner = ForeseePlanner()
        plan = planner.foresee("bajar latencia para juegos", make_diag())
        strategies = [s.strategy for s in plan.steps]
        self.assertEqual(strategies[0], "baseline")
        self.assertEqual(strategies[-1], "verify")
        self.assertIn("dns_failover", strategies)
        self.assertIn("gaming_l4s_qos", strategies)
        self.assertTrue(all(s.requires_snapshot for s in plan.mutating_steps))
        self.assertEqual(plan.risk_summary, "MEDIUM")

        # Strategy with consecutive failures >= threshold is excluded by Foresee
        refl = {"strategies": {"gaming_l4s_qos": {"consecutive_failures": 2}}}
        plan2 = planner.foresee("bajar latencia para juegos", make_diag(), reflections=refl)
        self.assertNotIn("gaming_l4s_qos", [s.strategy for s in plan2.steps])
        self.assertIn("gaming_l4s_qos", plan2.excluded_strategies)

        # Healthy network with no goal keywords -> only measure + verify
        plan3 = ForeseePlanner().foresee("revisar", make_diag(HealthState.HEALTHY, True, "A", 20.0))
        self.assertEqual([s.strategy for s in plan3.steps], ["baseline", "verify"])

    def test_executor_dry_run_never_reports_success_for_mutations(self):
        executor = HermesExecutor(WindowsHAL(dry_run=True))
        self._stub_engines(executor)
        plan = ForeseePlanner().foresee("juegos", make_diag())
        rep = executor.execute(plan, diag=make_diag(), execute=True)
        self.assertFalse(rep.executed_for_real)
        self.assertIsNone(rep.snapshot_id)
        for r in rep.step_results:
            if r.strategy in ("dns_failover", "gaming_l4s_qos"):
                self.assertEqual(r.status, SIMULATED)
        executor.rollback_mgr.capture_snapshot.assert_not_called()

        refl = ReflectEvaluator(self.memory).evaluate(plan, rep)
        self.assertEqual(refl.verdict, "SIMULATED")
        self.assertFalse(refl.should_replan)
        self.assertEqual(self.memory.state["reflections"]["strategies"], {})

    def test_real_failure_rollback_reflect_and_replan_learning(self):
        hal = MagicMock()
        hal.dry_run = False
        executor = HermesExecutor(hal)
        self._stub_engines(executor, gaming_ok=False, verify_ok=False)
        plan = ForeseePlanner().foresee("juegos", make_diag())
        rep = executor.execute(plan, diag=make_diag(), execute=True)

        self.assertTrue(rep.executed_for_real)
        self.assertEqual(rep.snapshot_id, "snap_cog_1")
        executor.rollback_mgr.capture_snapshot.assert_called_once()
        self.assertTrue(rep.rolled_back)
        executor.rollback_mgr.rollback.assert_called_once_with("snap_cog_1", execute=True)
        statuses = {r.strategy: r.status for r in rep.step_results}
        self.assertEqual(statuses["gaming_l4s_qos"], FAILED)
        self.assertEqual(statuses["dns_failover"], SUCCEEDED)

        evaluator = ReflectEvaluator(self.memory)
        refl = evaluator.evaluate(plan, rep)
        self.assertEqual(refl.verdict, "FAIL")
        self.assertIn("gaming_l4s_qos", refl.failed_strategies)
        self.assertTrue(refl.should_replan)
        evaluator.evaluate(plan, rep)  # second consecutive failure
        stats = self.memory.state["reflections"]["strategies"]["gaming_l4s_qos"]
        self.assertEqual(stats["consecutive_failures"], 2)
        self.assertEqual(self.memory.state["reflections"]["strategies"]["dns_failover"]["consecutive_failures"], 0)

        blocked = ForeseePlanner().blocked_strategies(evaluator.reflections_state())
        self.assertIn("gaming_l4s_qos", blocked)

    def test_cognitive_loop_replans_excluding_failed_strategy(self):
        hal = MagicMock()
        hal.dry_run = False
        loop = HermesCognitiveLoop(hal=hal, memory=self.memory)
        self._stub_engines(loop.executor, gaming_ok=False, verify_ok=True)
        with patch("hermes.cognitive_loop.run_full_diagnostics", return_value=make_diag()):
            rep = loop.run("juegos", execute=True, max_iterations=2, diag=make_diag())
        self.assertEqual(len(rep.iterations), 2)
        self.assertIn("gaming_l4s_qos", [s.strategy for s in rep.iterations[0].plan.steps])
        self.assertNotIn("gaming_l4s_qos", [s.strategy for s in rep.iterations[1].plan.steps])
        self.assertEqual(rep.final_verdict, "PASS")
        d = rep.to_dict()
        self.assertEqual(d["final_verdict"], "PASS")
        self.assertTrue(d["executed_for_real"])

    def test_executor_system_resource_audit(self):
        executor = HermesExecutor(WindowsHAL(dry_run=True))
        self._stub_engines(executor)
        plan = ForeseePlanner().foresee("revisar sockets y rendimiento de memoria", make_diag())
        rep = executor.execute(plan, diag=make_diag(), execute=False)
        step_res = [r for r in rep.step_results if r.strategy == "resource_audit"]
        self.assertTrue(len(step_res) > 0)
        self.assertEqual(step_res[0].status, SUCCEEDED)
        self.assertTrue(step_res[0].criterion_met)
        self.assertIn("cpu_percent", step_res[0].output)
        self.assertIn("disk_free_gb", step_res[0].output)
        self.assertIn("disk_used_percent", step_res[0].output)
        self.assertIn("power_plugged", step_res[0].output)
        self.assertIn("battery_percent", step_res[0].output)
        self.assertIn("top_processes_count", step_res[0].output)

    def test_foresee_energy_and_power_goal_triggers_resource_audit(self):
        """Verifies that energy and battery audit goals deterministically trigger resource_audit."""
        planner = ForeseePlanner()
        plan = planner.foresee("auditar consumo de energia y estado de bateria del equipo", make_diag())
        strategies = [s.strategy for s in plan.steps]
        self.assertIn("baseline", strategies)
        self.assertIn("resource_audit", strategies)
        step = [s for s in plan.steps if s.strategy == "resource_audit"][0]
        self.assertEqual(step.tool, "hermes_system_resource_audit")
        self.assertFalse(step.mutating)
        self.assertEqual(step.risk, "LOW")

    def test_reflect_evaluator_history_limit_and_distillation(self):
        from hermes.executor import ExecutionReport, StepResult
        evaluator = ReflectEvaluator(memory=self.memory, history_limit=5)
        plan = ForeseePlanner().foresee("juegos", make_diag())

        step_results = [
            StepResult(
                step_id=s.step_id, strategy=s.strategy, tool=s.tool,
                status=SUCCEEDED, duration_ms=10.0, output={}, criterion_met=True
            )
            for s in plan.steps
        ]
        report = ExecutionReport(plan_id=plan.plan_id, executed_for_real=True, step_results=step_results)

        # Pre-seed consecutive failure in strategy
        self.memory.state["reflections"] = {
            "strategies": {"gaming_l4s_qos": {"success_count": 0, "failure_count": 3, "consecutive_failures": 3}},
            "history": []
        }

        refl = evaluator.evaluate(plan, report, health_after="healthy")
        self.assertEqual(refl.verdict, "PASS")
        self.assertEqual(refl.score, 100)

        # Verify consecutive failures reset to 0
        stats = self.memory.state["reflections"]["strategies"]["gaming_l4s_qos"]
        self.assertEqual(stats["consecutive_failures"], 0)
        self.assertEqual(stats["success_count"], 1)

        # Verify skill was distilled into memory
        self.assertTrue(any(s.get("name") == "foresee_gaming_l4s_qos" for s in self.memory.state["learned_skills"]))

        # Push 10 reflections to test history_limit=5
        for _ in range(10):
            evaluator.evaluate(plan, report, health_after="healthy")
        self.assertLessEqual(len(self.memory.state["reflections"]["history"]), 5)

    def test_summarize_learning_insights_and_meta_cognitive_propagation(self):
        """Verifies meta-cognitive synthesis of learning insights and propagation via HermesCognitiveLoop."""
        from hermes.cognitive_loop import HermesCognitiveLoop
        from starlette.testclient import TestClient
        from netopt.fastapi_app import create_app

        evaluator = ReflectEvaluator(memory=self.memory)

        # Empty state
        insights_empty = evaluator.summarize_learning_insights()
        self.assertEqual(insights_empty["total_plans_evaluated"], 0)
        self.assertEqual(insights_empty["high_confidence_strategies"], [])
        self.assertEqual(insights_empty["penalized_strategies"], [])

        # Seed state with learned strategies and historical evaluations
        self.memory.state["reflections"] = {
            "strategies": {
                "dns_failover": {"success_count": 5, "failure_count": 0, "consecutive_failures": 0},
                "gaming_l4s_qos": {"success_count": 4, "failure_count": 1, "consecutive_failures": 0},
                "bbr_congestion": {"success_count": 0, "failure_count": 3, "consecutive_failures": 3},
                "experimental_tweak": {"success_count": 1, "failure_count": 0, "consecutive_failures": 0}
            },
            "history": [
                {"plan_id": "p1", "verdict": "PASS", "score": 100, "executed_for_real": True},
                {"plan_id": "p2", "verdict": "SIMULATED", "score": 80, "executed_for_real": False},
                {"plan_id": "p3", "verdict": "FAIL", "score": 20, "executed_for_real": True}
            ]
        }

        insights = evaluator.summarize_learning_insights()
        self.assertEqual(insights["total_plans_evaluated"], 3)
        self.assertEqual(insights["real_execution_plans"], 2)
        # Pass rate: 2 out of 3 = 66.67%
        self.assertAlmostEqual(insights["historical_pass_rate_pct"], 66.67, places=1)
        # Avg score: (100 + 80 + 20) / 3 = 66.67
        self.assertAlmostEqual(insights["avg_plan_score"], 66.67, places=1)
        self.assertEqual(insights["total_strategies_tracked"], 4)
        # High confidence: dns_failover (5/5), gaming_l4s_qos (4/5 = 80%)
        self.assertEqual(insights["high_confidence_strategies"], ["dns_failover", "gaming_l4s_qos"])
        # Penalized: bbr_congestion (consecutive_failures=3 >= 2)
        self.assertEqual(insights["penalized_strategies"], ["bbr_congestion"])

        # Test HermesCognitiveLoop propagation
        loop = HermesCognitiveLoop(memory=self.memory)
        loop_insights = loop.meta_cognitive_insights()
        self.assertEqual(loop_insights["total_strategies_tracked"], 4)
        self.assertEqual(loop_insights["penalized_strategies"], ["bbr_congestion"])

        # Test FastAPI /api/hermes/insights endpoint
        app = create_app()
        client = TestClient(app)
        res = client.get("/api/hermes/insights")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_strategies_tracked", data)
        self.assertIn("high_confidence_strategies", data)
        self.assertIn("penalized_strategies", data)

    def test_foresee_pqc_goal_triggers_pqc_audit_tool(self):
        """Verifies that PQC / Quantum security goals trigger hermes_pqc_audit."""
        plan = ForeseePlanner().foresee("verificar seguridad cuantica y algoritmos pqc", make_diag())
        strategies = [s.strategy for s in plan.steps]
        self.assertIn("pqc_audit", strategies)

        step = [s for s in plan.steps if s.strategy == "pqc_audit"][0]
        self.assertEqual(step.tool, "hermes_pqc_audit")
        self.assertFalse(step.mutating)
        self.assertEqual(step.risk, "LOW")

        # Execute step via HermesExecutor
        executor = HermesExecutor(WindowsHAL(dry_run=True))
        self._stub_engines(executor)
        res = executor.execute(plan, diag=make_diag(), execute=False)
        pqc_result = [r for r in res.step_results if r.strategy == "pqc_audit"][0]
        self.assertTrue(pqc_result.criterion_met)
        self.assertEqual(pqc_result.output.get("active_pqc_algorithm"), "X25519MLKEM768")

    def test_foresee_encrypted_dns_and_dner_goals_trigger_specialized_tools(self):
        """Verifies DDR/DNR encrypted discovery and DNER/EDE error reporting in Foresee & Executor."""
        planner = ForeseePlanner()
        plan = planner.foresee("autodescubrimiento ddr dnr svcb y auditoria de errores dns dner ede", make_diag())
        strategies = [s.strategy for s in plan.steps]
        self.assertIn("encrypted_dns_discovery", strategies)
        self.assertIn("dns_error_reporting", strategies)

        step_ddr = [s for s in plan.steps if s.strategy == "encrypted_dns_discovery"][0]
        self.assertEqual(step_ddr.tool, "hermes_encrypted_dns_discovery")
        self.assertFalse(step_ddr.mutating)

        step_dner = [s for s in plan.steps if s.strategy == "dns_error_reporting"][0]
        self.assertEqual(step_dner.tool, "hermes_dns_error_reporting")
        self.assertFalse(step_dner.mutating)

        # Execute steps via HermesExecutor
        executor = HermesExecutor(WindowsHAL(dry_run=True))
        self._stub_engines(executor)
        res = executor.execute(plan, diag=make_diag(), execute=False)

        ddr_res = [r for r in res.step_results if r.strategy == "encrypted_dns_discovery"][0]
        self.assertTrue(ddr_res.criterion_met)
        self.assertIn("RFC 9463", ddr_res.output.get("standard_ddr", ""))

        dner_res = [r for r in res.step_results if r.strategy == "dns_error_reporting"][0]
        self.assertTrue(dner_res.criterion_met)
        self.assertIn("RFC 9578", dner_res.output.get("standard_dner", ""))


if __name__ == "__main__":
    unittest.main()

