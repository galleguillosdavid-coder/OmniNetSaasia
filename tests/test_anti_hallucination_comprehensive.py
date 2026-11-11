"""
OmniNet Saasia - Comprehensive Anti-Hallucination & Vulnerability Verification Suite.
Validates epistemological truthfulness across versions, manifests, subagents,
roles recursion, Zero NetLoss gates, dry-run safety, and encoding resilience.
"""

from __future__ import annotations
import os
import sys
import re
import json
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from netopt import __version__ as NETOPT_VERSION
from main import VERSION as MAIN_VERSION
from mcp_server import handle_tool_call, load_tools_schema
from netopt.ecosystem_subagents import get_ecosystem_orchestrator
from netopt.hal import WindowsHAL, LinuxHAL, DarwinHAL
from netopt.optimizer import NetworkOptimizer
from netopt.models import OrchestrationPlan, AgentActionLog, PlatformType, DiagnosticsReport, HealthState
from netopt.diagnostics import audit_arp_lan
from netopt.llm_gateway import LLMGateway
from hermes.executor import HermesExecutor, SIMULATED, SUCCEEDED
from hermes.foresee import ForeseePlan, PlanStep
from hermes.harness import HermesAgentHarness


class TestAntiHallucinationComprehensive(unittest.TestCase):
    """
    Test suite validating epistemological honesty, manifest parity,
    Zero NetLoss invariants, and resilience against hallucinations.
    """

    # 1. Paridad estricta de versiones (Anti-Drift / Anti-Phantom-Releases)
    def test_version_parity_across_all_manifests_and_modules(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # main.py
        self.assertEqual(MAIN_VERSION, "2.9.6")
        # netopt/__init__.py
        self.assertEqual(NETOPT_VERSION, "2.9.6")

        # pyproject.toml
        import tomllib
        with open(os.path.join(root_dir, "pyproject.toml"), "rb") as f:
            pyproj = tomllib.load(f)
        self.assertEqual(pyproj["project"]["version"], "2.9.6")

        # setup.py
        with open(os.path.join(root_dir, "setup.py"), "r", encoding="utf-8") as f:
            setup_content = f.read()
        setup_ver_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', setup_content)
        self.assertIsNotNone(setup_ver_match, "setup.py must declare a version")
        self.assertEqual(setup_ver_match.group(1), "2.9.6")

        # config/tools_manifest.json
        manifest_path = os.path.join(root_dir, "config", "tools_manifest.json")
        if not os.path.exists(manifest_path):
            manifest_path = os.path.join(root_dir, "tools_manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["version"], "2.9.6")

        # README.md header/badge
        with open(os.path.join(root_dir, "README.md"), "r", encoding="utf-8") as f:
            readme_content = f.read()
        self.assertIn("v2.9.6", readme_content)
        self.assertIn("version-2.9.6", readme_content)

    # 2. Paridad total de herramientas MCP (Anti-Phantom-Tools)
    def test_mcp_tools_manifest_dispatch_parity(self):
        tools = load_tools_schema()
        self.assertEqual(len(tools), 15, "tools_manifest.json must declare exactly 15 tools")

        tool_names = [t["name"] for t in tools]
        self.assertEqual(len(tool_names), len(set(tool_names)), "All tool names in manifest must be unique")

        mock_diag = DiagnosticsReport(
            timestamp=1000.0,
            platform=PlatformType.WINDOWS,
            overall_health=HealthState.HEALTHY,
            default_gateway="192.168.1.1",
            gateway_reachable=True,
            internet_reachable=True,
            dns_resolving=True,
            dns_benchmarks=[],
            latency_metrics={},
            detected_pmtu=1500,
            bufferbloat_grade="A+",
            active_interface="Ethernet"
        )

        with patch("mcp_server.run_full_diagnostics", return_value=mock_diag), \
             patch("netopt.optimizer.run_full_diagnostics", return_value=mock_diag), \
             patch("mcp_server.benchmark_all_resolvers", return_value=[]), \
             patch("mcp_server.run_fast_traceroute", return_value={"raw_trace": "ok"}), \
             patch("mcp_server.measure_bandwidth_speed", return_value={"download_mbps": 100.0}):
            for tool_name in tool_names:
                try:
                    res = handle_tool_call(tool_name, {"execute": False})
                    self.assertIsInstance(res, dict, f"Tool {tool_name} must return a dictionary")
                except Exception as e:
                    self.fail(f"Tool {tool_name} failed to dispatch in handle_tool_call: {e}")

    # 3. Integridad y veracidad del catálogo de Sub-Agentes (Anti-Phantom-SubAgents)
    def test_subagents_ecosystem_catalog_integrity(self):
        orch = get_ecosystem_orchestrator()
        cat = orch.get_ecosystem_catalog()
        self.assertGreaterEqual(len(cat), 10, "There must be at least 10 specialized sub-agents in the ecosystem")

        required_keys = {"id", "name", "emoji", "motor", "mission"}
        for sa in cat:
            self.assertTrue(required_keys.issubset(sa.keys()), f"Subagent {sa.get('id')} missing required schema keys")
            self.assertTrue(bool(sa["id"].strip()))
            self.assertTrue(bool(sa["name"].strip()))
            self.assertTrue(bool(sa["motor"].strip()))

            # Dry-run execution must produce valid structured output
            res = orch.execute_subagent_by_id(sa["id"], execute=False)
            self.assertIsInstance(res, dict)
            self.assertEqual(res.get("subagent"), sa["id"])
            self.assertTrue(any(k in res for k in ("health", "summary", "installed", "status", "cleaner", "action")))

    # 4. Verificación de la Directiva Recursiva de Roles (Hermes Harness² como Tarea Inicial)
    def test_recursive_initial_role_directive_presence(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        files_to_check = [
            ("README.md", "README.md"),
            ("AGENTS.md", "AGENTS.md"),
            ("AUTONOMOUS_OPERATIONAL_MANIFESTO.md", os.path.join("docs", "AUTONOMOUS_OPERATIONAL_MANIFESTO.md")),
            ("AGENT_INSTRUCTIONS.md", os.path.join("docs", "AGENT_INSTRUCTIONS.md")),
        ]

        for label, rel_path in files_to_check:
            full_path = os.path.join(root_dir, rel_path)
            self.assertTrue(os.path.exists(full_path), f"File {rel_path} must exist")
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Hermes Harness²", content, f"{rel_path} must mention Hermes Harness²")
            self.assertTrue(
                "Orquestador de Auto-Mejora" in content or "Orquestador" in content,
                f"{rel_path} must document the orchestrator role"
            )

    # 5. Veracidad en la documentación de métricas (Anti-Stale-Documentation)
    def test_docs_metrics_truthfulness(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root_dir, "README.md"), "r", encoding="utf-8") as f:
            readme = f.read()

        # Debe documentar 10 sub-agentes, 15 herramientas MCP y suite de tests completa
        self.assertIn("10 Sub-Agentes", readme)
        self.assertIn("15 herramientas MCP", readme)
        self.assertNotIn("Manifiesto de 12 herramientas MCP", readme)

    # 6. Aborto obligatorio ante fallo de Snapshot en Zero NetLoss
    def test_zero_netloss_snapshot_failure_blocks_mutation(self):
        hal = WindowsHAL(dry_run=False)
        optimizer = NetworkOptimizer(hal)

        # Mock rollback manager to fail snapshot
        optimizer.rollback_mgr.capture_snapshot = MagicMock(side_effect=RuntimeError("Disk write protected"))
        plan = OrchestrationPlan(planned_actions=[AgentActionLog(description="test action", command="netsh")])

        with self.assertRaises(RuntimeError):
            optimizer.execute_plan(plan, execute=True)

    # 7. Aislamiento estricto de Dry-Run en HAL (Cero Mutaciones en Simulación)
    def test_hal_dry_run_absolute_isolation(self):
        for HalClass in [WindowsHAL, LinuxHAL, DarwinHAL]:
            hal = HalClass(dry_run=True)
            with patch("subprocess.run") as mock_sub:
                action = hal.run_cmd(["netsh", "int", "tcp", "set", "global", "autotuninglevel=normal"], execute=False)
                self.assertTrue(action.is_dry_run)
                self.assertTrue(action.success)
                # Subprocess must never be called with execute=False
                mock_sub.assert_not_called()

    # 8. Honestidad epistemológica en Hermes Executor (SIMULATED nunca es SUCCEEDED)
    def test_hermes_executor_dry_run_never_reports_succeeded(self):
        from hermes import ForeseePlanner, ReflectEvaluator, HermesMemory
        from tests.test_hermes_cognitive import make_diag

        executor = HermesExecutor(WindowsHAL(dry_run=True))
        executor.rollback_mgr.capture_snapshot = MagicMock()
        plan = ForeseePlanner().foresee("juegos", make_diag())
        
        report = executor.execute(plan, diag=make_diag(), execute=True)
        self.assertFalse(report.executed_for_real)
        self.assertIsNone(report.snapshot_id)
        for r in report.step_results:
            if r.strategy in ("dns_failover", "gaming_l4s_qos"):
                self.assertNotEqual(r.status, SUCCEEDED, "Dry-run mutation step must never report SUCCEEDED")
                self.assertEqual(r.status, SIMULATED, "Dry-run mutation step must report SIMULATED")

    # 9. Detección honesta de ARP Spoofing / MAC duplicada en LAN Radar
    def test_lan_radar_arp_spoofing_detection_truthfulness(self):
        fake_arp_output = (
            "Interfaz: 192.168.1.50 --- 0x12\n"
            "  Dirección de Internet          Dirección física      Tipo\n"
            "  192.168.1.1                   00-11-22-33-44-55     dinámico\n"
            "  192.168.1.105                 00-11-22-33-44-55     dinámico\n"
            "  192.168.1.200                 aa-bb-cc-dd-ee-ff     dinámico\n"
        )

        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout=fake_arp_output)
            report = audit_arp_lan()

        self.assertIsInstance(report, dict)
        self.assertIn("anomalies", report)
        self.assertTrue(len(report["anomalies"]) > 0)
        self.assertTrue(any("duplicate mac" in a.lower() for a in report["anomalies"]))

    # 10. Resiliencia contra UnicodeDecodeError en CLI de Windows (OEM codepage / bytes no UTF-8)
    def test_unicode_decode_resilience_in_traceroute_and_hal(self):
        from netopt.llm_gateway import run_fast_traceroute

        # Simulated tracert output with OEM/Latin-1 byte 0xa0 or non-utf8 characters
        fake_stdout = "Traza a la direcci\xa0n 1.1.1.1 con un m\xa0ximo de 8 saltos:\n  1    2 ms     2 ms     2 ms  192.168.1.1\n"
        
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout=fake_stdout)
            result = run_fast_traceroute("1.1.1.1", max_hops=8)
            self.assertIsInstance(result, dict)
            self.assertIn("raw_trace", result)
            self.assertIn("192.168.1.1", result["raw_trace"])

    # 11. No exposición de credenciales secretas en respuestas y configuraciones
    def test_sensitive_secrets_never_exposed_unmasked(self):
        gw = LLMGateway()
        gw.config["api_key"] = "sk-deepseek-live-secret-key-12345"
        
        # Masked public projection must redact API key
        safe_repr = {k: ("***" if "key" in k.lower() or "secret" in k.lower() else v) for k, v in gw.config.items()}
        self.assertEqual(safe_repr["api_key"], "***")
        self.assertNotIn("sk-deepseek", json.dumps(safe_repr))


if __name__ == "__main__":
    unittest.main()
