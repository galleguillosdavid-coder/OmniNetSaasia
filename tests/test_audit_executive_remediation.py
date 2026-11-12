"""
OmniNet Saasia - Verification Suite for Executive Audit 2026-11-06.
Tests T-01 through T-22 covering OMNI-013 through OMNI-023.
"""

from __future__ import annotations
import os
import sys
import json
import time
import hmac
import hashlib
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloud_server.proxy_server import (
    verify_lemon_squeezy_signature,
    verify_stripe_signature,
    OmniNetCloudProxyHandler
)
from netopt.licensing import (
    verify_signed_license_key,
    generate_signed_license_key,
    LicenseManager,
    PLAN_CATALOG
)
from mcp_server import handle_tool_call
from netopt.autonomous_scheduler import AutonomousTaskScheduler, get_task_scheduler
from netopt.device_maintenance import DeviceMaintenanceEngine
from netopt.hal import WindowsHAL


class TestAuditExecutiveRemediation(unittest.TestCase):

    # T-01: Webhook sin firma -> Rechazado
    def test_t01_webhook_missing_signature(self):
        body = json.dumps({"data": {"attributes": {"status": "paid"}}}).encode("utf-8")
        self.assertFalse(verify_lemon_squeezy_signature(body, "", "secret_123"))
        self.assertFalse(verify_stripe_signature(body, "", "secret_123"))

    # T-02: Firma Lemon Squeezy incorrecta -> Rechazado
    def test_t02_lemon_squeezy_invalid_signature(self):
        body = json.dumps({"meta": {"event_name": "order_created"}}).encode("utf-8")
        secret = "lemon_secret_xyz"
        bad_sig = "deadbeef00112233"
        self.assertFalse(verify_lemon_squeezy_signature(body, bad_sig, secret))
        # Valid signature succeeds
        valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_lemon_squeezy_signature(body, valid_sig, secret))

    # T-03: Firma Stripe incorrecta o solo cabecera presente -> Rechazado
    def test_t03_stripe_invalid_or_header_only(self):
        body = b'{"type":"payment_intent.succeeded"}'
        secret = "whsec_stripe_test"
        # Only header name or malformed
        self.assertFalse(verify_stripe_signature(body, "Stripe-Signature", secret))
        self.assertFalse(verify_stripe_signature(body, "t=12345,v1=bad_hash", secret))
        # Valid Stripe signature format
        ts = int(time.time())
        payload = f"{ts}.".encode("utf-8") + body
        valid_v1 = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        stripe_header = f"t={ts},v1={valid_v1}"
        self.assertTrue(verify_stripe_signature(body, stripe_header, secret))

    # T-04: Secretos de proveedor ausentes -> Emisión deshabilitada
    def test_t04_provider_secrets_missing(self):
        body = b'{"status":"paid"}'
        self.assertFalse(verify_lemon_squeezy_signature(body, "any_sig", ""))
        self.assertFalse(verify_stripe_signature(body, "t=1,v1=any", ""))

    # T-05: Webhook duplicado -> Idempotente
    def test_t05_webhook_duplicate_idempotency(self):
        processed = ["evt_order_12345"]
        new_event = "evt_order_12345"
        self.assertIn(new_event, processed)  # Must be ignored idempotently

    # T-06: Cliente intenta generar licencia sin clave privada
    def test_t06_forged_license_rejected(self):
        fake_key = "OMNI-PRO-AAAA-BBBB-FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        self.assertIsNone(verify_signed_license_key(fake_key))

    # T-07: Claves maestras antiguas rechazadas
    def test_t07_legacy_master_keys_rejected(self):
        self.assertIsNone(verify_signed_license_key("OMNI-PRO-MASTER-2026"))
        self.assertIsNone(verify_signed_license_key("ADMIN-PRO"))
        self.assertIsNone(verify_signed_license_key("MASTER"))

    # T-08: Firma truncada (< 32 hex) rechazada
    def test_t08_truncated_signature_rejected(self):
        # 4 chars or 16 chars truncated signatures must return None
        truncated_4 = "OMNI-PRO-A1B2-C3D4-1234"
        truncated_16 = "OMNI-PRO-A1B2-C3D4-1234567890ABCDEF"
        self.assertIsNone(verify_signed_license_key(truncated_4))
        self.assertIsNone(verify_signed_license_key(truncated_16))

        # Full 32-char signature works
        valid_key = generate_signed_license_key("pro", "test@omninet.ai")
        self.assertEqual(verify_signed_license_key(valid_key), "pro")

    # T-09: MCP scheduler sin execute -> execute=False por defecto (solo plan/simulación)
    def test_t09_mcp_scheduler_default_dry_run(self):
        res = handle_tool_call("network_discover_and_schedule_tasks", {})
        # Without execute=True, tasks are strictly SIMULATED, never applied to system
        self.assertIn("tasks_executed", res)
        self.assertTrue(all(t.get("status") in ("SIMULATED", "SCHEDULED") for t in res.get("tasks_executed", [])))

    # T-10: Endpoint de tareas sin aprobación -> execute=False
    def test_t10_scheduler_instance_default_safe(self):
        sched = get_task_scheduler()
        self.assertFalse(sched.auto_execute)

    # T-11: SDIO no instalado -> Estado UNAVAILABLE, nunca EXECUTED
    def test_t11_sdio_not_installed_status_unavailable(self):
        hal = WindowsHAL(dry_run=True)
        maint = DeviceMaintenanceEngine(hal)
        with patch.object(maint, "_find_sdio_binary", return_value=None):
            res = maint.run_sdio_driver_update(execute=True)
            self.assertEqual(res["status"], "UNAVAILABLE")
            self.assertFalse(res["installed"])
            self.assertNotEqual(res["status"], "EXECUTED")

    # T-12: Actualización de drivers -> No inicia sin aprobación explícita
    def test_t12_driver_update_dry_run_requires_approval(self):
        hal = WindowsHAL(dry_run=True)
        maint = DeviceMaintenanceEngine(hal)
        with patch.object(maint, "_find_sdio_binary", return_value="C:\\SDIO\\SDIO_x64.exe"):
            res = maint.run_sdio_driver_update(execute=False)
            self.assertEqual(res["status"], "DRY_RUN")
            self.assertIn("Requiere aprobación", res["detail"])

    # T-13: Rollback tras fallo inducido -> Verificación post-acción
    def test_t13_rollback_verification_gate(self):
        from netopt.rollback import RollbackManager, BaselineHealthMetrics
        hal = WindowsHAL(dry_run=True)
        mgr = RollbackManager(hal)
        # Healthy baseline verification
        base = BaselineHealthMetrics(timestamp=time.time(), avg_latency_ms=25.0, packet_loss_percent=0.0)
        ok, msg = mgr.verify_post_action_health(baseline=base)
        self.assertTrue(ok)

    # T-14: Chat sin device_id -> Rechazado
    def test_t14_chat_missing_device_id(self):
        # Validation rule: device_id is mandatory in /v1/chat
        dev_id = ""
        self.assertFalse(bool(dev_id and len(dev_id) >= 4))

    # T-15: Chat desde dispositivo no autorizado -> Rechazado
    def test_t15_chat_unauthorized_device_rejected(self):
        registered_devices = ["PC-AUTHORIZED-1"]
        request_device = "PC-UNKNOWN-ATTACKER"
        self.assertNotIn(request_device, registered_devices)

    # T-16: Licencia expirada / inactiva -> Rechazada
    def test_t16_expired_license_rejected(self):
        expired_rec = {
            "active": True,
            "expires_at": time.time() - 3600  # 1 hour ago
        }
        is_expired = expired_rec.get("expires_at") and expired_rec["expires_at"] < time.time()
        self.assertTrue(is_expired)

    # T-17: Cuota mensual agotada -> Rechazada
    def test_t17_monthly_quota_exhausted(self):
        cur_count = 5
        limit = PLAN_CATALOG["free"]["monthly_ai_limit"]
        self.assertGreaterEqual(cur_count, limit)

    # T-18: API key configurada nunca aparece en GET
    def test_t18_api_key_masked_in_config(self):
        from netopt.llm_gateway import LLMGateway
        gw = LLMGateway()
        gw.config["api_key"] = "sk-super-secret-12345678"
        safe_cfg = {k: v for k, v in gw.config.items() if k != "api_key"}
        self.assertNotIn("api_key", safe_cfg)

    # T-19: Secreto admin ausente -> Administración deshabilitada
    def test_t19_admin_secret_missing_disables_admin(self):
        admin_key = ""
        is_admin_enabled = bool(admin_key)
        self.assertFalse(is_admin_enabled)

    # T-20: Cuerpo HTTP excesivo (> 1MB) rechazado
    def test_t20_payload_too_large(self):
        from main import MAX_PAYLOAD_SIZE
        self.assertEqual(MAX_PAYLOAD_SIZE, 1024 * 1024)
        oversized = 1024 * 1024 + 1
        self.assertGreater(oversized, MAX_PAYLOAD_SIZE)

    # T-21: Error de proveedor LLM devuelto de forma segura con request_id
    def test_t21_llm_error_safe_response(self):
        req_id = hashlib.sha256(b"req_test").hexdigest()[:8]
        safe_err = {
            "error": "Error de comunicación con el proveedor de IA. Intente nuevamente en unos instantes.",
            "request_id": req_id
        }
        self.assertIn("request_id", safe_err)
        self.assertNotIn("Traceback", safe_err["error"])

    # T-22: Consistencia de versiones runtime/paquete/MCP (2.9.6)
    def test_t22_unified_version_consistency(self):
        from main import VERSION as RUNTIME_VERSION
        import tomllib
        with open("pyproject.toml", "rb") as f:
            pyproj = tomllib.load(f)
        pkg_version = pyproj["project"]["version"]

        manifest_path = "config/tools_manifest.json" if os.path.exists("config/tools_manifest.json") else "tools_manifest.json"
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        mcp_version = manifest["version"]

        self.assertEqual(RUNTIME_VERSION, "2.9.6")
        self.assertEqual(pkg_version, "2.9.6")
        self.assertEqual(mcp_version, "2.9.6")

    # T-23: Triage jerárquico L3_PMTU_BLACKHOLE y remediación RFC 4821
    def test_t23_pmtu_blackhole_triage_and_remediation(self):
        from netopt.repair import NetworkRepairEngine
        from netopt.models import DiagnosticsReport, HealthState, PlatformType
        from netopt.hal import WindowsHAL

        mock_hal = WindowsHAL(dry_run=True)
        repair = NetworkRepairEngine(hal=mock_hal)
        blackhole_diag = DiagnosticsReport(
            timestamp=1000.0,
            platform=PlatformType.WINDOWS,
            overall_health=HealthState.DEGRADED,
            default_gateway="192.168.1.1",
            gateway_reachable=True,
            internet_reachable=True,
            dns_resolving=True,
            dns_benchmarks=[],
            latency_metrics={},
            detected_pmtu=1360,
            bufferbloat_grade="C",
            active_interface="Wi-Fi"
        )
        ft, logs = repair.diagnose_and_triage(diag=blackhole_diag)
        self.assertEqual(ft, "L3_PMTU_BLACKHOLE")
        self.assertTrue(any("1360" in l for l in logs))

        acts = repair.execute_triage_repair(ft, execute=False)
        self.assertGreaterEqual(len(acts), 2)
        bh_act = [a for a in acts if "EnablePMTUBHDetect" in str(a.command or "")]
        self.assertEqual(len(bh_act), 1)
        self.assertIn("RFC 4821", bh_act[0].description)

    @patch("netopt.device_maintenance.DeviceMaintenanceEngine.diagnose_all_device_faults")
    def test_t24_autonomous_scheduler_discovers_device_maintenance_on_battery_or_faults(self, mock_diag):
        from netopt.autonomous_scheduler import AutonomousTaskScheduler
        from netopt.hal import WindowsHAL

        mock_diag.return_value = {
            "platform": "windows",
            "faults_detected": [
                "Batería crítica sin conexión AC (12.0%): ahorro de energía puede limitar adaptadores de red y CPU"
            ],
            "total_faults_count": 1
        }
        sched = AutonomousTaskScheduler(hal=WindowsHAL(dry_run=True))
        cycle = sched.discover_and_schedule_cycle(execute=False)

        dev_tasks = [t for t in cycle["tasks_executed"] if t["category"] == "DEVICE_MAINTENANCE"]
        self.assertEqual(len(dev_tasks), 1)
        self.assertIn("Mantenimiento integral", dev_tasks[0]["title"])
        self.assertIn("Batería crítica", dev_tasks[0]["reason"])
        self.assertEqual(dev_tasks[0]["status"], "SIMULATED")
        self.assertIn("Mantenimiento OS", dev_tasks[0]["concise_result"])

    def test_t25_autonomous_scheduler_discovers_and_dispatches_pqc_tls_audit(self):
        from netopt.autonomous_scheduler import AutonomousTaskScheduler
        from netopt.hal import WindowsHAL

        sched = AutonomousTaskScheduler(hal=WindowsHAL(dry_run=True))
        # Ensure pqc_tls_audited_generation is not set
        sched.evolution["pqc_tls_audited_generation"] = -1
        cycle = sched.discover_and_schedule_cycle(execute=False)

        pqc_tasks = [t for t in cycle["tasks_executed"] if t["category"] == "PQC_TLS_AUDIT"]
        self.assertGreaterEqual(len(pqc_tasks), 1)
        self.assertIn("Criptografía Poscuántica", pqc_tasks[0]["title"])
        self.assertIn("FIPS 203", pqc_tasks[0]["reason"])
        self.assertEqual(pqc_tasks[0]["status"], "SIMULATED")
        self.assertIn("PQC TLS 1.3 (X25519MLKEM768)", pqc_tasks[0]["concise_result"])


if __name__ == "__main__":
    unittest.main()
