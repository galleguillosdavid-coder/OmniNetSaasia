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
        self.assertGreater(len(report.actions_taken), 0)
        self.assertIn("Ciclo Hermes", report.summary)


if __name__ == "__main__":
    unittest.main()

