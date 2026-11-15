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

    def test_compute_global_feedback_stats_and_aggregation(self):
        """Verifies fleet-wide statistical aggregation of anonymous AI assistant feedback."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_feedback_file = os.path.join(tmp_dir, "test_global_feedback.json")
            with patch.object(proxy, "CLOUD_FEEDBACK_FILE", tmp_feedback_file):
                # Empty state
                stats_empty = proxy.compute_global_feedback_stats()
                self.assertEqual(stats_empty["total_feedback_entries"], 0)
                self.assertEqual(stats_empty["unique_devices"], 0)
                self.assertEqual(stats_empty["avg_messages_per_session"], 0.0)
                self.assertEqual(stats_empty["models_used"], {})

                # Ingest synthetic feedback entries
                now = time.time()
                entries = [
                    {
                        "timestamp": now - 100,
                        "device_hash": "dev_a",
                        "license_hash": "lic_1",
                        "msg_count": 2,
                        "model": "deepseek-chat"
                    },
                    {
                        "timestamp": now - 50,
                        "device_hash": "dev_b",
                        "license_hash": "lic_2",
                        "msg_count": 4,
                        "model": "deepseek-chat"
                    },
                    {
                        "timestamp": now - 10,
                        "device_hash": "dev_a",  # repeated device
                        "license_hash": "lic_1",
                        "msg_count": 6,
                        "model": "deepseek-coder"
                    }
                ]
                for e in entries:
                    proxy.append_global_feedback(e)

                stats = proxy.compute_global_feedback_stats()
                self.assertEqual(stats["total_feedback_entries"], 3)
                self.assertEqual(stats["unique_devices"], 2)
                self.assertEqual(stats["unique_licenses"], 2)
                # avg_messages = (2 + 4 + 6) / 3 = 4.0
                self.assertEqual(stats["avg_messages_per_session"], 4.0)
                self.assertEqual(stats["models_used"]["deepseek-chat"], 2)
                self.assertEqual(stats["models_used"]["deepseek-coder"], 1)
                self.assertEqual(stats["recent_activity_count"], 3)

    def test_cloud_db_and_telemetry_atomic_thread_safe_persistence(self):
        """Verifies concurrent append_global_telemetry calls do not lose or corrupt entries."""
        import tempfile
        import threading
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_tel = os.path.join(tmp_dir, "concurrent_telemetry.json")
            with patch.object(proxy, "CLOUD_TELEMETRY_FILE", tmp_tel):
                threads = [
                    threading.Thread(
                        target=proxy.append_global_telemetry,
                        args=({"device_hash": f"dev_{i}", "avg_latency_ms": float(i), "bufferbloat_grade": "A"},),
                    )
                    for i in range(12)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=2.0)

                stats = proxy.compute_global_telemetry_stats()
                self.assertEqual(stats["total_reports"], 12)
                self.assertEqual(stats["unique_devices"], 12)

    def test_license_manager_rejects_non_http_cloud_url_and_atomic_save(self):
        """Verifies LicenseManager skips non-HTTP cloud_proxy_url and atomically persists state."""
        import tempfile
        import netopt.licensing as lic

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_state = os.path.join(tmp_dir, "license_state.json")
            with patch.object(lic, "LICENSE_STATE_FILE", tmp_state), \
                 patch("urllib.request.urlopen", side_effect=AssertionError("urlopen should not be called for file://")):
                mgr = lic.LicenseManager()
                mgr.state["cloud_proxy_url"] = "file:///etc/passwd"
                res = mgr.activate_license("INVALID-KEY-1234")
                self.assertFalse(res["success"])
                mgr.save_state()
                self.assertTrue(os.path.exists(tmp_state))

    def test_corrupt_cloud_json_raises_and_preserves_original_file(self):
        """H-01: Corrupt JSON in cloud DB or telemetry must fail closed and never overwrite data."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            corrupt_db = os.path.join(tmp_dir, "cloud_db.json")
            raw_corrupt = "{corrupt-json-payload"
            with open(corrupt_db, "w", encoding="utf-8") as f:
                f.write(raw_corrupt)

            corrupt_tel = os.path.join(tmp_dir, "cloud_tel.json")
            with open(corrupt_tel, "w", encoding="utf-8") as f:
                f.write('{"not": "a_list"}')

            with patch.object(proxy, "CLOUD_DB_FILE", corrupt_db), \
                 patch.object(proxy, "CLOUD_TELEMETRY_FILE", corrupt_tel):
                with self.assertRaises(proxy.CloudDataCorruptionError):
                    proxy.load_cloud_db()
                with self.assertRaises(proxy.CloudDataCorruptionError):
                    proxy.append_global_telemetry({"device_hash": "d1"})

            with open(corrupt_db, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), raw_corrupt)
            with open(corrupt_tel, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), '{"not": "a_list"}')

    def test_concurrent_update_cloud_db_no_lost_updates(self):
        """H-02 / Sec 4: Transactional _update_cloud_db preserves all concurrent mutations."""
        import tempfile
        import threading
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "cloud_db.json")
            with patch.object(proxy, "CLOUD_DB_FILE", db_path):
                def worker(idx: int):
                    def _tx(db):
                        lics = db.setdefault("licenses", {})
                        lics[f"KEY-{idx}"] = {"active": True, "queries_count": idx}
                        return idx, True
                    proxy._update_cloud_db(_tx)

                threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=5.0)

                loaded = proxy.load_cloud_db()
                self.assertEqual(len(loaded["licenses"]), 16)

    def test_http_body_validation_and_webhook_idempotency(self):
        """H-08 & Sec 4: Strict HTTP body framing and fail-closed webhook idempotency."""
        import http.client
        import socket
        import tempfile
        import threading
        from http.server import ThreadingHTTPServer

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = os.path.join(tmp_dir, "cloud_db.json")
            tel_path = os.path.join(tmp_dir, "cloud_tel.json")
            secret = "test_lemon_secret_123456"
            with patch.object(proxy, "CLOUD_DB_FILE", db_path), \
                 patch.object(proxy, "CLOUD_TELEMETRY_FILE", tel_path), \
                 patch.object(proxy, "LEMONSQUEEZY_WEBHOOK_SECRET", secret), \
                 patch.object(proxy, "STRIPE_WEBHOOK_SECRET", ""), \
                 patch.object(proxy, "is_supabase_configured", return_value=False):
                srv = ThreadingHTTPServer(("127.0.0.1", 0), proxy.OmniNetCloudProxyHandler)
                port = srv.server_address[1]
                t = threading.Thread(target=srv.serve_forever, daemon=True)
                t.start()
                try:
                    # 1. Missing Content-Length -> 411 (raw socket so http.client doesn't auto-add Content-Length: 0)
                    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
                        sock.sendall(b"POST /v1/telemetry/report HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
                        raw_411 = sock.recv(4096)
                    self.assertIn(b"411 Length Required", raw_411)

                    # 2. Transfer-Encoding: chunked -> 501
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request("POST", "/v1/telemetry/report", body="2\r\n{}\r\n0\r\n\r\n", headers={"Transfer-Encoding": "chunked"})
                    resp = conn.getresponse()
                    resp.read()
                    self.assertEqual(resp.status, 501)
                    conn.close()

                    # 3. Truncated body -> 400
                    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
                        sock.sendall(b"POST /v1/telemetry/report HTTP/1.1\r\nHost: 127.0.0.1\r\nContent-Length: 50\r\nConnection: close\r\n\r\n{\"a\":1}")
                        sock.shutdown(socket.SHUT_WR)
                        raw_resp = sock.recv(4096)
                    self.assertIn(b"400 Bad Request", raw_resp)

                    # 4. Invalid JSON -> 400
                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request("POST", "/v1/telemetry/report", body="{bad", headers={"Content-Type": "application/json", "Content-Length": "4"})
                    resp = conn.getresponse()
                    resp.read()
                    self.assertEqual(resp.status, 400)
                    conn.close()

                    # 5. Webhook idempotency: first creates license, second ignores duplicate
                    payload = json.dumps({
                        "meta": {"event_name": "order_created", "event_id": "evt_idem_001", "custom_data": {"plan": "pro"}},
                        "data": {"id": "order_1", "attributes": {"status": "paid", "user_email": "buyer@example.com", "first_order_item": {"product_name": "OmniNet Pro"}}}
                    }).encode("utf-8")
                    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request("POST", "/v1/webhooks/payment", body=payload, headers={"Content-Type": "application/json", "X-Signature": sig})
                    r1 = conn.getresponse()
                    b1 = json.loads(r1.read().decode("utf-8"))
                    self.assertEqual(r1.status, 200)
                    self.assertTrue(b1.get("created"))
                    conn.close()

                    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                    conn.request("POST", "/v1/webhooks/payment", body=payload, headers={"Content-Type": "application/json", "X-Signature": sig})
                    r2 = conn.getresponse()
                    b2 = json.loads(r2.read().decode("utf-8"))
                    self.assertEqual(r2.status, 200)
                    self.assertEqual(b2.get("status"), "idempotent_duplicate_ignored")
                    conn.close()

                    loaded = proxy.load_cloud_db()
                    self.assertEqual(len(loaded["licenses"]), 1)
                finally:
                    srv.shutdown()
                    srv.server_close()


if __name__ == "__main__":
    unittest.main()
