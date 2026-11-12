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

    @patch("netopt.adapters.HttpClientAdapter.get_json")
    def test_check_ech_rfc9460_uses_http_adapter(self, mock_get):
        from netopt.diagnostics import check_ech_rfc9460_status
        mock_get.return_value = (200, {
            "Answer": [
                {"type": 65, "data": "1 . alpn=h2,h3 ech=AEX+DQBBJQA=="}
            ]
        })
        res = check_ech_rfc9460_status(domain="crypto.cloudflare.com")
        mock_get.assert_called_once()
        self.assertTrue(res["ech_supported"])
        self.assertTrue(res["https_rr_found"])
        self.assertTrue(res["ech_param_present"])

    @patch("httpx.Client.get")
    @patch("httpx.Client.post")
    def test_httpx_adapter_get_and_post_bytes(self, mock_post, mock_get):
        mock_resp_get = MagicMock()
        mock_resp_get.status_code = 200
        mock_resp_get.content = b"sample_binary_data"
        mock_get.return_value = mock_resp_get

        mock_resp_post = MagicMock()
        mock_resp_post.status_code = 200
        mock_resp_post.content = b"ack_bytes"
        mock_post.return_value = mock_resp_post

        code_g, data_g = HttpClientAdapter.get_bytes("https://speed.cloudflare.com/__down?bytes=100")
        self.assertEqual(code_g, 200)
        self.assertEqual(data_g, b"sample_binary_data")

        code_p, data_p = HttpClientAdapter.post_bytes("https://speed.cloudflare.com/__up", b"0" * 100)
        self.assertEqual(code_p, 200)
        self.assertEqual(data_p, b"ack_bytes")

    @patch("netopt.adapters.HttpClientAdapter.get_bytes")
    @patch("netopt.adapters.HttpClientAdapter.post_bytes")
    @patch("netopt.diagnostics.measure_target_metrics")
    def test_measure_bandwidth_speed_uses_http_adapter(self, mock_metrics, mock_post_bytes, mock_get_bytes):
        from netopt.diagnostics import measure_bandwidth_speed
        mock_get_bytes.return_value = (200, b"1" * 1_000_000)
        mock_post_bytes.return_value = (200, b"ack")
        mock_lat = MagicMock()
        mock_lat.avg_ms = 18.5
        mock_lat.jitter_ms = 0.5
        mock_lat.packet_loss_percent = 0.0
        mock_metrics.return_value = mock_lat

        res = measure_bandwidth_speed()
        mock_get_bytes.assert_called_once()
        mock_post_bytes.assert_called_once()
        self.assertGreater(res["download_mbps"], 0.0)
        self.assertGreater(res["upload_mbps"], 0.0)
        self.assertEqual(res["ping_ms"], 18.5)
        self.assertIn("Cloudflare", res["server"])

    @patch("psutil.sensors_battery")
    def test_psutil_adapter_power_telemetry(self, mock_battery):
        from netopt.adapters import SystemResourceAdapter
        # 1. Desktop / plugged case where sensors_battery returns None
        mock_battery.return_value = None
        res_desktop = SystemResourceAdapter.get_power_telemetry()
        self.assertTrue(res_desktop["available"])
        self.assertFalse(res_desktop["has_battery"])
        self.assertTrue(res_desktop["power_plugged"])
        self.assertEqual(res_desktop["battery_percent"], 100.0)
        self.assertFalse(res_desktop["is_power_saving"])

        # 2. Laptop low battery case
        mock_batt = MagicMock()
        mock_batt.percent = 12.0
        mock_batt.power_plugged = False
        mock_batt.secsleft = 1800
        mock_battery.return_value = mock_batt
        res_laptop = SystemResourceAdapter.get_power_telemetry()
        self.assertTrue(res_laptop["available"])
        self.assertTrue(res_laptop["has_battery"])
        self.assertFalse(res_laptop["power_plugged"])
        self.assertEqual(res_laptop["battery_percent"], 12.0)
        self.assertEqual(res_laptop["seconds_left"], 1800)
        self.assertTrue(res_laptop["is_power_saving"])






if __name__ == "__main__":
    unittest.main()

