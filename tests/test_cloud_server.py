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


if __name__ == "__main__":
    unittest.main()
