import unittest
from netopt.schemas import (
    DeviceIdentity,
    HealthResponse,
    SubagentRequest,
    OptimizeRequest,
    ChatRequest,
    LicenseActivationRequest,
    TelemetryReport,
    RollbackRequest,
    RepairRequest,
    SentinelToggleRequest
)
from pydantic import ValidationError


class TestPydanticSchemas(unittest.TestCase):
    """Verifies Pydantic v2 data models per mature libraries mandate (docs/Auditorias/3.md)."""

    def test_device_identity_validation(self):
        dev = DeviceIdentity(device_id="PC-A1B2C3D4E5F6", platform="windows")
        self.assertEqual(dev.device_id, "PC-A1B2C3D4E5F6")
        self.assertEqual(dev.platform, "windows")

        # Rejects device_id with less than 4 chars
        with self.assertRaises(ValidationError):
            DeviceIdentity(device_id="AB")

    def test_health_response_defaults(self):
        hr = HealthResponse()
        self.assertEqual(hr.status, "healthy")
        self.assertEqual(hr.version, "2.9.6")
        self.assertGreater(hr.timestamp, 0)

    def test_subagent_request_validation(self):
        req = SubagentRequest(id="redes", execute=True)
        self.assertEqual(req.id, "redes")
        self.assertTrue(req.execute)

        with self.assertRaises(ValidationError):
            SubagentRequest(id="")

    def test_optimize_request_validation(self):
        opt = OptimizeRequest()
        self.assertFalse(opt.execute)
        self.assertEqual(opt.profile, "balanced")

        opt_gaming = OptimizeRequest(execute=True, profile="gaming")
        self.assertTrue(opt_gaming.execute)
        self.assertEqual(opt_gaming.profile, "gaming")

    def test_chat_request_validation(self):
        chat = ChatRequest(
            message="¿Cómo optimizar mi Wi-Fi?",
            device_id="PC-12345678",
            history=[{"role": "user", "content": "Hola"}],
            language_mode="simple"
        )
        self.assertEqual(chat.message, "¿Cómo optimizar mi Wi-Fi?")
        self.assertEqual(chat.device_id, "PC-12345678")
        self.assertEqual(len(chat.history), 1)
        self.assertEqual(chat.language_mode, "simple")

        with self.assertRaises(ValidationError):
            ChatRequest(message="")

    def test_rollback_and_repair_requests(self):
        rb = RollbackRequest(snapshot_id="snap_2026", execute=True)
        self.assertEqual(rb.snapshot_id, "snap_2026")
        self.assertTrue(rb.execute)

        rep = RepairRequest(execute=False)
        self.assertFalse(rep.execute)

    def test_sentinel_toggle_request(self):
        toggle = SentinelToggleRequest(enabled=True)
        self.assertTrue(toggle.enabled)
        toggle_default = SentinelToggleRequest()
        self.assertIsNone(toggle_default.enabled)

    def test_license_activation_request_validation(self):
        lic = LicenseActivationRequest(license_key="OMNI-PRO-TEST-1234-SIG")
        self.assertEqual(lic.license_key, "OMNI-PRO-TEST-1234-SIG")
        self.assertEqual(lic.email, "")

        with self.assertRaises(ValidationError):
            LicenseActivationRequest(license_key="")

    def test_telemetry_report_validation(self):
        telem = TelemetryReport(device_id="PC-99887766", overall_health="degraded", latency_ms=45.2)
        self.assertEqual(telem.device_id, "PC-99887766")
        self.assertEqual(telem.overall_health, "degraded")
        self.assertEqual(telem.latency_ms, 45.2)
        self.assertEqual(telem.bufferbloat_grade, "A")


if __name__ == "__main__":
    unittest.main()

