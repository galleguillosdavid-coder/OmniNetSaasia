"""
Unit and integration tests for Hermes AI Agent Harness & Orchestrator.
Verifies cognitive execution loop, dynamic tool dispatch, multi-agent spawning,
and closed-loop self-improvement.
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import sys

from hermes.harness import HermesAgentHarness, HermesHarnessConfig, ToolDefinition
from hermes.orchestrator import HermesOrchestrator, SubagentSession
from hermes.self_improvement import HermesSelfImprovementEngine, HermesMemory, EvolutionReport


class TestHermesAgentHarness(unittest.TestCase):

    def setUp(self):
        self.harness = HermesAgentHarness()

    def test_tool_registration_and_schemas(self):
        def sample_calculator(a: int, b: int) -> int:
            return a + b

        self.harness.register_tool(
            name="add_numbers",
            description="Adds two integers",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"}
                },
                "required": ["a", "b"]
            },
            func=sample_calculator
        )

        self.assertIn("add_numbers", self.harness.tools)
        schemas = self.harness.get_tool_schemas()
        names = [s["function"]["name"] for s in schemas]
        self.assertIn("add_numbers", names)
        self.assertIn("execute_python", names)

    def test_tool_dispatch_success_and_error_handling(self):
        def faulty_tool():
            raise ValueError("Simulation error in tool")

        self.harness.register_tool("faulty", "Faulty tool", {}, faulty_tool)

        # 1. Success dispatch
        res_ok = self.harness.dispatch_tool("execute_python", {"code": "print(2 + 2)"})
        self.assertTrue(res_ok["success"])
        self.assertIn("4", res_ok["result"]["stdout"])

        # 2. Faulty dispatch
        res_err = self.harness.dispatch_tool("faulty", {})
        self.assertFalse(res_err["success"])
        self.assertIn("Simulation error", res_err["error"])

        # 3. Missing tool
        res_missing = self.harness.dispatch_tool("non_existent_tool", {})
        self.assertFalse(res_missing["success"])

    def test_execute_python_sandbox_timeout_and_error(self):
        # Syntax error handling
        err_res = self.harness.execute_python("def incomplete(")
        self.assertFalse(err_res["success"])
        self.assertGreater(len(err_res["stderr"]), 0)

        # Timeout handling
        timeout_res = self.harness.execute_python("import time; time.sleep(1.0)", timeout_sec=0.1)
        self.assertFalse(timeout_res["success"])
        self.assertIn("timed out", timeout_res["stderr"])

    def test_harness_turn_execution(self):
        turn = self.harness.run_turn("Por favor ejecuta código python para verificar el sistema")
        self.assertTrue(turn.success)
        self.assertGreater(len(turn.content), 0)
        self.assertGreater(len(turn.tool_calls_executed), 0)

        # Verify dispatch_tool propagates inner dict success=False
        res_bad_py = self.harness.dispatch_tool("execute_python", {"code": "import sys; sys.exit(1)"})
        self.assertFalse(res_bad_py["success"])


class TestHermesOrchestrator(unittest.TestCase):

    def setUp(self):
        self.orchestrator = HermesOrchestrator()

    def test_spawn_session(self):
        session = self.orchestrator.spawn_session(
            role="Network Diagnostic Specialist",
            task_prompt="Analizar latencia y jitter de la red"
        )
        self.assertIsInstance(session, SubagentSession)
        self.assertEqual(session.status, "completed")
        self.assertIn("Network Diagnostic Specialist", session.role)
        self.assertIsNotNone(session.result)

    def test_delegate_parallel_and_synthesis(self):
        tasks = [
            {"role": "Radar Subagent", "prompt": "Escanear dispositivos en LAN"},
            {"role": "QoS Subagent", "prompt": "Verificar colas WMM y DSCP"},
            {"role": "Route Subagent", "prompt": "Inspeccionar rutas 0.0.0.0/0"}
        ]
        sessions = self.orchestrator.delegate_parallel(tasks, max_workers=3)
        self.assertEqual(len(sessions), 3)

        synth = self.orchestrator.synthesize_results(sessions)
        self.assertEqual(synth["total_subagents_spawned"], 3)
        self.assertEqual(synth["successful_subagents"], 3)
        self.assertTrue(synth["all_succeeded"])
        self.assertIn("Radar Subagent", synth["synthesized_summary"])

        # Empty session list must not report all_succeeded=True
        empty_synth = self.orchestrator.synthesize_results([])
        self.assertFalse(empty_synth["all_succeeded"])


class TestHermesSelfImprovement(unittest.TestCase):

    def test_memory_distillation_and_persistence(self):
        test_mem_file = os.path.expanduser("~/.netopt_state/test_hermes_memory.json")
        if os.path.exists(test_mem_file):
            try:
                os.remove(test_mem_file)
            except Exception:
                pass

        memory = HermesMemory(memory_path=test_mem_file)
        initial_count = len(memory.state["learned_skills"])

        # Distill new skill
        memory.distill_skill("test_bbr_switch", "loss > 2%", "Switch congestion to BBRv3")
        self.assertEqual(len(memory.state["learned_skills"]), initial_count + 1)

        # Distill same skill again (increments count)
        memory.distill_skill("test_bbr_switch", "loss > 2%", "Switch congestion to BBRv3")
        self.assertEqual(len(memory.state["learned_skills"]), initial_count + 1)

        # Clean up
        if os.path.exists(test_mem_file):
            try:
                os.remove(test_mem_file)
            except Exception:
                pass

    def test_evolution_cycle_dry_run(self):
        engine = HermesSelfImprovementEngine()
        report = engine.run_evolution_cycle(execute=False, run_tests=False)
        self.assertIsInstance(report, EvolutionReport)
        self.assertTrue(report.zero_regressions_verified)
        self.assertFalse(report.tests_executed)
        self.assertIn("Tests omitidos", report.summary)
        self.assertGreater(len(report.actions_taken), 0)
        self.assertIn("Ciclo Hermes", report.summary)

        # Verify exception during run_tests=True sets zero_regressions_verified=False
        with patch("hermes.self_improvement.subprocess.run", side_effect=RuntimeError("Runner crash")):
            rep_fail = engine.run_evolution_cycle(execute=False, run_tests=True)
            self.assertFalse(rep_fail.zero_regressions_verified)

    def test_hermes_memory_atomic_save_and_dry_run_enforced(self):
        import tempfile
        import threading
        from unittest.mock import MagicMock

        with tempfile.TemporaryDirectory() as tmp_dir:
            mem_file = os.path.join(tmp_dir, "mem.json")
            mem = HermesMemory(memory_path=mem_file)
            threads = [
                threading.Thread(target=mem.distill_skill, args=(f"skill_{i}", "t", "a"))
                for i in range(10)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=2.0)
            self.assertTrue(os.path.exists(mem_file))
            reloaded = HermesMemory(memory_path=mem_file)
            names = {s["name"] for s in reloaded.state["learned_skills"]}
            for i in range(10):
                self.assertIn(f"skill_{i}", names)

        mock_hal = MagicMock()
        mock_hal.dry_run = True
        engine = HermesSelfImprovementEngine(hal=mock_hal)
        with patch("hermes.self_improvement.check_duplicate_default_gateways_status", return_value={"has_duplicate_gateways": True}):
            engine.run_evolution_cycle(execute=True, run_tests=False)
            mock_hal.prune_duplicate_default_gateways.assert_called_once_with(execute=False)

    def test_orchestrator_parallel_bounds_and_exception_containment(self):
        from hermes.orchestrator import HermesOrchestrator, SubagentSession

        orch = HermesOrchestrator()
        self.assertEqual(orch.delegate_parallel([], max_workers=4), [])

        with self.assertRaises(ValueError):
            orch.delegate_parallel([], max_workers=0)
        with self.assertRaises(ValueError):
            orch.delegate_parallel([], max_workers=True)
        with self.assertRaises(ValueError):
            orch.delegate_parallel([{"role": "", "prompt": "Check"}], max_workers=2)
        with self.assertRaises(ValueError):
            orch.spawn_session("", "Check")

        with patch("hermes.orchestrator.HermesAgentHarness.run_turn", side_effect=RuntimeError("turn boom Bearer secret_tok_123\nline2")):
            sess = orch.spawn_session("Audit", "Check")
            self.assertEqual(sess.status, "failed")
            self.assertIsNotNone(sess.completed_at)
            self.assertIn("turn boom", sess.result.error)
            self.assertNotIn("secret_tok_123", sess.result.error)
            self.assertNotIn("\n", sess.result.error)

        # H-03: Running sessions must never be evicted when exceeding MAX_RETAINED_SESSIONS
        orch2 = HermesOrchestrator()
        for i in range(205):
            st = "running" if i < 5 else "completed"
            orch2._record_session(SubagentSession(session_id=f"s-{i}", role="r", task_prompt="p", status=st))
        running = orch2.list_sessions(status="running")
        self.assertEqual(len(running), 5)
        self.assertIsNotNone(orch2.get_session("s-0"))
        self.assertIsNone(orch2.get_session("s-5"))

    def test_execute_python_rejects_invalid_timeout_and_bounds_output(self):
        """H-10: execute_python rejects NaN/bool/empty code and truncates excessive output."""
        from hermes.harness import HermesAgentHarness
        h = HermesAgentHarness()
        r_nan = h.execute_python("print(1)", timeout_sec=float("nan"))
        self.assertFalse(r_nan["success"])
        self.assertIn("finite", r_nan["stderr"])

        r_bool = h.execute_python("print(1)", timeout_sec=True)
        self.assertFalse(r_bool["success"])

        r_empty = h.execute_python("   ")
        self.assertFalse(r_empty["success"])

        r_big = h.execute_python("print('A' * 20000)")
        self.assertTrue(r_big["success"])
        self.assertLessEqual(len(r_big["stdout"]), h.MAX_OUTPUT_CHARS)

    def test_orchestrator_propagates_default_config_and_synthesizes_errors(self):
        from hermes.orchestrator import HermesOrchestrator
        from hermes.harness import HermesHarnessConfig, HarnessTurnResult
        cfg = HermesHarnessConfig(provider="openai", model="gpt-4o-mini", timeout_sec=12.5, max_tokens=200)
        orch = HermesOrchestrator(default_config=cfg)
        with patch("hermes.orchestrator.HermesAgentHarness.run_turn", side_effect=RuntimeError("boom")):
            sess = orch.spawn_session("Audit", "Check")
            self.assertEqual(sess.status, "failed")
        with patch("hermes.orchestrator.HermesAgentHarness") as mock_h:
            mock_h.return_value.run_turn.return_value = HarnessTurnResult(content="ok", success=True)
            orch.spawn_session("Net", "Check")
            passed_cfg = mock_h.call_args.kwargs["config"]
            self.assertEqual(passed_cfg.timeout_sec, 12.5)
            self.assertEqual(passed_cfg.max_tokens, 200)
        synth = orch.synthesize_results([sess])
        self.assertIn("Error:", synth["synthesized_summary"])

    def test_hermes_memory_handles_relative_path_and_corrupt_non_dict_json(self):
        import tempfile
        from hermes.self_improvement import HermesMemory
        with tempfile.TemporaryDirectory() as tmpd:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmpd)
                with open("rel_mem.json", "w", encoding="utf-8") as f:
                    f.write("[]")
                mem = HermesMemory(memory_path="rel_mem.json")
                self.assertIn("learned_skills", mem.state)
                self.assertIsInstance(mem.state["learned_skills"], list)
            finally:
                os.chdir(orig_cwd)


if __name__ == "__main__":
    unittest.main()

