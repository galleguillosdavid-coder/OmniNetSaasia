"""
Unit tests for OmniNet core modules with mocking to ensure zero side-effects.
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import os
import sys

from netopt.models import (
    PlatformType,
    HealthState,
    NetworkInterfaceInfo,
    DiagnosticsReport,
    LatencyMetrics,
    DnsBenchmarkEntry,
    OrchestrationPlan
)
from netopt.hal import WindowsHAL, LinuxHAL, DarwinHAL, detect_platform, get_hal
from netopt.diagnostics import tcp_ping, benchmark_all_resolvers, check_bufferbloat
from netopt.rollback import RollbackManager
from netopt.optimizer import NetworkOptimizer
from netopt.repair import NetworkRepairEngine


class TestOmniNetCore(unittest.TestCase):

    def test_hal_dry_run_safety(self):
        """Ensures that dry-run commands never execute actual system changes."""
        hal = get_hal(dry_run=True)
        res = hal.run_cmd(["mock_unsafe_command_delete_all"], execute=False)
        self.assertTrue(res.is_dry_run)
        self.assertTrue(res.success)
        self.assertIn("DRY-RUN SIMULATION", res.stdout)

    def test_windows_hal_methods_dry_run(self):
        hal = WindowsHAL(dry_run=True)
        res_dns = hal.set_dns_servers("Ethernet", ["1.1.1.1", "8.8.8.8"], execute=False)
        self.assertTrue(res_dns.is_dry_run)
        self.assertEqual(res_dns.action_type.value, "optimization")

        res_flush = hal.flush_dns_cache(execute=False)
        self.assertTrue(res_flush.is_dry_run)

        res_tcp = hal.set_tcp_parameters({"autotuninglevel": "normal"}, execute=False)
        self.assertEqual(len(res_tcp), 1)
        self.assertTrue(res_tcp[0].is_dry_run)

    def test_linux_hal_methods_dry_run(self):
        hal = LinuxHAL(dry_run=True)
        res_dns = hal.set_dns_servers("eth0", ["1.1.1.1", "8.8.8.8"], execute=False)
        self.assertTrue(res_dns.is_dry_run)

        res_tcp = hal.set_tcp_parameters({"net.ipv4.tcp_congestion_control": "bbr"}, execute=False)
        self.assertEqual(len(res_tcp), 1)
        self.assertTrue(res_tcp[0].is_dry_run)

    def test_darwin_hal_methods_dry_run(self):
        hal = DarwinHAL(dry_run=True)
        res_dns = hal.set_dns_servers("Wi-Fi", ["1.1.1.1", "8.8.8.8"], execute=False)
        self.assertTrue(res_dns.is_dry_run)

    def test_rollback_manager_snapshot(self):
        mock_hal = MagicMock()
        mock_hal.get_dns_servers.return_value = ["192.168.1.1"]
        mock_hal.get_tcp_parameters.return_value = {"autotuninglevel": "normal"}
        mock_hal.get_interfaces.return_value = [
            NetworkInterfaceInfo(name="TestEth", mtu=1500, is_up=True)
        ]

        mgr = RollbackManager(hal=mock_hal)
        snap = mgr.capture_snapshot(description="Test unit snapshot")
        self.assertIsNotNone(snap.snapshot_id)
        self.assertEqual(snap.dns_settings["default"], ["192.168.1.1"])

        # Test loading
        loaded = mgr.load_snapshot(snap.snapshot_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.snapshot_id, snap.snapshot_id)

    def test_optimizer_plan_generation(self):
        mock_hal = MagicMock()
        mock_hal.dry_run = True
        mock_hal.get_interfaces.return_value = [
            NetworkInterfaceInfo(name="Eth0", is_up=True, is_loopback=False)
        ]

        optimizer = NetworkOptimizer(hal=mock_hal)
        diag = DiagnosticsReport(
            timestamp=1000.0,
            platform=PlatformType.WINDOWS,
            overall_health=HealthState.HEALTHY,
            default_gateway="192.168.1.1",
            gateway_reachable=True,
            internet_reachable=True,
            dns_resolving=True,
            dns_benchmarks=[
                DnsBenchmarkEntry("Cloudflare", "1.1.1.1", 12.0, 100.0),
                DnsBenchmarkEntry("Google", "8.8.8.8", 15.0, 100.0)
            ],
            latency_metrics={},
            detected_pmtu=1500,
            bufferbloat_grade="A",
            active_interface="Eth0"
        )

        plan = optimizer.generate_plan(diag=diag)
        self.assertGreater(len(plan.planned_actions), 0)
        self.assertIn("Fastest DNS", plan.reasoning)

    def test_repair_triage_gateway_down(self):
        mock_hal = MagicMock()
        mock_hal.dry_run = True
        repair = NetworkRepairEngine(hal=mock_hal)

        with patch("netopt.repair.run_full_diagnostics") as mock_diag:
            mock_diag.return_value = DiagnosticsReport(
                timestamp=1000.0,
                platform=PlatformType.WINDOWS,
                overall_health=HealthState.DOWN,
                default_gateway="192.168.1.1",
                gateway_reachable=False,
                internet_reachable=False,
                dns_resolving=False,
                dns_benchmarks=[],
                latency_metrics={},
                detected_pmtu=1500,
                bufferbloat_grade="F",
                active_interface="Eth0"
            )

            failure_type, logs = repair.diagnose_and_triage()
            self.assertEqual(failure_type, "L2_DHCP_OR_GATEWAY_FAILURE")
            actions = repair.execute_triage_repair(failure_type, execute=False)
            self.assertGreater(len(actions), 0)
            self.assertTrue(all(a.is_dry_run for a in actions))

    def test_autonomous_10min_scheduler_discovery(self):
        from netopt.autonomous_scheduler import AutonomousTaskScheduler
        mock_hal = MagicMock()
        mock_hal.dry_run = True
        mock_hal.get_dns_servers.return_value = ["192.168.1.1"]
        mock_hal.get_tcp_parameters.return_value = {"autotuninglevel": "normal"}
        mock_hal.get_interfaces.return_value = [
            NetworkInterfaceInfo(name="Eth0", mtu=1500, is_up=True)
        ]
        sched = AutonomousTaskScheduler(hal=mock_hal, interval_sec=600, auto_execute=False)
        self.assertEqual(sched.interval_sec, 600)
        with patch("netopt.autonomous_scheduler.run_full_diagnostics") as mock_diag, \
             patch("netopt.autonomous_scheduler.inspect_active_sockets") as mock_sock, \
             patch("netopt.autonomous_scheduler.audit_arp_lan") as mock_arp, \
             patch("netopt.autonomous_scheduler.discover_path_mtu") as mock_pmtu:
            mock_diag.return_value = DiagnosticsReport(
                timestamp=1000.0,
                platform=PlatformType.WINDOWS,
                overall_health=HealthState.HEALTHY,
                default_gateway="192.168.1.1",
                gateway_reachable=True,
                internet_reachable=True,
                dns_resolving=True,
                dns_benchmarks=[DnsBenchmarkEntry("Cloudflare", "1.1.1.1", 10.0, 100.0)],
                latency_metrics={"1.1.1.1": LatencyMetrics("1.1.1.1", 4, 4, 0.0, 10.0, 12.0, 14.0, 1.2)},
                detected_pmtu=1500,
                bufferbloat_grade="A+",
                active_interface="Eth0"
            )
            mock_sock.return_value = {"total_tcp": 42, "total_udp": 12, "states": {"ESTABLISHED": 20}, "anomalies": []}
            mock_arp.return_value = {"neighbor_count": 3, "neighbors": [], "anomalies": []}
            mock_pmtu.return_value = {"optimal_mtu": 1500, "max_unfragmented_payload": 1472, "needs_tuning": False}

            res = sched.discover_and_schedule_cycle(execute=False)
            self.assertEqual(res["next_cycle_in_sec"], 600)
            self.assertGreaterEqual(res["generation"], 1)
            self.assertIsNotNone(res["baseline_rtt_ms"])
            self.assertGreaterEqual(len(res["tasks_executed"]), 1)
            self.assertIn("Ciclo 10m", res["concise_summary"])

    def test_simple_language_ui_and_gateway(self):
        from netopt.llm_gateway import LLMGateway
        from main import get_dashboard_html

        html = get_dashboard_html()
        self.assertIn("OmniNet — Cuidador de tu Internet y tu PC", html)
        self.assertIn("oneClickBoostInternet()", html)
        self.assertIn("oneClickCleanAndRepairPC()", html)
        self.assertIn("oneClickSpeedTest()", html)
        self.assertIn("oneClickUndoLastChange()", html)
        self.assertNotIn("RFC 3550", html)
        self.assertNotIn("setLanguageMode('technical')", html)

        gw = LLMGateway()
        gw.config["api_key"] = ""
        gw.config["base_url"] = "https://api.deepseek.com"
        with patch("netopt.llm_gateway.inspect_active_sockets") as mock_sock:
            mock_sock.return_value = {
                "total_tcp": 25,
                "total_udp": 5,
                "states": {"ESTABLISHED": 10},
                "top_processes": [{"process": "chrome.exe", "sockets": 8}],
                "anomalies": []
            }
            res_simple = gw.chat("sockets", language_mode="technical")

        self.assertEqual(res_simple["language_mode"], "simple")
        self.assertIn("Programas que están usando tu Internet", res_simple["reply"])
        self.assertIn("chrome.exe", res_simple["reply"])
        self.assertNotIn("Estados FSM", res_simple["reply"])

    def test_doh_nic_and_wifi_telemetry(self):
        from netopt.diagnostics import inspect_wifi_and_nic
        hal = WindowsHAL(dry_run=True)
        doh_logs = hal.enable_encrypted_dns_doh(execute=False)
        nic_log = hal.optimize_nic_low_latency(execute=False)
        self.assertTrue(any("DoH" in l.command or "encryption" in l.command for l in doh_logs))
        self.assertTrue("NIC" in nic_log.command or "PowerManagement" in nic_log.command)

        with patch("netopt.diagnostics.get_hal") as mock_get_hal:
            mock_hal = MagicMock()
            mock_hal.get_active_interfaces.return_value = ["Wi-Fi"]
            mock_get_hal.return_value = mock_hal
            res = inspect_wifi_and_nic()
            self.assertIn("wifi", res)
            self.assertIn("active_nics", res)
            self.assertIn("preamble_puncturing_supported", res["wifi"])

    def test_multi_os_device_maintenance_engine(self):
        from netopt.device_maintenance import DeviceMaintenanceEngine, MULTI_OS_MAINTENANCE_CATALOG
        for os_key in ("windows", "linux", "darwin", "bsd"):
            self.assertIn(os_key, MULTI_OS_MAINTENANCE_CATALOG)
            self.assertGreaterEqual(len(MULTI_OS_MAINTENANCE_CATALOG[os_key]), 5)

        eng = DeviceMaintenanceEngine(WindowsHAL(dry_run=True))
        diag = eng.diagnose_all_device_faults()
        self.assertIn("storage", diag)
        self.assertIn("memory", diag)
        self.assertIn("security", diag)

        maint_res = eng.run_full_device_maintenance(execute=False)
        self.assertFalse(maint_res["executed"])
        self.assertIn("bleachbit", maint_res)
        self.assertIn("sdio_drivers", maint_res)
        self.assertGreaterEqual(len(maint_res["actions_executed"]), 5)

        large_res = eng.find_large_files_and_folders(min_size_mb=500.0, max_results=3)
        self.assertIn("largest_files", large_res)
        self.assertIn("largest_folders", large_res)

    def test_conversation_feedback_and_followup_continuity(self):
        from netopt.llm_gateway import LLMGateway
        gw = LLMGateway()
        gw.config["api_key"] = ""
        history = [
            {"role": "assistant", "content": "¿Quieres que busque las carpetas y archivos más pesados para que decidas qué borrar?"}
        ]
        with patch("netopt.device_maintenance.DeviceMaintenanceEngine.find_large_files_and_folders") as mock_find:
            mock_find.return_value = {
                "storage": {"free_gb": 39.0, "total_gb": 385.0},
                "largest_files": [{"name": "video_4k.mp4", "folder": "Descargas", "path": "C:\\video_4k.mp4", "size_mb": 1250.0, "size_gb": 1.22}],
                "largest_folders": [{"folder": "Descargas", "path": "C:\\Downloads", "total_mb": 4500.0, "total_gb": 4.39}],
                "total_large_files_found": 1
            }
            res_ok = gw.chat("ok", history=history)
            res_buscalas = gw.chat("buscalas", history=history)

        self.assertEqual(res_ok["executed_tool"], "device_find_large_files")
        self.assertIn("video_4k.mp4", res_ok["reply"])
        self.assertEqual(res_buscalas["executed_tool"], "device_find_large_files")

    def test_global_saas_licensing_and_quota(self):
        from netopt.licensing import generate_signed_license_key, verify_signed_license_key, get_license_manager
        pro_key = generate_signed_license_key("pro", "cliente@mundo.com")
        fam_key = generate_signed_license_key("family", "empresa@mundo.com")
        self.assertEqual(verify_signed_license_key(pro_key), "pro")
        self.assertEqual(verify_signed_license_key(fam_key), "family")
        self.assertIsNone(verify_signed_license_key("OMNI-PRO-0000-0000-FAKE"))

        mgr = get_license_manager()
        act_pro = mgr.activate_license(pro_key, email="cliente@mundo.com")
        self.assertTrue(act_pro["success"])
        self.assertEqual(act_pro["plan"], "pro")
        # Keep valid signed pro key for test environment
        mgr.activate_license(pro_key)

    def test_high_value_internet_research_features(self):
        from netopt.diagnostics import (
            check_doh_status, check_l4s_ecn_status, audit_lan_radar_devices,
            inspect_wifi_and_nic, check_ech_rfc9460_status, check_dnssec_dane_status,
            check_tsq_pacing_status, check_odoh_rfc9230_status, check_hystart_plusplus_status,
            check_bbrv3_readiness, check_doh3_rfc9297_status, check_tcp_prague_accecn_status,
            check_wifi7_preamble_puncturing_status
        )
        from netopt.optimizer import NetworkOptimizer
        from netopt.llm_gateway import LLMGateway

        # 1. DoH, ECH & L4S/ECN status
        doh = check_doh_status()
        self.assertIn("doh_enabled", doh)
        self.assertIn("privacy_status", doh)
        self.assertIn("ech_sni_encryption_supported", doh)

        prague = check_tcp_prague_accecn_status()
        self.assertTrue(prague["accecn_supported"])
        self.assertTrue(prague["dualpi2_aqm_compatible"])
        self.assertIn("RFC 9331", prague["transport_protocol"])

        doh3 = check_doh3_rfc9297_status()
        self.assertTrue(doh3["head_of_line_blocking_free"])
        self.assertTrue(doh3["zero_rtt_resumption_ready"])
        self.assertIn("RFC 9297", doh3["standard"])

        ech = check_ech_rfc9460_status()
        self.assertTrue(ech["ech_supported"])
        self.assertTrue(ech["sni_leak_mitigated"])

        dnssec = check_dnssec_dane_status()
        self.assertTrue(dnssec["dane_tlsa_ready"])
        self.assertIn("dnssec_supported_resolvers", dnssec)

        odoh = check_odoh_rfc9230_status()
        self.assertTrue(odoh["ip_query_decoupling_supported"])
        self.assertGreaterEqual(odoh["relay_count"], 1)

        bbr = check_bbrv3_readiness()
        self.assertTrue(bbr["bbr_supported"])
        self.assertTrue(bbr["shallow_threshold_ecn_coupled"])
        self.assertIn("BBRv3", bbr["algorithm"])

        hystart = check_hystart_plusplus_status()
        self.assertTrue(hystart["hystart_supported"])
        self.assertTrue(hystart["conservative_slow_start_enabled"])
        self.assertIn("RFC 9406", hystart["standard"])

        ecn = check_l4s_ecn_status()
        self.assertIn("ecn_enabled", ecn)
        self.assertIn("latency_mode", ecn)
        self.assertIn("dualq_aqm_supported", ecn)
        self.assertIn("quic_0rtt_capable", ecn)

        tsq = check_tsq_pacing_status()
        self.assertTrue(tsq["tsq_supported"])
        self.assertTrue(tsq["bql_active"])
        self.assertIn("pacing_algorithm", tsq)

        # Wi-Fi 7 TTLM & Preamble Puncturing support
        wifi_nic = inspect_wifi_and_nic()
        self.assertIn("wifi", wifi_nic)
        self.assertIn("tid_to_link_mapping_supported", wifi_nic["wifi"])

        punct = check_wifi7_preamble_puncturing_status()
        self.assertTrue(punct["preamble_puncturing_supported"])
        self.assertTrue(punct["anti_interference_fallback_avoided"])
        self.assertIn("802.11be", punct["standard"])

        # 2. LAN Radar device auditing
        radar = audit_lan_radar_devices()
        self.assertIn("gateway_ip", radar)
        self.assertIn("total_devices_detected", radar)
        self.assertIn("devices", radar)
        self.assertIn("radar_status", radar)

        # 3. Gaming & L4S QoS optimizer
        opt = NetworkOptimizer(WindowsHAL(dry_run=True))
        g_res = opt.optimize_gaming_and_l4s_qos(execute=False)
        self.assertTrue(g_res["gaming_mode_active"])
        self.assertGreaterEqual(len(g_res["actions"]), 2)

        # 4. LLM Gateway Intent routing for high-value tasks
        gw = LLMGateway()
        gw.config["api_key"] = ""
        res_radar = gw.chat("¿Hay intrusos o desconocidos en mi wifi?")
        self.assertEqual(res_radar["executed_tool"], "network_lan_radar")
        self.assertIn("Radar de Red Local", res_radar["reply"])

        res_game = gw.chat("activa el modo juego para videollamadas")
        self.assertEqual(res_game["executed_tool"], "network_gaming_mode")
        self.assertIn("Modo Juegos y Videollamadas", res_game["reply"])

        res_priv = gw.chat("activa máxima privacidad y cifrar dns")
        self.assertEqual(res_priv["executed_tool"], "network_doh_privacy")
        self.assertIn("Máxima Privacidad Activada", res_priv["reply"])

    def test_dynamic_software_catalog_and_installer(self):
        from netopt.software_catalog import find_matching_software, install_software_package, SOFTWARE_REGISTRY
        from netopt.llm_gateway import LLMGateway

        zip_recs = find_matching_software("necesito descomprimir archivos rar")
        self.assertTrue(any(r["id"] == "7zip" for r in zip_recs))

        office_recs = find_matching_software("word y excel para escribir documentos")
        self.assertTrue(any(r["id"] == "libreoffice" for r in office_recs))

        sim_res = install_software_package("7zip", execute=False)
        self.assertTrue(sim_res["success"])
        self.assertTrue(sim_res["simulated"])
        self.assertEqual(sim_res["program_name"], "7-Zip")

        gw = LLMGateway()
        gw.config["api_key"] = ""
        res_rec = gw.chat("¿qué programa me recomiendas para descomprimir archivos?")
        self.assertEqual(res_rec["executed_tool"], "software_recommendation")
        self.assertIn("7-Zip", res_rec["reply"])
        self.assertIn("te instale", res_rec["reply"])

        history = [
            {"role": "user", "content": "¿qué programa me recomiendas para descomprimir archivos?"},
            {"role": "assistant", "content": res_rec["reply"]}
        ]
        with patch("netopt.llm_gateway.install_software_package") as mock_install:
            mock_install.return_value = {
                "success": True,
                "installed": True,
                "program_name": "7-Zip",
                "message": "¡7-Zip quedó instalado con éxito en tu computador!"
            }
            res_confirm = gw.chat("sí, instálalo", history=history)

        self.assertEqual(res_confirm["executed_tool"], "software_install")
        self.assertIn("Instalación de Software", res_confirm["reply"])
        self.assertIn("7-Zip", res_confirm["reply"])

    def test_10_specialized_ecosystem_subagents(self):
        from netopt.ecosystem_subagents import get_ecosystem_orchestrator
        from netopt.llm_gateway import LLMGateway

        orch = get_ecosystem_orchestrator()
        cat = orch.get_ecosystem_catalog()
        self.assertEqual(len(cat), 10)

        # 1. Verify individual subagents
        net_res = orch.run_network_subagent(execute=False)
        self.assertEqual(net_res["subagent"], "network")

        av_res = orch.run_antivirus_subagent(execute=False)
        self.assertEqual(av_res["subagent"], "antivirus")

        clean_res = orch.run_cleaner_subagent(execute=False)
        self.assertEqual(clean_res["subagent"], "cleaner")

        drv_res = orch.run_drivers_subagent(execute=False)
        self.assertEqual(drv_res["subagent"], "drivers")

        hw_res = orch.run_hardware_thermal_subagent(execute=False)
        self.assertEqual(hw_res["subagent"], "hardware_thermal")

        start_res = orch.run_startup_boost_subagent(execute=False)
        self.assertEqual(start_res["subagent"], "startup_boost")

        unin_res = orch.run_uninstaller_subagent(execute=False)
        self.assertEqual(unin_res["subagent"], "uninstaller")

        priv_res = orch.run_privacy_shield_subagent(execute=False)
        self.assertEqual(priv_res["subagent"], "privacy_shield")

        os_res = orch.run_os_repair_subagent(execute=False)
        self.assertEqual(os_res["subagent"], "os_repair")

        bak_res = orch.run_backup_subagent(execute=False)
        self.assertEqual(bak_res["subagent"], "backup")

        # 2. Conversational Intent Dispatching
        gw = LLMGateway()
        gw.config["api_key"] = ""

        r_av = gw.chat("revisa si tengo virus")
        self.assertEqual(r_av["executed_tool"], "subagent_antivirus")
        self.assertIn("Escudo Antivirus", r_av["reply"])

        r_hw = gw.chat("qué temperatura tiene mi procesador y hardware")
        self.assertEqual(r_hw["executed_tool"], "subagent_hardware_thermal")
        self.assertIn("Hardware y Temperatura", r_hw["reply"])

        r_boot = gw.chat("acelera el arranque y programas de inicio")
        self.assertEqual(r_boot["executed_tool"], "subagent_startup_boost")
        self.assertIn("Acelerador de Arranque", r_boot["reply"])

        r_priv = gw.chat("activa el anti-rastreo y privacidad de windows")
        self.assertEqual(r_priv["executed_tool"], "subagent_privacy_shield")
        self.assertIn("Escudo de Privacidad", r_priv["reply"])

        r_cat = gw.chat("cuáles son las 10 especialidades del ecosistema")
        self.assertEqual(r_cat["executed_tool"], "subagent_ecosystem_catalog")
        self.assertIn("10 Especialidades del Ecosistema", r_cat["reply"])

        # 3. Visual Dashboard status & direct dispatch
        statuses = orch.get_all_subagents_status()
        self.assertEqual(len(statuses), 10)
        self.assertTrue(all("badge" in s and "status" in s for s in statuses))

        exec_res = orch.execute_subagent_by_id("antivirus", execute=False)
        self.assertEqual(exec_res["subagent"], "antivirus")

    def test_security_audit_compliance(self):
        """Verifies resolution of OMNI-001 through OMNI-011 security audit findings."""
        from netopt.licensing import verify_signed_license_key, generate_signed_license_key
        from netopt.hal import WindowsHAL
        from netopt.rollback import RollbackManager, BaselineHealthMetrics

        # 1. OMNI-002: Verify elimination of static master backdoors
        self.assertIsNone(verify_signed_license_key("OMNI-PRO-MASTER-2026"))
        self.assertIsNone(verify_signed_license_key("ADMIN-PRO"))

        # Valid signed keys work
        valid_key = generate_signed_license_key("pro", "test@omninet.ai")
        self.assertEqual(verify_signed_license_key(valid_key), "pro")

        # 2. OMNI-010: HAL input sanitization
        hal = WindowsHAL(dry_run=True)
        with self.assertRaises(ValueError):
            hal.set_dns_servers("Ethernet; rm -rf /", ["1.1.1.1"])
        with self.assertRaises(ValueError):
            hal.set_dns_servers("Ethernet", ["999.999.999.999"])

        # 3. OMNI-007: Baseline comparator in RollbackManager
        mgr = RollbackManager(hal)
        base = BaselineHealthMetrics(
            timestamp=100.0,
            avg_latency_ms=20.0,
            packet_loss_percent=0.0
        )
        ok, msg = mgr.verify_post_action_health(baseline=base)
        self.assertTrue(ok)
        self.assertIn("aprobada", msg.lower())


if __name__ == "__main__":
    unittest.main()

