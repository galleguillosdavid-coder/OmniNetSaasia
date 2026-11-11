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
        self.assertIn("top_processes_count", step_res[0].output)


if __name__ == "__main__":
    unittest.main()

