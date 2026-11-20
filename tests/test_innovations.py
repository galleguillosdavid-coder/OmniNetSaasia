import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from netopt.fastapi_app import create_app
from netopt.keystore import SovereignKeystore
from netopt.models import NetworkInterfaceInfo
from netopt.quarantine import QuarantineManager, find_duplicate_files
from netopt.telemetry import get_impact_summary
from netopt.virtual_mesh import MAX_MESH_PEERS, VirtualMeshManager, evaluate_multipath_failover


class TestInnovations(unittest.TestCase):
    def test_sovereign_keystore_encrypts_and_rotates_identity(self):
        with tempfile.TemporaryDirectory() as tmpd:
            ks_path = os.path.join(tmpd, "ks.json")
            ks = SovereignKeystore(keystore_path=ks_path, passphrase="test-passphrase-123")
            ident1 = ks.ensure_device_identity()
            self.assertTrue(ident1["did"].startswith("did:omninet:ed25519:"))
            ks.set_secret("mesh_psk", "super_secret_value")

            with open(ks_path, "r", encoding="utf-8") as f:
                raw = f.read()
            self.assertNotIn("super_secret_value", raw)

            ks2 = SovereignKeystore(keystore_path=ks_path, passphrase="test-passphrase-123")
            self.assertEqual(ks2.get_secret("mesh_psk"), "super_secret_value")
            self.assertEqual(ks2.ensure_device_identity()["did"], ident1["did"])

            ident2 = ks2.rotate_device_keys()
            self.assertNotEqual(ident2["public_key_hex"], ident1["public_key_hex"])

    def test_virtual_mesh_peer_limits_and_multipath_failover(self):
        with tempfile.TemporaryDirectory() as tmpd:
            ks = SovereignKeystore(keystore_path=os.path.join(tmpd, "ks.json"), passphrase="p")
            mesh = VirtualMeshManager(keystore=ks)
            for i in range(1, MAX_MESH_PEERS + 1):
                mesh.register_peer(f"pc-{i}", f"pub-{i}", f"10.77.0.{i + 1}")

            with self.assertRaises(ValueError):
                mesh.register_peer("pc-6", "pub-6", "10.77.0.10")
            with self.assertRaises(ValueError):
                mesh.register_peer("pc-1", "pub-1", "10.77.0.3")  # IP already used by pc-2

            st = mesh.get_status()
            self.assertEqual(st["peers_count"], MAX_MESH_PEERS)
            self.assertIn("tun_driver", st)

            mock_hal = MagicMock()
            mock_hal.dry_run = True
            mock_hal.get_interfaces.return_value = [
                NetworkInterfaceInfo(name="Wi-Fi", is_up=True, is_loopback=False),
                NetworkInterfaceInfo(name="Ethernet", is_up=True, is_loopback=False),
            ]
            res = evaluate_multipath_failover(hal=mock_hal, primary_degraded=True, execute=True)
            self.assertTrue(res["failover_available"])
            self.assertTrue(res["simulated"])
            self.assertFalse(res["switched"])

    def test_quarantine_restore_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmpd:
            qdir = os.path.join(tmpd, "q")
            work = os.path.join(tmpd, "work")
            os.makedirs(work, exist_ok=True)
            f1 = os.path.join(work, "a.bin")
            f2 = os.path.join(work, "b.bin")
            payload = b"X" * 2048
            with open(f1, "wb") as fp:
                fp.write(payload)
            with open(f2, "wb") as fp:
                fp.write(payload)

            dedup = find_duplicate_files(work, min_size_bytes=1024)
            self.assertEqual(len(dedup["duplicate_groups"]), 1)
            self.assertEqual(dedup["reclaimable_bytes"], 2048)

            qm = QuarantineManager(quarantine_dir=qdir)
            sim = qm.quarantine_file(f1, reason="duplicate", execute=False)
            self.assertTrue(sim["simulated"])
            self.assertTrue(os.path.exists(f1))

            moved = qm.quarantine_file(f1, reason="duplicate", execute=True)
            self.assertFalse(moved["simulated"])
            self.assertFalse(os.path.exists(f1))

            restored = qm.restore_file(moved["item_id"], execute=True)
            self.assertTrue(restored["success"])
            self.assertTrue(os.path.exists(f1))

    def test_impact_summary_and_fastapi_endpoints(self):
        with tempfile.TemporaryDirectory() as tmpd:
            mpath = os.path.join(tmpd, "metrics.json")
            with open(mpath, "w", encoding="utf-8") as f:
                json.dump([
                    {"ping_avg_ms": 50.0, "jitter_ms": 3.0, "bufferbloat_grade": "B"},
                    {"ping_avg_ms": 28.0, "jitter_ms": 0.4, "bufferbloat_grade": "A+"},
                ], f)
            imp = get_impact_summary(metrics_path=mpath)
            self.assertTrue(imp["has_comparison"])
            self.assertEqual(imp["ping_delta_ms"], -22.0)
            self.assertTrue(imp["improved"])

        client = TestClient(create_app())
        self.assertEqual(client.get("/api/metrics/impact").status_code, 200)
        self.assertEqual(client.get("/api/mesh/status").status_code, 200)
        self.assertEqual(client.get("/api/quarantine").status_code, 200)
        self.assertEqual(client.get("/api/defense/audit").status_code, 200)
        r_url = client.post("/api/defense/check-url", json={"url": "http://g00gle-login.xyz"})
        self.assertEqual(r_url.status_code, 200)
        self.assertIn(r_url.json()["verdict"], ("SUSPICIOUS", "DANGEROUS"))

    def test_ai_defense_url_and_endpoint_audit(self):
        from netopt.ai_defense import inspect_url_or_domain, audit_ai_threats
        self.assertEqual(inspect_url_or_domain("https://google.com")["verdict"], "SAFE")
        self.assertEqual(inspect_url_or_domain("https://xn--pple-43d.com")["verdict"], "SUSPICIOUS")
        self.assertEqual(inspect_url_or_domain("http://192.168.1.50/login")["verdict"], "DANGEROUS")
        self.assertEqual(inspect_url_or_domain("https://microsft.com")["verdict"], "SUSPICIOUS")
        leet = inspect_url_or_domain("http://g00gle-login.xyz")
        self.assertEqual(leet["verdict"], "DANGEROUS")
        self.assertGreaterEqual(leet["risk_score"], 80)

        fake_conn = MagicMock()
        fake_conn.status = "ESTABLISHED"
        fake_conn.raddr = MagicMock(ip="203.0.113.5", port=4444)
        fake_conn.laddr = MagicMock(ip="192.168.1.10", port=51234)
        fake_conn.pid = 9999
        fake_proc = MagicMock()
        fake_proc.name.return_value = "payload.exe"
        fake_proc.exe.return_value = r"C:\Users\User\AppData\Local\Temp\payload.exe"

        with patch("psutil.net_connections", return_value=[fake_conn]), \
             patch("psutil.Process", return_value=fake_proc), \
             patch("netopt.ai_defense.audit_arp_lan", return_value={"anomalies": []}):
            res = audit_ai_threats()
            self.assertGreaterEqual(res["risk_score"], 30)
            self.assertEqual(len(res["temp_network_processes"]), 1)

    def test_ui_panels_and_quarantine_post_routes(self):
        from main import get_dashboard_html
        client = TestClient(create_app(dashboard_html_provider=get_dashboard_html))
        html_res = client.get("/")
        self.assertEqual(html_res.status_code, 200)
        for ep in ("/api/mesh/status", "/api/quarantine", "/api/hermes/insights", "/api/quarantine/isolate", "/api/quarantine/restore"):
            self.assertIn(ep, html_res.text)
        self.assertIn("total_plans_evaluated", html_res.text)
        self.assertIn("Plan Gratis Full", html_res.text)
        ins = client.get("/api/hermes/insights")
        self.assertEqual(ins.status_code, 200)
        self.assertIn("total_plans_evaluated", ins.json())
        self.assertIn("avg_plan_score", ins.json())
        self.assertIn("real_pass_rate_pct", ins.json())

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"safe-test-payload")
            tmp_path = tf.name
        try:
            iso = client.post("/api/quarantine/isolate", json={"file_path": tmp_path, "reason": "test"})
            self.assertEqual(iso.status_code, 200)
            self.assertTrue(iso.json().get("simulated"))
            rst = client.post("/api/quarantine/restore", json={"item_id": "nonexistent-id"})
            self.assertEqual(rst.status_code, 200)
            self.assertFalse(rst.json().get("success"))
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def test_chat_memory_followup_and_summary_no_hallucination(self):
        from main import get_dashboard_html
        from netopt.llm_gateway import LLMGateway

        self.assertIn("omninet_chat_history_v1", get_dashboard_html())
        gw = LLMGateway()
        self.assertEqual(
            gw._detect_followup_from_assistant("¿Quieres que revise también el estado del computador (espacio, memoria y programas pesados)?"),
            "device_full_maintenance",
        )
        with patch.object(gw, "config", {"api_key": "", "base_url": ""}), \
             patch.object(gw, "_record_conversation_feedback"):
            hist = [
                {"role": "user", "content": "¿Cómo está mi internet?"},
                {"role": "assistant", "content": "Tu internet está bien. ¿Quieres que revise ahora el estado de tu computador?"},
            ]
            with patch("netopt.device_maintenance.DeviceMaintenanceEngine.run_full_device_maintenance", return_value={"actions_executed": [], "disk_free_gb": 50.0, "summary": "PC OK"}) as m_dev:
                res_ok = gw.chat("ok", history=hist, language_mode="simple")
                self.assertEqual(res_ok["executed_tool"], "device_full_maintenance")
                m_dev.assert_called_once()

            res_sum = gw.chat("dame un resumen de nuestras conversaciones", history=hist, language_mode="simple")
            self.assertEqual(res_sum["executed_tool"], "conversation_summary")
            self.assertIn("¿Cómo está mi internet?", res_sum["reply"])
            self.assertNotIn("802 archivos basura", res_sum["reply"])

            res_url = gw.chat("verifica este enlace http://g00gle-login.xyz", history=[], language_mode="simple")
            self.assertEqual(res_url["executed_tool"], "ai_defense_check_url")
            self.assertIn("Riesgo", res_url["reply"])

            with patch("netopt.ai_defense.audit_ai_threats", return_value={"threat_level": "LOW", "risk_score": 0, "summary": "Sistema limpio"}):
                res_aud = gw.chat("escanea amenazas y hackeos ia", history=[], language_mode="simple")
                self.assertEqual(res_aud["executed_tool"], "ai_defense_audit")
                self.assertIn("LOW", res_aud["reply"])

    def test_mcp_ai_defense_tools(self):
        from mcp_server import handle_tool_call
        r_url = handle_tool_call("ai_defense_check_url", {"url": "http://g00gle-login.xyz"})
        self.assertEqual(r_url["verdict"], "DANGEROUS")
        with patch("netopt.ai_defense.audit_ai_threats", return_value={"threat_level": "LOW", "risk_score": 0, "summary": "OK"}):
            r_aud = handle_tool_call("ai_defense_audit", {})
            self.assertEqual(r_aud["threat_level"], "LOW")

    def test_saas_free_full_and_paid_full_editions_and_cloud_endpoints(self):
        import threading
        import urllib.request
        from http.server import ThreadingHTTPServer
        from cloud_server.proxy_server import OmniNetCloudProxyHandler
        from netopt.licensing import PLAN_CATALOG

        self.assertTrue(PLAN_CATALOG["free"]["local_full_unlocked"])
        self.assertTrue(PLAN_CATALOG["free"]["auto_care_10m"])
        self.assertTrue(PLAN_CATALOG["free"]["deep_clean_bleachbit_sdio"])
        self.assertFalse(PLAN_CATALOG["free"]["cloud_managed_ai"])
        self.assertTrue(PLAN_CATALOG["pro"]["cloud_managed_ai"])
        self.assertTrue(PLAN_CATALOG["family"]["cloud_managed_ai"])

        srv = ThreadingHTTPServer(("127.0.0.1", 0), OmniNetCloudProxyHandler)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
                self.assertEqual(r.status, 200)
                html = r.read().decode("utf-8")
                self.assertIn("Edición Gratuita Full", html)
                self.assertIn("Edición Pagada Full", html)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertEqual(json.loads(r.read().decode("utf-8"))["status"], "ok")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/plans", timeout=5) as r:
                self.assertEqual(r.status, 200)
                data = json.loads(r.read().decode("utf-8"))
                self.assertIn("free_full", data["editions"])
                self.assertIn("paid_pro", data["editions"])
                self.assertIn("paid_family", data["editions"])
        finally:
            srv.shutdown()
            srv.server_close()

    def test_matrix_wallpaper_manager_and_endpoints(self):
        from main import get_dashboard_html
        from netopt.matrix_wallpaper import MatrixWallpaperManager

        self.assertIn("/api/wallpaper/matrix", get_dashboard_html())
        with tempfile.TemporaryDirectory() as tmpd:
            st_file = os.path.join(tmpd, "mx.json")
            mgr = MatrixWallpaperManager(state_file=st_file)
            self.assertFalse(mgr.status()["running"])

            sim = mgr.start(execute=False)
            self.assertTrue(sim["simulated"])
            self.assertIn(sim["mode"], ("workerw_desktop", "ewmh_desktop"))

            fake_proc = MagicMock(pid=424242)
            with patch("netopt.matrix_wallpaper.subprocess.Popen", return_value=fake_proc) as m_pop:
                started = mgr.start(execute=True)
                self.assertFalse(started["simulated"])
                self.assertEqual(started["pid"], 424242)
                m_pop.assert_called_once()

            with patch("netopt.matrix_wallpaper._is_pid_alive", return_value=True), \
                 patch("netopt.matrix_wallpaper.subprocess.run") as m_run, \
                 patch("netopt.matrix_wallpaper.os.kill") as m_kill:
                stopped = mgr.stop(execute=True)
                self.assertFalse(stopped["running"])
                self.assertTrue(m_run.called or m_kill.called)

        client = TestClient(create_app())
        self.assertEqual(client.get("/api/wallpaper/status").status_code, 200)
        r_mx = client.get("/matrix")
        self.assertEqual(r_mx.status_code, 200)
        self.assertIn("E=mc^2", r_mx.text)
        self.assertIn("AI::HANDSHAKE[OK]", r_mx.text)
        self.assertIn("UnrealBloomPass", r_mx.text)
        self.assertIn("createMatrixRainTexture", r_mx.text)
        self.assertIn("createCodeHuman", r_mx.text)
        self.assertIn("figureRimLight", r_mx.text)
        self.assertIn("emissiveIntensity: 2.45", r_mx.text)

    def test_sovereign_dns_qos_service_and_autonomy_endpoints(self):
        from netopt.sovereign_dns import SovereignDNSServer, extract_dns_qname
        from netopt.qos_controller import apply_app_dscp_qos_policies, manage_autostart_service
        from main import get_dashboard_html

        self.assertIn("/api/autonomy/sovereign-dns", get_dashboard_html())
        self.assertIn("Detener DNS", get_dashboard_html())

        from netopt.llm_gateway import LLMGateway
        gw = LLMGateway()
        with patch.object(gw, "config", {"api_key": "", "base_url": ""}), \
             patch.object(gw, "_record_conversation_feedback"):
            res_ctrl = gw.chat("estado de dns soberano y failover multipath", history=[], language_mode="simple")
            self.assertEqual(res_ctrl["executed_tool"], "autonomous_control_plane")

        # Build minimal RFC 1035 DNS query for g00gle-login.xyz
        qname_wire = b"\x0cg00gle-login\x03xyz\x00"
        pkt = b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + qname_wire + b"\x00\x01\x00\x01"
        self.assertEqual(extract_dns_qname(pkt), "g00gle-login.xyz")

        dns_srv = SovereignDNSServer(port=0)
        reply, blocked, dom = dns_srv.handle_packet(pkt)
        self.assertTrue(blocked)
        self.assertEqual(dom, "g00gle-login.xyz")
        self.assertEqual(reply[:2], b"\x12\x34")
        self.assertEqual(reply[3] & 0x0F, 3)  # NXDOMAIN

        safe_q = b"\x06google\x03com\x00"
        safe_pkt1 = b"\xaa\xbb\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + safe_q + b"\x00\x01\x00\x01"
        safe_pkt2 = b"\xcc\xdd\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00" + safe_q + b"\x00\x01\x00\x01"
        fake_resp = b"\xaa\xbb\x81\x80\x00\x01\x00\x01\x00\x00\x00\x00" + safe_q + b"\x00\x01\x00\x01"
        with patch.object(dns_srv, "_forward_doh", return_value=fake_resp) as m_doh:
            r1, b1, _ = dns_srv.handle_packet(safe_pkt1)
            r2, b2, _ = dns_srv.handle_packet(safe_pkt2)
            self.assertFalse(b1 or b2)
            m_doh.assert_called_once()
            self.assertEqual(r2[:2], b"\xcc\xdd")
            self.assertEqual(dns_srv.status()["cache_hits"], 1)

        sim_dns = dns_srv.start(execute=False)
        self.assertTrue(sim_dns["simulated"])

        # Fallback to ephemeral port if preferred port raises OSError/PermissionError (WinError 10013)
        dns_fb = SovereignDNSServer(port=5353)
        real_sock = dns_fb.start(execute=True)
        try:
            self.assertTrue(real_sock["success"])
            self.assertTrue(real_sock["running"])
        finally:
            dns_fb.stop(execute=True)

        sim_qos = apply_app_dscp_qos_policies(execute=False)
        self.assertTrue(sim_qos["simulated"])
        self.assertGreaterEqual(len(sim_qos["policies"]), 3)

        sim_svc = manage_autostart_service(enabled=True, execute=False)
        self.assertTrue(sim_svc["simulated"])

        client = TestClient(create_app())
        self.assertEqual(client.get("/api/autonomy/status").status_code, 200)
        self.assertTrue(client.post("/api/autonomy/sovereign-dns", json={"enabled": True, "execute": False}).json()["simulated"])
        self.assertTrue(client.post("/api/autonomy/qos", json={"execute": False}).json()["simulated"])
        self.assertTrue(client.post("/api/autonomy/service", json={"enabled": True, "execute": False}).json()["simulated"])

        from hermes.executor import HermesExecutor
        hx = HermesExecutor()
        self.assertIn("hermes_ai_defense_audit", hx.harness.tools)
        self.assertIn("hermes_multipath_failover", hx.harness.tools)

    def test_rfc9959_careful_resume_and_rfc9957_l4s_queue_protection(self):
        from netopt.diagnostics import check_rfc9959_careful_resume_and_rfc9957_l4s_queue_protection_status
        res = check_rfc9959_careful_resume_and_rfc9957_l4s_queue_protection_status()
        self.assertIn("RFC 9959", res["standard_careful_resume"])
        self.assertIn("RFC 9957", res["standard_l4s_qprotect"])
        self.assertTrue(res["careful_resume_path_state_bounded"])
        self.assertTrue(res["l4s_queue_isolation_active"])

    def test_mcp_server_unknown_tool_and_manifest_parity(self):
        import json as _json
        import mcp_server
        tools = mcp_server.load_tools_schema()
        self.assertEqual(len(tools), 17)
        resp = mcp_server.process_jsonrpc_line(
            _json.dumps({"jsonrpc": "2.0", "id": 99, "method": "tools/call", "params": {"name": "nonexistent_tool", "arguments": {}}}),
            tools,
        )
        self.assertEqual(resp["error"]["code"], -32602)
        self.assertIn("Unknown tool", resp["error"]["message"])

    def test_pqc_tls13_x25519mlkem768_mtu_readiness(self):
        from netopt.diagnostics import check_pqc_tls13_x25519mlkem768_mtu_readiness
        ok_1500 = check_pqc_tls13_x25519mlkem768_mtu_readiness(1500)
        self.assertTrue(ok_1500["single_packet_clienthello_safe"])
        self.assertFalse(ok_1500["fragmentation_risk"])
        risk_1280 = check_pqc_tls13_x25519mlkem768_mtu_readiness(1280)
        self.assertFalse(risk_1280["single_packet_clienthello_safe"])
        self.assertTrue(risk_1280["fragmentation_risk"])

    def test_main_daemon_cli_bounds_validation(self):
        import sys
        import io
        from contextlib import redirect_stderr
        import main as omninet_main
        with patch.object(sys, "argv", ["main.py", "daemon", "--interval", "1"]):
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    omninet_main.main()
        self.assertEqual(cm.exception.code, 2)

    def test_sovereign_dns_doh_failover_when_primary_unreachable(self):
        from netopt.sovereign_dns import SovereignDNSServer
        srv = SovereignDNSServer(upstream_doh="https://1.1.1.1/dns-query", fallback_doh="https://dns.google/dns-query")

        class _FakeResp:
            def __init__(self, data: bytes):
                self._data = data
            def read(self) -> bytes:
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        calls = []
        def _fake_urlopen(req, timeout=3.0):
            calls.append(req.full_url)
            if "1.1.1.1" in req.full_url:
                raise OSError("primary timeout")
            return _FakeResp(b"\x12\x34\x81\x80")

        with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            out = srv._forward_doh(b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        self.assertEqual(out, b"\x12\x34\x81\x80")
        self.assertEqual(srv.upstream_failovers, 1)
        self.assertEqual(len(calls), 2)

    def test_mcp_server_safe_target_and_empty_url_is_error(self):
        import json as _json
        import mcp_server
        self.assertEqual(mcp_server._safe_target("1.1.1.1; whoami"), "1.1.1.1")
        self.assertEqual(mcp_server._safe_target("dns.google"), "dns.google")
        tools = mcp_server.load_tools_schema()
        resp = mcp_server.process_jsonrpc_line(
            _json.dumps({"jsonrpc": "2.0", "id": 100, "method": "tools/call", "params": {"name": "ai_defense_check_url", "arguments": {"url": "   "}}}),
            tools,
        )
        self.assertTrue(resp["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
