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

    def test_psutil_adapter_disk_telemetry(self):
        disk = SystemResourceAdapter.get_disk_telemetry()
        self.assertTrue(disk["available"])
        self.assertGreater(disk["total_gb"], 0)
        self.assertGreaterEqual(disk["free_gb"], 0)
        self.assertGreaterEqual(disk["used_percent"], 0.0)
        self.assertIn("write_bytes", disk)
        self.assertIn("read_bytes", disk)


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

    @patch("httpx.Client.patch")
    def test_httpx_adapter_patch_json_success(self, mock_patch):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"updated": True}
        mock_patch.return_value = mock_resp

        status, data = HttpClientAdapter.patch_json("http://cloud.omninet.ai/v1/license/devices", {"devices": ["dev-1"]})
        self.assertEqual(status, 200)
        self.assertTrue(data.get("updated"))

    @patch("httpx.Client.request")
    def test_httpx_adapter_generic_request_json_success(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"id": 1, "status": "active"}]
        mock_request.return_value = mock_resp

        status, data = HttpClientAdapter.request_json("GET", "http://cloud.omninet.ai/rest/v1/licenses", params={"limit": "1"})
        self.assertEqual(status, 200)
        self.assertIsInstance(data, list)
        self.assertEqual(data[0]["status"], "active")


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

    @patch("netopt.adapters.HttpClientAdapter.post_json")
    def test_dispatch_global_device_telemetry_uses_http_adapter(self, mock_post):
        from netopt.telemetry import dispatch_global_device_telemetry
        mock_post.return_value = (200, {"status": "telemetry_received", "device_hash": "a1b2c3d4e5f6"})

        report = {
            "device_id": "test-dev-01",
            "platform": "windows",
            "ping_avg_ms": 22.5,
            "jitter_ms": 1.1,
            "packet_loss_pct": 0.0,
            "bufferbloat_grade": "A",
            "wifi_band": "5 GHz",
            "is_wifi7": False,
            "app_version": "2.9.6"
        }
        res = dispatch_global_device_telemetry(report, collector_url="http://mock-cloud.omninet.ai")
        mock_post.assert_called_once()
        self.assertTrue(res["success"])
        self.assertTrue(res["dispatched"])
        self.assertEqual(res["device_hash"], "a1b2c3d4e5f6")



if __name__ == "__main__":
    unittest.main()

