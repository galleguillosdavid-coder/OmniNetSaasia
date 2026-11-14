"""
Tests for the FastAPI application (docs/Auditorias/3.md §245-285).
Verifies route preservation, Pydantic schema validation, and Zero NetLoss safety.
"""

import warnings
import unittest
from unittest.mock import patch, MagicMock

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from fastapi.testclient import TestClient

from netopt.fastapi_app import create_app
from main import get_dashboard_html


class TestFastAPIApp(unittest.TestCase):
    """Verifies FastAPI REST API endpoints and compatibility with OmniNet."""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app(dashboard_html_provider=get_dashboard_html)
        cls.client = TestClient(cls.app)

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["version"], "2.9.6")
        self.assertEqual(data["service"], "OmniNet AI Agent Pro")

    def test_dashboard_html_endpoint(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<!DOCTYPE html>", resp.text)
        self.assertIn("OmniNet", resp.text)
        self.assertIn("Centro de Herramientas", resp.text)
        self.assertIn("toolLanRadar", resp.text)
        self.assertIn("toolWifiAudit", resp.text)
        self.assertIn("toolDnsBench", resp.text)
        self.assertIn("toolSocketsInspect", resp.text)
        self.assertIn("toolTriageRepair", resp.text)


    def test_system_status_endpoint(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["version"], "2.9.6")
        self.assertIn("platform", data)
        self.assertIn("admin_elevated", data)

    def test_subagents_list_endpoint(self):
        resp = self.client.get("/api/subagents")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 10)

    def test_chat_endpoint_valid_and_validation_error(self):
        # Valid chat request
        resp = self.client.post("/api/chat", json={
            "message": "Hola, ¿cómo optimizar mi conexión?",
            "history": [],
            "language_mode": "simple"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("reply", data)

        # Invalid chat request (empty message -> Pydantic 422 Unprocessable Entity)
        err_resp = self.client.post("/api/chat", json={"message": ""})
        self.assertEqual(err_resp.status_code, 422)

    def test_optimize_endpoint_dry_run_safety(self):
        resp = self.client.post("/api/optimize", json={"execute": False, "profile": "balanced"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["applied"])
        self.assertIn("plan_id", data)

    def test_subagent_run_endpoint_dry_run(self):
        resp = self.client.post("/api/subagents/run", json={"id": "redes", "execute": False})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("subagent"), "network")

    def test_payload_too_large_rejection(self):
        # Header indicating content > 1MB
        headers = {"content-length": str(1024 * 1024 + 10)}
        resp = self.client.post("/api/chat", json={"message": "test"}, headers=headers)
        self.assertEqual(resp.status_code, 413)

    def test_device_maintain_endpoint_dry_run(self):
        resp = self.client.post("/api/device/maintain", json={"execute": False})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data.get("executed"))
        self.assertTrue(data.get("verified"))
        self.assertIn("actions_executed", data)

    def test_openapi_schema_integrity(self):
        resp = self.client.get("/openapi.json")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("info", {}).get("title"), "OmniNet AI Agent Pro API")
        self.assertEqual(data.get("info", {}).get("version"), "2.9.6")
        paths = data.get("paths", {})
        self.assertGreaterEqual(len(paths), 25)
        self.assertIn("/health", paths)
        self.assertIn("/api/subagents", paths)
        self.assertIn("/api/chat", paths)
        self.assertIn("/api/optimize", paths)
        self.assertIn("/api/device/maintain", paths)

    def test_repair_endpoint_dry_run(self):
        resp = self.client.post("/api/repair", json={"execute": False})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data["applied"])
        self.assertIn("failure_type", data)
        self.assertIn("triage_logs", data)
        self.assertIn("actions", data)

    def test_rollback_endpoint_dry_run(self):
        resp = self.client.post("/api/rollback", json={"snapshot_id": "test_snap_001", "execute": False})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["snapshot_id"], "test_snap_001")
        self.assertFalse(data["applied"])
        self.assertIn("logs", data)

    def test_tasks_trigger_endpoint_dry_run_safety(self):
        resp = self.client.post("/api/tasks/trigger", json={"execute": False})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("tasks_executed", data)
        self.assertIn("generation", data)
        self.assertIn("concise_summary", data)
        for t in data["tasks_executed"]:
            self.assertIn(t.get("status"), ("SIMULATED", "SCHEDULED"))

    def test_sentinel_endpoints_contract_and_trigger(self):
        # 1. GET /api/sentinel/status
        resp_status = self.client.get("/api/sentinel/status")
        self.assertEqual(resp_status.status_code, 200)
        data = resp_status.json()
        self.assertIn("enabled", data)
        self.assertIn("running", data)
        self.assertIn("latency_threshold_ms", data)

        # 2. POST /api/sentinel/toggle (disable)
        resp_toggle = self.client.post("/api/sentinel/toggle", json={"enabled": False})
        self.assertEqual(resp_toggle.status_code, 200)
        self.assertFalse(resp_toggle.json()["enabled"])

        # 3. POST /api/sentinel/trigger
        resp_trigger = self.client.post("/api/sentinel/trigger")
        self.assertEqual(resp_trigger.status_code, 200)
        t_data = resp_trigger.json()
        self.assertTrue(t_data["triggered"])
        self.assertIn("had_incident", t_data)
        self.assertIn("status", t_data)

    def test_invalid_and_negative_content_length_rejected(self):
        resp_bad = self.client.post("/api/chat", json={"message": "test"}, headers={"content-length": "not-a-number"})
        self.assertEqual(resp_bad.status_code, 400)
        resp_neg = self.client.post("/api/chat", json={"message": "test"}, headers={"content-length": "-10"})
        self.assertEqual(resp_neg.status_code, 400)

    def test_sanitize_llm_config_short_and_long_keys(self):
        from netopt.fastapi_app import _sanitize_llm_config
        short_sanitized = _sanitize_llm_config({"provider": "openai", "api_key": "sk-123"})
        self.assertTrue(short_sanitized["api_key_configured"])
        self.assertEqual(short_sanitized["api_key_masked"], "****")
        self.assertNotIn("api_key", short_sanitized)

        long_sanitized = _sanitize_llm_config({"provider": "openai", "api_key": "sk-1234567890abcdef"})
        self.assertTrue(long_sanitized["api_key_configured"])
        self.assertEqual(long_sanitized["api_key_masked"], "sk-1...def")
        self.assertNotIn("api_key", long_sanitized)

    def test_llm_config_pydantic_validation(self):
        resp_bad = self.client.post("/api/llm/config", json={"temperature": 9.9})
        self.assertEqual(resp_bad.status_code, 422)

    def test_is_local_llm_url_prevents_ssrf_bypass(self):
        from netopt.llm_gateway import _is_local_llm_url
        self.assertTrue(_is_local_llm_url("http://localhost:11434/v1"))
        self.assertTrue(_is_local_llm_url("http://127.0.0.1:8080/v1"))
        self.assertTrue(_is_local_llm_url("http://[::1]:11434/v1"))
        self.assertFalse(_is_local_llm_url("https://evil.com/?localhost"))
        self.assertFalse(_is_local_llm_url("https://127.0.0.1.attacker.com/v1"))
        self.assertFalse(_is_local_llm_url("https://localhost.attacker.com/v1"))

    def test_rollback_load_snapshot_prevents_path_traversal(self):
        from netopt.rollback import RollbackManager
        mgr = RollbackManager()
        self.assertIsNone(mgr.load_snapshot("../../etc/passwd"))
        self.assertIsNone(mgr.load_snapshot("..\\..\\secret"))
        self.assertIsNone(mgr.load_snapshot(""))
        self.assertIsNone(mgr.load_snapshot("sub/snap_001"))

    def test_hal_linux_and_darwin_input_validation_blocks_injection(self):
        from netopt.hal import LinuxHAL, DarwinHAL
        lhal = LinuxHAL(dry_run=True)
        with self.assertRaises(ValueError):
            lhal.renew_dhcp_lease("eth0; rm -rf /")
        with self.assertRaises(ValueError):
            lhal.renew_dhcp_lease("$(whoami)")
        ok_log = lhal.renew_dhcp_lease("eth0", execute=False)
        self.assertTrue(ok_log.is_dry_run)

        dhal = DarwinHAL(dry_run=True)
        with self.assertRaises(ValueError):
            dhal.set_dns_servers("Wi-Fi; id", ["1.1.1.1"])
        with self.assertRaises(ValueError):
            dhal.set_dns_servers("Wi-Fi", ["not-an-ip"])

    def test_optimizer_execute_plan_dry_run_hal_reports_simulated(self):
        from netopt.hal import WindowsHAL
        from netopt.optimizer import NetworkOptimizer
        from netopt.models import OrchestrationPlan, AgentActionLog
        opt = NetworkOptimizer(WindowsHAL(dry_run=True))
        plan = OrchestrationPlan(planned_actions=[AgentActionLog(description="test", command="netsh")])
        ok, logs = opt.execute_plan(plan, execute=True)
        self.assertTrue(ok)
        self.assertEqual(plan.status, "simulated")
        self.assertTrue(any("DRY-RUN SIMULATION" in l for l in logs))

    def test_auto_sentinel_stop_event_wakes_immediately(self):
        from netopt.auto_trigger import AutoSentinel
        s = AutoSentinel(interval_sec=60, enabled=False)
        s.start()
        self.assertTrue(s.running)
        s.stop()
        s._thread.join(timeout=1.0)
        self.assertFalse(s.running)
        self.assertFalse(s._thread.is_alive())

    def test_autonomous_scheduler_stop_event_wakes_immediately(self):
        from netopt.autonomous_scheduler import AutonomousTaskScheduler
        sched = AutonomousTaskScheduler(interval_sec=600, auto_execute=False)
        with patch.object(sched, "discover_and_schedule_cycle", return_value={}):
            sched.start()
            self.assertTrue(sched.running)
            sched.stop()
            sched._thread.join(timeout=1.0)
            self.assertFalse(sched.running)
            self.assertFalse(sched._thread.is_alive())

    def test_mcp_server_jsonrpc_error_and_bounds_handling(self):
        from mcp_server import process_jsonrpc_line, handle_tool_call
        self.assertEqual(process_jsonrpc_line("{bad json", [])["error"]["code"], -32700)
        self.assertEqual(process_jsonrpc_line("[1, 2, 3]", [])["error"]["code"], -32600)
        self.assertEqual(process_jsonrpc_line('{"jsonrpc":"2.0","id":1,"method":"unknown"}', [])["error"]["code"], -32601)
        self.assertIsNone(process_jsonrpc_line('{"jsonrpc":"2.0","method":"notifications/initialized"}', []))
        res = handle_tool_call("network_persistent_monitor", {"action": "status", "poll_interval_sec": 999999})
        self.assertEqual(res["poll_interval_sec"], 86400)

    def test_ecosystem_subagent_dispatch_default_dry_run(self):
        from netopt.ecosystem_subagents import EcosystemOrchestrator
        orch = EcosystemOrchestrator()
        res_unk = orch.execute_subagent_by_id("unknown_agent")
        self.assertFalse(res_unk["success"])
        res_net = orch.execute_subagent_by_id("redes")
        self.assertEqual(res_net["subagent"], "network")
        self.assertFalse(res_net.get("executed", False))

    def test_pmtu_endpoint_rejects_invalid_target_flag_injection(self):
        resp_flag = self.client.get("/api/pmtu", params={"target": "-t"})
        self.assertEqual(resp_flag.status_code, 400)
        resp_bad = self.client.get("/api/pmtu", params={"target": "1.1.1.1; whoami"})
        self.assertEqual(resp_bad.status_code, 400)

    def test_network_daemon_stop_event_wakes_immediately(self):
        import threading
        from unittest.mock import patch
        from netopt.persistence import NetworkDaemon

        daemon = NetworkDaemon(poll_interval_sec=60)
        first_cycle = threading.Event()

        def fake_check():
            first_cycle.set()
            return {"status": "HEALTHY"}

        with patch.object(daemon, "check_and_heal_once", side_effect=fake_check):
            thread = threading.Thread(target=daemon.run_loop, daemon=True)
            thread.start()
            self.assertTrue(first_cycle.wait(timeout=1.0))
            daemon.stop()
            thread.join(timeout=1.0)
            self.assertFalse(thread.is_alive())
            self.assertFalse(daemon.running)

    def test_repair_engine_dry_run_hal_forces_simulated_and_handles_unknown_tier(self):
        from unittest.mock import MagicMock
        from netopt.repair import NetworkRepairEngine

        mock_hal = MagicMock()
        mock_hal.dry_run = True
        fake_log = MagicMock(is_dry_run=True)
        mock_hal.flush_dns_cache.return_value = fake_log

        engine = NetworkRepairEngine(hal=mock_hal)
        self.assertEqual(engine.execute_triage_repair("UNKNOWN_TIER", execute=True), [])
        acts = engine.execute_triage_repair("L3_PMTU_BLACKHOLE", execute=True)
        self.assertTrue(len(acts) >= 1)
        for call in mock_hal.run_cmd.call_args_list:
            self.assertFalse(call.kwargs.get("execute"))
        mock_hal.flush_dns_cache.assert_called_once_with(execute=False)

    def test_http_client_adapter_rejects_invalid_scheme_and_delegates(self):
        from netopt.adapters import HttpClientAdapter

        code_bad, body_bad = HttpClientAdapter.get_json("file:///etc/passwd")
        self.assertEqual(code_bad, 400)
        self.assertIn("Unsupported", body_bad.get("error", ""))

        code_bytes, data_bytes = HttpClientAdapter.get_bytes("ftp://example.com/a")
        self.assertEqual(code_bytes, 400)
        self.assertEqual(data_bytes, b"")
        self.assertEqual(HttpClientAdapter._bound_timeout(-5), 0.1)
        self.assertEqual(HttpClientAdapter._bound_timeout(999), 120.0)

    def test_telemetry_validates_target_and_rejects_non_http_collector(self):
        from netopt.telemetry import run_real_device_empirical_probes, dispatch_global_device_telemetry

        with self.assertRaises(ValueError):
            run_real_device_empirical_probes(target="1.1.1.1; whoami")

        res = dispatch_global_device_telemetry(
            empirical_report={"device_id": "abc", "platform": "windows"},
            collector_url="file:///etc/passwd",
        )
        self.assertFalse(res["success"])
        self.assertIn("Unsupported", res["error"])

    def test_elevation_windows_list2cmdline_and_posix_fallback(self):
        import sys
        from unittest.mock import patch, MagicMock
        import netopt.elevation as elev

        fake_shell32 = MagicMock()
        fake_shell32.ShellExecuteW.return_value = 42
        with patch.object(sys, "argv", ["main.py", "--arg", 'val with "quotes"']), \
             patch.object(sys, "frozen", False, create=True), \
             patch.object(elev.ctypes, "windll", MagicMock(shell32=fake_shell32), create=True), \
             patch.object(sys, "exit") as mock_exit:
            elev._elevate_windows()
            called_args = fake_shell32.ShellExecuteW.call_args[0][3]
            self.assertIn(r'\"quotes\"', called_args)
            mock_exit.assert_called_once_with(0)

        with patch("shutil.which", return_value=None):
            with self.assertRaises(PermissionError):
                elev._elevate_posix()

    def test_cli_daemon_bounds_and_repair_json_serialization(self):
        import io
        import contextlib
        from unittest.mock import patch, MagicMock
        import netopt.cli as cli

        with patch("netopt.cli.NetworkDaemon") as mock_daemon_cls:
            mock_daemon = MagicMock()
            mock_daemon_cls.return_value = mock_daemon
            rc = cli.main(["daemon", "--interval", "-5", "--cycles", "0"])
            self.assertEqual(rc, 0)
            self.assertEqual(mock_daemon_cls.call_args.kwargs["poll_interval_sec"], 5)
            mock_daemon.run_loop.assert_called_once()
            self.assertEqual(mock_daemon.run_loop.call_args.kwargs["max_cycles"], 1)

        buf = io.StringIO()
        with patch("netopt.cli.NetworkRepairEngine") as mock_rep_cls, \
             contextlib.redirect_stdout(buf):
            mock_rep = MagicMock()
            mock_rep.diagnose_and_triage.return_value = ("HEALTHY", ["OK"])
            mock_rep.execute_triage_repair.return_value = []
            mock_rep_cls.return_value = mock_rep
            rc2 = cli.main(["repair", "--json"])
            self.assertEqual(rc2, 0)
            self.assertIn('"failure_type": "HEALTHY"', buf.getvalue())


if __name__ == "__main__":
    unittest.main()
