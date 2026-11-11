import unittest
from unittest.mock import patch, MagicMock
from netopt.adapters import SystemResourceAdapter, HttpClientAdapter


class TestMatureAdapters(unittest.TestCase):
    """Verifies mature library adapters (psutil and httpx) per docs/Auditorias/3.md §38."""

    def test_psutil_adapter_availability_and_cpu_memory(self):
        self.assertTrue(SystemResourceAdapter.is_available())
        telemetry = SystemResourceAdapter.get_cpu_and_memory_telemetry()
        self.assertTrue(telemetry["available"])
        self.assertGreaterEqual(telemetry["cpu_percent"], 0.0)
        self.assertGreaterEqual(telemetry["physical_cores"], 1)
        self.assertGreater(telemetry["ram_total_mb"], 0)
        self.assertGreater(telemetry["ram_available_mb"], 0)
        self.assertIsInstance(telemetry["memory_pressure"], bool)

    def test_psutil_adapter_interface_io_counters(self):
        io_counters = SystemResourceAdapter.get_interface_io_counters()
        self.assertTrue(io_counters["available"])
        self.assertGreaterEqual(io_counters["total_bytes_sent"], 0)
        self.assertGreaterEqual(io_counters["total_bytes_recv"], 0)
        self.assertIsInstance(io_counters["interfaces"], dict)

    def test_psutil_adapter_top_network_processes(self):
        top_procs = SystemResourceAdapter.get_top_network_processes(limit=3)
        self.assertIsInstance(top_procs, list)
        if top_procs:
            proc = top_procs[0]
            self.assertIn("pid", proc)
            self.assertIn("name", proc)
            self.assertIn("open_sockets", proc)
            self.assertGreaterEqual(proc["open_sockets"], 1)

    def test_httpx_adapter_availability_and_error_handling(self):
        self.assertTrue(HttpClientAdapter.is_available())
        # Call non-existent port on loopback to verify error handling without unhandled exceptions
        status, data = HttpClientAdapter.get_json("http://127.0.0.1:59999/health", timeout_sec=0.2)
        self.assertEqual(status, 500)
        self.assertIn("error", data)
        self.assertEqual(data.get("adapter"), "httpx_adapter")

    @patch("httpx.Client.post")
    def test_httpx_adapter_post_json_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"valid": True, "plan": "pro"}
        mock_post.return_value = mock_resp

        status, data = HttpClientAdapter.post_json("http://cloud.omninet.ai/v1/license/activate", {"key": "TEST"})
        self.assertEqual(status, 200)
        self.assertTrue(data.get("valid"))
        self.assertEqual(data.get("plan"), "pro")

    @patch("netopt.adapters.HttpClientAdapter.post_json")
    def test_license_manager_activate_license_uses_http_adapter(self, mock_post):
        from netopt.licensing import LicenseManager
        mock_post.return_value = (200, {"valid": True, "plan": "pro"})

        lm = LicenseManager()
        lm.state["cloud_proxy_url"] = "http://mock-cloud.omninet.ai"
        res = lm.activate_license("OMNI-PRO-1234-5678-ABCD1234ABCD1234ABCD1234ABCD1234", "user@test.com")

        mock_post.assert_called_once()
        self.assertTrue(res["success"])
        self.assertEqual(res["plan"], "pro")


if __name__ == "__main__":
    unittest.main()

