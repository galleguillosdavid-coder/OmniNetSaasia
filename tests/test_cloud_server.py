import os
import time
import json
import hmac
import hashlib
import unittest
from unittest.mock import patch, MagicMock

import cloud_server.proxy_server as proxy
import cloud_server.supabase_client as sb_client
from netopt.adapters import HttpClientAdapter


class TestCloudServer(unittest.TestCase):
    """
    Comprehensive tests for OmniNet Cloud Server SaaS infrastructure:
    - Webhook security (Lemon Squeezy HMAC-SHA256 & Stripe signed payload)
    - RFC 9457 Problem Details standard
    - Global telemetry & conversation feedback persistence
    - Supabase credential separation (OMNI-023: Service Role vs Anon Key)
    - Mature HttpClientAdapter integration
    """

    def test_lemon_squeezy_signature_verification(self):
        secret = "lemon_secret_xyz123"
        payload = b'{"event_name": "order_created", "data": {"id": "123"}}'
        valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        # Valid signature
        self.assertTrue(proxy.verify_lemon_squeezy_signature(payload, valid_sig, secret))
        # Tampered payload
        tampered = b'{"event_name": "order_created", "data": {"id": "999"}}'
        self.assertFalse(proxy.verify_lemon_squeezy_signature(tampered, valid_sig, secret))
        # Missing secret or header
        self.assertFalse(proxy.verify_lemon_squeezy_signature(payload, "", secret))
        self.assertFalse(proxy.verify_lemon_squeezy_signature(payload, valid_sig, ""))

    def test_stripe_signature_verification(self):
        secret = "whsec_stripe_test_456"
        payload = b'{"id": "evt_test", "type": "payment_intent.succeeded"}'
        now = int(time.time())
        signed_payload = f"{now}.".encode("utf-8") + payload
        sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
        header = f"t={now},v1={sig}"

        # Valid signature
        self.assertTrue(proxy.verify_stripe_signature(payload, header, secret, tolerance=300))
        # Tampered payload
        self.assertFalse(proxy.verify_stripe_signature(b'tampered', header, secret, tolerance=300))
        # Expired tolerance (> 300s old)
        old_time = now - 600
        old_signed = f"{old_time}.".encode("utf-8") + payload
        old_sig = hmac.new(secret.encode("utf-8"), old_signed, hashlib.sha256).hexdigest()
        old_header = f"t={old_time},v1={old_sig}"
        self.assertFalse(proxy.verify_stripe_signature(payload, old_header, secret, tolerance=300))

    def test_format_rfc9457_problem_details(self):
        problem = proxy.format_rfc9457_problem_details(
            status=429,
            title="Rate Limit Exceeded",
            detail="You have sent too many requests in 60s.",
            instance="/v1/chat/completions",
            type_uri="https://api.omninet.ai/errors/rate-limit",
            error_code="RATE_LIMIT_HIT",
            retry_after_sec=30
        )
        self.assertEqual(problem["status"], 429)
        self.assertEqual(problem["title"], "Rate Limit Exceeded")
        self.assertEqual(problem["detail"], "You have sent too many requests in 60s.")
        self.assertEqual(problem["instance"], "/v1/chat/completions")
        self.assertEqual(problem["type"], "https://api.omninet.ai/errors/rate-limit")
        self.assertEqual(problem["error_code"], "RATE_LIMIT_HIT")
        self.assertEqual(problem["retry_after_sec"], 30)


    def test_cloud_db_load_and_save(self):
        db = proxy.load_cloud_db()
        self.assertIsInstance(db, dict)
        self.assertIn("licenses", db)
        self.assertIn("processed_webhook_events", db)

    def test_supabase_key_separation_omni_023(self):
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://xyzcompany.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "srv-role-secret-key-999",
            "SUPABASE_ANON_KEY": "anon-public-key-111"
        }, clear=False):
            # Backend service operations require service-role
            self.assertEqual(sb_client.get_supabase_backend_key(), "srv-role-secret-key-999")
            self.assertEqual(sb_client.get_supabase_client_key(), "anon-public-key-111")
            self.assertEqual(sb_client.get_supabase_key(require_service_role=True), "srv-role-secret-key-999")
            self.assertTrue(sb_client.is_supabase_configured(require_backend=True))

    @patch("netopt.adapters.HttpClientAdapter.request_json")
    def test_supabase_request_uses_mature_http_adapter(self, mock_request_json):
        mock_request_json.return_value = (200, [{"license_key": "OMNI-TEST", "plan": "pro"}])
        with patch.dict(os.environ, {
            "SUPABASE_URL": "https://xyzcompany.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "srv-role-secret-key-999"
        }, clear=False):
            res = sb_client.get_license_from_supabase("OMNI-TEST")
            mock_request_json.assert_called_once()
            self.assertIsNotNone(res)
            self.assertEqual(res["license_key"], "OMNI-TEST")
            self.assertEqual(res["plan"], "pro")

    def test_license_generation_and_cryptographic_verification(self):
        with patch.dict(os.environ, {"OMNINET_LICENSE_SECRET": "test_secret_for_licenses_9999"}):
            # Pro plan
            key_pro = proxy.generate_signed_license_key(plan="pro", email="alice@example.com")
            self.assertTrue(key_pro.startswith("OMNI-PRO-"))
            self.assertEqual(proxy.verify_signed_license_key(key_pro), "pro")

            # Family plan
            key_fam = proxy.generate_signed_license_key(plan="family", email="bob@example.com")
            self.assertTrue(key_fam.startswith("OMNI-FAM-"))
            self.assertEqual(proxy.verify_signed_license_key(key_fam), "family")

            # Tampered key
            tampered = key_pro[:-4] + "ABCD"
            self.assertIsNone(proxy.verify_signed_license_key(tampered))

            # Truncated signature (< 32 hex chars) rejected per OMNI-014
            parts = key_pro.split("-")
            truncated = f"{parts[0]}-{parts[1]}-{parts[2]}-{parts[3]}-{parts[4][:16]}"
            self.assertIsNone(proxy.verify_signed_license_key(truncated))

            # Master backdoor rejected
            self.assertIsNone(proxy.verify_signed_license_key("OMNI-PRO-MASTER-2026"))

    def test_compute_global_telemetry_stats_and_aggregation(self):
        """Verifies fleet-wide statistical aggregation of anonymous device telemetry."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_telemetry_file = os.path.join(tmp_dir, "test_global_telemetry.json")
            with patch.object(proxy, "CLOUD_TELEMETRY_FILE", tmp_telemetry_file):
                # Empty state
                stats_empty = proxy.compute_global_telemetry_stats()
                self.assertEqual(stats_empty["total_reports"], 0)
                self.assertEqual(stats_empty["unique_devices"], 0)
                self.assertEqual(stats_empty["avg_latency_ms"], 0.0)
                self.assertEqual(stats_empty["bufferbloat_distribution"], {})

                # Ingest synthetic telemetry entries
                entries = [
                    {
                        "timestamp": 1700000001,
                        "device_hash": "dev_001",
                        "platform": "windows",
                        "avg_latency_ms": 20.0,
                        "jitter_ms": 1.0,
                        "packet_loss_pct": 0.0,
                        "bufferbloat_grade": "A+",
                        "is_wifi7": True,
                        "app_version": "2.9.6"
                    },
                    {
                        "timestamp": 1700000002,
                        "device_hash": "dev_002",
                        "platform": "linux",
                        "avg_latency_ms": 40.0,
                        "jitter_ms": 3.0,
                        "packet_loss_pct": 1.0,
                        "bufferbloat_grade": "B",
                        "is_wifi7": False,
                        "app_version": "2.9.6"
                    },
                    {
                        "timestamp": 1700000003,
                        "device_hash": "dev_001",  # Repeated device
                        "platform": "windows",
                        "avg_latency_ms": 30.0,
                        "jitter_ms": 2.0,
                        "packet_loss_pct": 0.5,
                        "bufferbloat_grade": "A",
                        "is_wifi7": True,
                        "app_version": "2.9.6"
                    }
                ]
                for e in entries:
                    proxy.append_global_telemetry(e)

                stats = proxy.compute_global_telemetry_stats()
                self.assertEqual(stats["total_reports"], 3)
                self.assertEqual(stats["unique_devices"], 2)
                # avg_latency = (20 + 40 + 30) / 3 = 30.0
                self.assertEqual(stats["avg_latency_ms"], 30.0)
                # avg_jitter = (1 + 3 + 2) / 3 = 2.0
                self.assertEqual(stats["avg_jitter_ms"], 2.0)
                # avg_packet_loss = (0 + 1 + 0.5) / 3 = 0.5
                self.assertEqual(stats["avg_packet_loss_pct"], 0.5)
                # Bufferbloat breakdown
                self.assertEqual(stats["bufferbloat_distribution"]["A+"], 1)
                self.assertEqual(stats["bufferbloat_distribution"]["B"], 1)
                self.assertEqual(stats["bufferbloat_distribution"]["A"], 1)
                # Platforms breakdown
                self.assertEqual(stats["platforms_breakdown"]["windows"], 2)
                self.assertEqual(stats["platforms_breakdown"]["linux"], 1)
                # Wi-Fi 7 devices count
                self.assertEqual(stats["wifi7_devices_count"], 2)
                self.assertEqual(stats["app_versions"]["2.9.6"], 3)


if __name__ == "__main__":
    unittest.main()
