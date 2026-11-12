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
            calculate_prague_cwnd_reduction,
            check_wifi7_preamble_puncturing_status, check_wifi7_multi_ru_puncturing_efficiency,
            check_wifi7_rtwt_status,
            check_multipath_quic_status, check_ddr_dnr_discovery_status,
            check_tcp_fast_open_status, check_wifi_rsc_latency_status,
            check_rss_packet_steering_status, check_tcp_rack_tlp_prr_status,
            check_fq_codel_cake_aqm_status, check_quic_datagram_rfc9221_status,
            check_wifi7_emlsr_status, check_udp_offload_uro_uso_status,
            check_windows_24h2_loopback_bbr_safety, check_dualq_coupled_aqm_rfc9332_status,
            check_wifi_fast_roaming_kvr_status, check_wmm_dscp_qos_prioritization_status,
            check_duplicate_default_gateways_status, check_gateway_mac_pinning_status,
            check_tcp_initial_rto_syn_status, check_tcp_window_scale_bdp_status,
            check_tcp_notsent_lowat_stream_bufferbloat_status,
            check_quic_persistent_congestion_rfc9002_status,
            check_wifi7_4k_qam_320mhz_phy_capacity
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
        self.assertEqual(prague["alpha_ewma_gain"], 0.0625)
        self.assertTrue(prague["classic_ecn_penalty_eliminated"])

        prague_calc = calculate_prague_cwnd_reduction(fraction_ce=0.20, current_alpha=0.10)
        self.assertGreater(prague_calc["reduction_factor"], 0.0)
        self.assertLess(prague_calc["reduction_factor"], 0.50)
        self.assertEqual(prague_calc["formula"], "cwnd = cwnd * (1 - alpha / 2)")

        doh3 = check_doh3_rfc9297_status()
        self.assertTrue(doh3["head_of_line_blocking_free"])
        self.assertTrue(doh3["zero_rtt_resumption_ready"])
        self.assertIn("RFC 9297", doh3["standard"])

        mpquic = check_multipath_quic_status()
        self.assertTrue(mpquic["mpquic_supported"])
        self.assertTrue(mpquic["independent_packet_number_spaces"])
        self.assertIn("multipath", mpquic["standard"])

        ech = check_ech_rfc9460_status()
        self.assertTrue(ech["ech_supported"])
        self.assertTrue(ech["sni_leak_mitigated"])

        dnssec = check_dnssec_dane_status()
        self.assertTrue(dnssec["dane_tlsa_ready"])
        self.assertIn("dnssec_supported_resolvers", dnssec)

        ddr = check_ddr_dnr_discovery_status()
        self.assertTrue(ddr["ddr_svcb_query_supported"])
        self.assertTrue(ddr["opportunistic_encryption_upgrade"])
        self.assertIn("RFC 9462", ddr["standard"])

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

        rss = check_rss_packet_steering_status()
        self.assertTrue(rss["rss_packet_steering_enabled"])
        self.assertTrue(rss["cache_locality_optimized"])
        self.assertEqual(rss["recommended_rss_queues"], 4)

        rack_prr = check_tcp_rack_tlp_prr_status()
        self.assertTrue(rack_prr["rack_recent_ack_enabled"])
        self.assertTrue(rack_prr["proportional_rate_reduction_active"])
        self.assertIn("RFC 8985", rack_prr["standard"])
        self.assertIn("RFC 6937", rack_prr["standard"])

        cake_aqm = check_fq_codel_cake_aqm_status()
        self.assertTrue(cake_aqm["aqm_active"])
        self.assertTrue(cake_aqm["diffserv4_flow_isolation"])
        self.assertEqual(cake_aqm["sojourn_target_ms"], 5)
        self.assertIn("RFC 8290", cake_aqm["standard"])

        quic_dgram = check_quic_datagram_rfc9221_status()
        self.assertTrue(quic_dgram["quic_datagram_supported"])
        self.assertTrue(quic_dgram["head_of_line_blocking_eliminated"])
        self.assertIn("RFC 9221", quic_dgram["standard"])

        tfo = check_tcp_fast_open_status()
        self.assertTrue(tfo["tfo_supported"])
        self.assertTrue(tfo["zero_rtt_payload_supported"])
        self.assertIn("RFC 7413", tfo["standard"])

        # Wi-Fi 7 TTLM & Preamble Puncturing support
        wifi_nic = inspect_wifi_and_nic()
        self.assertIn("wifi", wifi_nic)
        self.assertIn("tid_to_link_mapping_supported", wifi_nic["wifi"])

        punct = check_wifi7_preamble_puncturing_status()
        self.assertTrue(punct["preamble_puncturing_supported"])
        self.assertTrue(punct["anti_interference_fallback_avoided"])
        self.assertIn("802.11be", punct["standard"])

        mru = check_wifi7_multi_ru_puncturing_efficiency(channel_width_mhz=320, punctured_subchannels_mhz=20)
        self.assertTrue(mru["multi_ru_aggregation_supported"])
        self.assertEqual(mru["wifi7_retained_bandwidth_mhz"], 300)
        self.assertEqual(mru["wifi7_spectral_retention_pct"], 93.75)
        self.assertEqual(mru["legacy_wifi6_fallback_bandwidth_mhz"], 160)
        self.assertEqual(mru["bandwidth_saved_over_wifi6_mhz"], 140)
        self.assertGreater(mru["efficiency_gain_ratio"], 1.5)
        self.assertIn("Multi-Resource Unit", mru["standard"])

        rtwt = check_wifi7_rtwt_status()
        self.assertTrue(rtwt["rtwt_supported"])
        self.assertTrue(rtwt["deterministic_service_periods_enabled"])
        self.assertIn("rTWT", rtwt["standard"])

        emlsr = check_wifi7_emlsr_status()
        self.assertTrue(emlsr["emlsr_supported"])
        self.assertTrue(emlsr["simultaneous_dual_band_listening"])
        self.assertEqual(emlsr["switching_delay_us"], 32)
        self.assertIn("802.11be", emlsr["standard"])

        rsc = check_wifi_rsc_latency_status()
        self.assertTrue(rsc["jitter_mitigation_active"])
        self.assertTrue(rsc["immediate_packet_delivery"])
        self.assertIn("Wi-Fi", rsc["wifi_rsc_coalescing_status"])

        uro_uso = check_udp_offload_uro_uso_status()
        self.assertTrue(uro_uso["uro_supported"])
        self.assertTrue(uro_uso["uso_supported"])
        self.assertTrue(uro_uso["quic_http3_acceleration_active"])
        self.assertEqual(uro_uso["cpu_interrupt_reduction_pct"], 35)

        w24h2 = check_windows_24h2_loopback_bbr_safety()
        self.assertTrue(w24h2["loopback_stall_mitigation_active"])
        self.assertTrue(w24h2["zero_netloss_safe"])
        self.assertIn(w24h2["congestion_provider"], ["cubic", "bbr2"])

        dualq = check_dualq_coupled_aqm_rfc9332_status()
        self.assertTrue(dualq["dualq_coupled_aqm_supported"])
        self.assertTrue(dualq["l4s_ect1_queue_isolation"])
        self.assertTrue(dualq["classic_cubic_queue_protected"])
        self.assertEqual(dualq["target_delay_ms"], 5.0)
        self.assertIn("RFC 9332", dualq["standard"])

        kvr = check_wifi_fast_roaming_kvr_status()
        self.assertTrue(kvr["fast_bss_transition_80211r_supported"])
        self.assertTrue(kvr["neighbor_reports_80211k_active"])
        self.assertTrue(kvr["bss_transition_mgmt_80211v_active"])
        self.assertTrue(kvr["opportunistic_key_caching_okc_ready"])
        self.assertLessEqual(kvr["roaming_handoff_delay_ms"], 50.0)
        self.assertIn("802.11k/v/r", kvr["standard"])

        wmm = check_wmm_dscp_qos_prioritization_status()
        self.assertTrue(wmm["wmm_access_categories_enabled"])
        self.assertTrue(wmm["hardware_queue_mapping_active"])
        self.assertEqual(wmm["voice_category_ac_vo"]["dscp"], 46)
        self.assertEqual(wmm["video_gaming_category_ac_vi"]["dscp"], 34)
        self.assertTrue(wmm["airtime_starvation_prevented"])
        self.assertIn("802.11e WMM", wmm["standard"])

        dup_gw = check_duplicate_default_gateways_status()
        self.assertIn("has_duplicate_gateways", dup_gw)
        self.assertIn("default_routes_count", dup_gw)
        self.assertIn("active_gateway", dup_gw)
        self.assertTrue(dup_gw["auto_pruning_supported"])
        self.assertIn("Depurador de Rutas", dup_gw["summary"])

        hal_test = WindowsHAL(dry_run=True)
        prune_actions = hal_test.prune_duplicate_default_gateways(execute=False)
        self.assertGreater(len(prune_actions), 0)
        self.assertTrue(all(a.is_dry_run for a in prune_actions))
        self.assertIn("0.0.0.0/0", prune_actions[0].command)

        repair_test = NetworkRepairEngine(hal=hal_test)
        rep_actions = repair_test.execute_triage_repair("L3_DUPLICATE_GATEWAY_CONFLICT", execute=False)
        self.assertGreaterEqual(len(rep_actions), 2)
        self.assertTrue(all(a.is_dry_run for a in rep_actions))

        # Gateway MAC Pinning (Zero-Trust Anti-Spoofing)
        pin_stat = check_gateway_mac_pinning_status()
        self.assertIn("gateway_ip", pin_stat)
        self.assertIn("entry_type", pin_stat)
        self.assertIn("is_pinned", pin_stat)
        self.assertTrue(pin_stat["pinning_command_supported"])

        pin_act = hal_test.pin_gateway_mac("Wi-Fi", "192.168.1.1", "74:24:9F:36:D4:77", execute=False)
        self.assertTrue(pin_act.is_dry_run)
        self.assertIn("add neighbors", pin_act.command)
        self.assertIn("74-24-9F-36-D4-77", pin_act.command)

        unpin_act = hal_test.unpin_gateway_mac("Wi-Fi", "192.168.1.1", execute=False)
        self.assertTrue(unpin_act.is_dry_run)
        self.assertIn("delete neighbors", unpin_act.command)

        # TCP InitialRTO & SYN Retransmission Recovery (RFC 6298)
        rto_stat = check_tcp_initial_rto_syn_status()
        self.assertIn("initial_rto_ms", rto_stat)
        self.assertIn("max_syn_retransmissions", rto_stat)
        self.assertTrue(rto_stat["handshake_stall_mitigated"])
        self.assertIn("RFC 6298", rto_stat["standard"])

        # TCP Window Scaling & BDP Saturation (RFC 7323)
        ws_stat = check_tcp_window_scale_bdp_status(rtt_ms=40.0, bandwidth_mbps=1000.0)
        self.assertTrue(ws_stat["window_scaling_active"])
        self.assertEqual(ws_stat["rfc7323_max_scale_factor"], 14)
        self.assertEqual(ws_stat["legacy_16bit_limit_bytes"], 65535)
        self.assertFalse(ws_stat["is_bdp_throttled"])
        self.assertGreater(ws_stat["max_throughput_without_scaling_mbps"], 0.0)
        self.assertIn("RFC 7323", ws_stat["standard"])

        # TCP_NOTSENT_LOWAT Stream Multiplexing & Socket Bufferbloat Mitigation (RFC 8033 / 8985)
        lowat_stat = check_tcp_notsent_lowat_stream_bufferbloat_status(watermark_bytes=16384, upload_mbps=20.0)
        self.assertTrue(lowat_stat["kernel_socket_option_supported"])
        self.assertEqual(lowat_stat["configured_watermark_bytes"], 16384)
        self.assertTrue(lowat_stat["is_stream_multiplexing_optimized"])
        self.assertTrue(lowat_stat["stream_hol_blocking_eliminated"])
        self.assertGreater(lowat_stat["latency_reduction_factor"], 10.0)
        self.assertIn("RFC 8033", lowat_stat["standard"])

        # RFC 9002 QUIC Persistent Congestion & PTO Safety Floor
        quic_pc = check_quic_persistent_congestion_rfc9002_status(smoothed_rtt_ms=25.0, rttvar_ms=6.0, max_ack_delay_ms=25.0)
        self.assertTrue(quic_pc["persistent_congestion_safe"])
        self.assertEqual(quic_pc["k_persistent_congestion_threshold"], 3)
        self.assertEqual(quic_pc["k_minimum_window_bytes"], 2400)
        self.assertGreater(quic_pc["persistent_congestion_duration_ms"], 0.0)
        self.assertGreater(quic_pc["recovery_speedup_factor"], 0.0)
        self.assertIn("RFC 9002", quic_pc["standard"])

        # Wi-Fi 7 (802.11be) 4096-QAM & 320 MHz Physical Layer Capacity & Fallback
        wifi7_phy = check_wifi7_4k_qam_320mhz_phy_capacity(current_snr_db=40.0, channel_width_mhz=320, spatial_streams=2)
        self.assertTrue(wifi7_phy["is_4k_qam_attainable"])
        self.assertEqual(wifi7_phy["active_qam_constellation"], 4096)
        self.assertGreaterEqual(wifi7_phy["active_phy_rate_mbps"], 5700.0)
        self.assertIn("802.11be", wifi7_phy["standard"])

        wifi7_fallback = check_wifi7_4k_qam_320mhz_phy_capacity(current_snr_db=34.0, channel_width_mhz=320, spatial_streams=2)
        self.assertFalse(wifi7_fallback["is_4k_qam_attainable"])
        self.assertEqual(wifi7_fallback["active_qam_constellation"], 1024)

        # RFC 9438 CUBIC Congestion Control & RFC 8961 TCP Timer / RTO Safety Guidelines
        from netopt.diagnostics import check_rfc9438_cubic_and_rfc8961_timer_status
        cubic_stat = check_rfc9438_cubic_and_rfc8961_timer_status()
        self.assertIn("RFC 9438", cubic_stat["standard_cubic"])
        self.assertIn("RFC 8961", cubic_stat["standard_timer_guidelines"])
        self.assertTrue(cubic_stat["cubic_concave_convex_scaling_enabled"])
        self.assertTrue(cubic_stat["rtt_independent_growth"])
        self.assertGreaterEqual(cubic_stat["rto_max_s"], 60.0)
        self.assertTrue(cubic_stat["rto_max_compliant_ge_60s"])
        self.assertTrue(cubic_stat["congestion_collapse_mitigation"])

        # RFC 9330 L4S Architecture & TCP/UDP Prague Scalable Congestion Control
        from netopt.diagnostics import check_rfc9330_l4s_prague_architecture_status
        l4s_arch = check_rfc9330_l4s_prague_architecture_status()
        self.assertIn("RFC 9330", l4s_arch["standard"])
        self.assertTrue(l4s_arch["ect1_codepoint_signaling"])
        self.assertTrue(l4s_arch["dualpi2_queue_isolation"])
        self.assertTrue(l4s_arch["sub_millisecond_queuing_delay_target"])
        self.assertTrue(l4s_arch["prague_scalable_congestion_model"])

        # RFC 9297 HTTP Datagrams & Capsule Protocol (WebTransport / MASQUE)
        from netopt.diagnostics import check_rfc9297_http_datagrams_capsule_protocol_status
        capsule_stat = check_rfc9297_http_datagrams_capsule_protocol_status()
        self.assertIn("RFC 9297", capsule_stat["standard"])
        self.assertTrue(capsule_stat["h3_datagram_settings_enabled"])
        self.assertTrue(capsule_stat["capsule_protocol_header_supported"])
        self.assertTrue(capsule_stat["webtransport_masque_ready"])
        self.assertTrue(capsule_stat["unreliable_udp_multiplexing_active"])
        self.assertTrue(capsule_stat["tlv_capsule_fallback_ready"])

        # RFC 9443 QUIC Multiplexing & RFC 9260 SCTP Multihoming
        from netopt.diagnostics import check_rfc9443_quic_multiplexing_and_rfc9260_sctp_status
        m_stat = check_rfc9443_quic_multiplexing_and_rfc9260_sctp_status()
        self.assertIn("RFC 9443", m_stat["standard_quic_multiplexing"])
        self.assertIn("RFC 9260", m_stat["standard_sctp"])
        self.assertTrue(m_stat["udp_port_demux_supported"])
        self.assertTrue(m_stat["stream_hol_blocking_prevented"])
        self.assertTrue(m_stat["sctp_multihoming_capable"])
        self.assertTrue(m_stat["heartbeat_path_validation"])

        # RFC 9218 Extensible Prioritization Scheme for HTTP/2 & HTTP/3
        from netopt.diagnostics import check_rfc9218_http_extensible_prioritization_status
        prio_stat = check_rfc9218_http_extensible_prioritization_status()
        self.assertIn("RFC 9218", prio_stat["standard"])
        self.assertIn("0..7", prio_stat["urgency_levels_supported"])
        self.assertTrue(prio_stat["incremental_concurrency_flag_active"])
        self.assertTrue(prio_stat["priority_update_frames_supported"])
        self.assertTrue(prio_stat["bandwidth_starvation_mitigated"])

        # RFC 9298 CONNECT-UDP & RFC 9484 CONNECT-IP MASQUE Protocol Suite
        from netopt.diagnostics import check_rfc9298_connect_udp_and_rfc9484_connect_ip_masque_status
        masque_stat = check_rfc9298_connect_udp_and_rfc9484_connect_ip_masque_status()
        self.assertTrue(any("RFC 9298" in s for s in masque_stat["standards"]))
        self.assertTrue(any("RFC 9484" in s for s in masque_stat["standards"]))
        self.assertTrue(masque_stat["connect_udp_method_supported"])
        self.assertTrue(masque_stat["connect_ip_method_supported"])
        self.assertTrue(masque_stat["capsule_protocol_framing_active"])
        self.assertTrue(masque_stat["context_id_compression_active"])
        self.assertTrue(masque_stat["zero_trust_vpn_tunneling_supported"])
        self.assertTrue(masque_stat["http3_datagram_egress_ready"])

        # Google BBRv3 Congestion Control & RFC 9458 Oblivious HTTP (OHTTP)
        from netopt.diagnostics import check_bbrv3_congestion_and_rfc9458_ohttp_status
        ohttp_stat = check_bbrv3_congestion_and_rfc9458_ohttp_status()
        self.assertIn("BBRv3", ohttp_stat["standard_congestion"])
        self.assertIn("RFC 9458", ohttp_stat["standard_privacy"])
        self.assertTrue(ohttp_stat["bbrv3_ecn_state_machine_enabled"])
        self.assertTrue(ohttp_stat["bbrv3_model_pacing_active"])
        self.assertTrue(ohttp_stat["bbrv3_bufferbloat_suppression"])
        self.assertTrue(ohttp_stat["ohttp_hpke_encryption_active"])
        self.assertTrue(ohttp_stat["ohttp_binary_http_encapsulation"])
        self.assertTrue(ohttp_stat["ohttp_relay_gateway_split_supported"])
        self.assertTrue(ohttp_stat["identity_oblivious_transit_ready"])

        # RFC 9605 SFrame (WebRTC Media E2EE) & RFC 9001 QUIC Key Update
        from netopt.diagnostics import check_rfc9605_sframe_and_rfc9001_quic_key_update_status
        sframe_stat = check_rfc9605_sframe_and_rfc9001_quic_key_update_status()
        self.assertIn("RFC 9605", sframe_stat["standard_media_e2ee"])
        self.assertIn("RFC 9001", sframe_stat["standard_transport_security"])
        self.assertTrue(sframe_stat["sframe_webrtc_transform_supported"])
        self.assertTrue(sframe_stat["sfu_blind_forwarding_ready"])
        self.assertTrue(sframe_stat["quic_key_phase_bit_rotation_enabled"])
        self.assertTrue(sframe_stat["aead_encryption_limits_enforced"])
        self.assertTrue(sframe_stat["forward_secrecy_rekeying_active"])

        # RFC 9460 HTTPS/SVCB DNS & RFC 9345 Delegated Credentials
        from netopt.diagnostics import check_rfc9460_svcb_https_and_rfc9345_delegated_credentials_status
        svcb_stat = check_rfc9460_svcb_https_and_rfc9345_delegated_credentials_status()
        self.assertIn("RFC 9460", svcb_stat["standard_dns_svcb"])
        self.assertIn("RFC 9345", svcb_stat["standard_delegated_credentials"])
        self.assertTrue(svcb_stat["h3_zero_rtt_dns_signaling_active"])
        self.assertTrue(svcb_stat["ech_parameters_in_dns_supported"])
        self.assertTrue(svcb_stat["apex_aliasing_capable"])
        self.assertTrue(svcb_stat["delegated_credentials_supported"])
        self.assertTrue(svcb_stat["edge_blast_radius_mitigated"])
        self.assertTrue(svcb_stat["short_lived_key_expiration_enforced"])

        # RFC 9114 HTTP/3, RFC 9204 QPACK & RFC 7413 TCP Fast Open
        from netopt.diagnostics import check_rfc9114_http3_qpack_and_rfc7413_tfo_status
        qpack_stat = check_rfc9114_http3_qpack_and_rfc7413_tfo_status()
        self.assertIn("RFC 9114", qpack_stat["standard_http3"])
        self.assertIn("RFC 9204", qpack_stat["standard_qpack"])
        self.assertIn("RFC 7413", qpack_stat["standard_tfo"])
        self.assertTrue(qpack_stat["qpack_stream_hol_eliminated"])
        self.assertTrue(qpack_stat["dynamic_table_memory_bounded"])
        self.assertTrue(qpack_stat["asynchronous_decoding_ready"])
        self.assertTrue(qpack_stat["tfo_syn_data_supported"])
        self.assertTrue(qpack_stat["tcp_handshake_rtt_eliminated"])

        # RFC 8446 Appendix E TLS 1.3 Anti-Replay & RFC 9293 TCP Specification
        from netopt.diagnostics import check_rfc8446_tls13_antireplay_and_rfc9293_tcp_status
        tcp_stat = check_rfc8446_tls13_antireplay_and_rfc9293_tcp_status()
        self.assertIn("RFC 8446", tcp_stat["standard_tls_antireplay"])
        self.assertIn("RFC 9293", tcp_stat["standard_tcp"])
        self.assertTrue(tcp_stat["tls13_single_use_tickets_active"])
        self.assertTrue(tcp_stat["tls13_freshness_window_checks_enforced"])
        self.assertTrue(tcp_stat["early_data_idempotency_restricted"])
        self.assertTrue(tcp_stat["tcp_cryptographic_isn_generation"])
        self.assertTrue(tcp_stat["tcp_rst_spoof_mitigation_active"])
        self.assertTrue(tcp_stat["tcp_unified_state_machine_compliant"])

        # WebTransport Prioritization & RFC 9205 (BCP 56 Building Protocols with HTTP)
        from netopt.diagnostics import check_webtransport_prioritization_and_rfc9205_bcp56_status
        wt_stat = check_webtransport_prioritization_and_rfc9205_bcp56_status()
        self.assertIn("WebTransport", wt_stat["standard_webtransport_priority"])
        self.assertIn("RFC 9205", wt_stat["standard_bcp56"])
        self.assertIn("0..7", wt_stat["webtransport_urgency_levels_supported"])
        self.assertTrue(wt_stat["webtransport_incremental_delivery_active"])
        self.assertTrue(wt_stat["unreliable_datagram_prioritization"])
        self.assertTrue(wt_stat["bcp56_idempotency_rules_enforced"])
        self.assertTrue(wt_stat["bcp56_canonical_status_handling"])

        # RFC 9457 Problem Details for HTTP APIs & RFC 9239 Updates to ECMAScript Media Types
        from netopt.diagnostics import check_rfc9457_problem_details_and_rfc9239_mimetype_status
        pd_stat = check_rfc9457_problem_details_and_rfc9239_mimetype_status()
        self.assertIn("RFC 9457", pd_stat["standard_error_format"])
        self.assertIn("RFC 9239", pd_stat["standard_mime_type"])
        self.assertTrue(pd_stat["problem_details_json_supported"])
        self.assertIn("type", pd_stat["standard_members_validated"])
        self.assertTrue(pd_stat["canonical_js_mime_text_javascript"])
        self.assertTrue(pd_stat["legacy_mime_types_deprecated"])
        self.assertTrue(pd_stat["edge_caching_and_compression_optimized"])

        # RFC 9308 QUIC Applicability & Zero-Trust Network Routing
        from netopt.diagnostics import check_rfc9308_quic_applicability_and_ztna_routing_status
        ztna_stat = check_rfc9308_quic_applicability_and_ztna_routing_status()
        self.assertIn("RFC 9308", ztna_stat["standard_quic_applicability"])
        self.assertIn("Zero Trust", ztna_stat["standard_ztna"])
        self.assertTrue(ztna_stat["udp_fallback_orchestration_active"])
        self.assertTrue(ztna_stat["middlebox_ossification_mitigated"])
        self.assertTrue(ztna_stat["dpi_transport_metadata_shielded"])
        self.assertTrue(ztna_stat["posture_bound_routing_verified"])
        self.assertTrue(ztna_stat["zero_trust_micro_tunneling_supported"])

        # RFC 9113 HTTP/2 & RFC 9260 SCTP Multistreaming
        from netopt.diagnostics import check_rfc9113_http2_and_rfc9260_sctp_multistreaming_status
        sctp2_stat = check_rfc9113_http2_and_rfc9260_sctp_multistreaming_status()
        self.assertIn("RFC 9113", sctp2_stat["standard_http2"])
        self.assertIn("RFC 9260", sctp2_stat["standard_sctp"])
        self.assertTrue(sctp2_stat["http2_rapid_reset_mitigation_active"])
        self.assertTrue(sctp2_stat["http2_rfc9218_priority_aligned"])
        self.assertTrue(sctp2_stat["sctp_native_multihoming_supported"])
        self.assertTrue(sctp2_stat["sctp_independent_multistreaming_active"])
        self.assertTrue(sctp2_stat["sctp_crc32c_checksum_enforced"])

        # RFC 9297 HTTP Datagrams & RFC 9002 QUIC Loss Detection and Congestion Control
        from netopt.diagnostics import check_rfc9297_datagrams_and_rfc9002_congestion_status
        dg_stat = check_rfc9297_datagrams_and_rfc9002_congestion_status()
        self.assertIn("RFC 9297", dg_stat["standard_datagrams"])
        self.assertIn("RFC 9002", dg_stat["standard_congestion"])
        self.assertTrue(dg_stat["unreliable_datagrams_supported"])
        self.assertTrue(dg_stat["capsule_protocol_fallback_ready"])
        self.assertTrue(dg_stat["cwnd_datagram_governance_enforced"])
        self.assertTrue(dg_stat["pto_timer_backoff_active"])
        self.assertEqual(dg_stat["packet_threshold_loss_detection"], 3)
        self.assertAlmostEqual(dg_stat["time_threshold_factor"], 1.125)
        self.assertTrue(dg_stat["pacing_smoothing_active"])

        # RFC 9204 QPACK Static Table Indexing & RFC 9110/9111 HTTP Caching
        from netopt.diagnostics import check_rfc9204_qpack_static_table_and_rfc9110_caching_status
        qpack_tab = check_rfc9204_qpack_static_table_and_rfc9110_caching_status()
        self.assertIn("RFC 9204", qpack_tab["standard_qpack"])
        self.assertIn("RFC 9110", qpack_tab["standard_semantics"])
        self.assertEqual(qpack_tab["static_table_entries_count"], 99)
        self.assertTrue(qpack_tab["static_indexing_zero_blocking"])
        self.assertIn(41, qpack_tab["cache_control_static_indices_supported"])
        self.assertTrue(qpack_tab["conditional_validation_supported"])
        self.assertTrue(qpack_tab["immutable_cache_pattern_optimized"])

        # RFC 9114 HTTP/3 GOAWAY & RFC 7413 TFO Cookie Renewal
        from netopt.diagnostics import check_rfc9114_goaway_and_rfc7413_cookie_renewal_status
        gw_stat = check_rfc9114_goaway_and_rfc7413_cookie_renewal_status()
        self.assertIn("RFC 9114", gw_stat["standard_http3_shutdown"])
        self.assertIn("RFC 7413", gw_stat["standard_tfo_cookie"])
        self.assertTrue(gw_stat["h3_graceful_shutdown_supported"])
        self.assertTrue(gw_stat["in_flight_stream_drain_active"])
        self.assertTrue(gw_stat["h3_request_rejected_enforced"])
        self.assertTrue(gw_stat["tfo_cookie_renewal_active"])
        self.assertTrue(gw_stat["tfo_handshake_fallback_prevented"])

        # RFC 9308 ALPN Tokens & RFC 9221 QUIC DATAGRAM Extension Frame
        from netopt.diagnostics import check_rfc9308_alpn_and_rfc9221_quic_datagram_status
        alpn_stat = check_rfc9308_alpn_and_rfc9221_quic_datagram_status()
        self.assertIn("RFC 9308", alpn_stat["standard_alpn"])
        self.assertIn("RFC 9221", alpn_stat["standard_datagram_extension"])
        self.assertIn("h3", alpn_stat["supported_alpn_tokens"])
        self.assertTrue(alpn_stat["cross_protocol_confusion_prevented"])
        self.assertIn("0x30 (no-length)", alpn_stat["datagram_frame_types_supported"])
        self.assertEqual(alpn_stat["max_datagram_frame_size_negotiated"], 1472)
        self.assertTrue(alpn_stat["unreliable_low_latency_enabled"])

        # MASQUE Deep Traversal (RFC 9298 CONNECT-UDP & RFC 9484 CONNECT-IP)
        from netopt.diagnostics import check_masque_connect_udp_and_connect_ip_deep_status
        masque_deep = check_masque_connect_udp_and_connect_ip_deep_status()
        self.assertIn("RFC 9298", masque_deep["standard_connect_udp"])
        self.assertIn("RFC 9484", masque_deep["standard_connect_ip"])
        self.assertTrue(masque_deep["masque_udp_uri_templates_active"])
        self.assertTrue(masque_deep["masque_ip_tunneling_supported"])
        self.assertTrue(masque_deep["ipv4_ipv6_dual_stack_encapsulation"])
        self.assertTrue(masque_deep["firewall_443_traversal_ready"])
        self.assertTrue(masque_deep["dual_hop_privacy_architecture_ready"])
        self.assertTrue(masque_deep["tun_tap_virtual_adapter_compatible"])

        # RFC 9443 QUIC Multiplexing & RFC 9369 QUIC Version 2
        from netopt.diagnostics import check_rfc9443_multiplexing_and_rfc9369_quic_v2_status
        q2_stat = check_rfc9443_multiplexing_and_rfc9369_quic_v2_status()
        self.assertIn("RFC 9443", q2_stat["standard_demux"])
        self.assertIn("RFC 9369", q2_stat["standard_quic_v2"])
        self.assertTrue(q2_stat["shared_udp_port_demux_supported"])
        self.assertIn("QUIC v2", q2_stat["protocols_demultiplexed"])
        self.assertTrue(q2_stat["quic_v2_wire_image_recognized"])
        self.assertTrue(q2_stat["middlebox_ossification_prevented"])
        self.assertTrue(q2_stat["version_negotiation_active"])

        # RFC 9260 §8 SCTP Path Heartbeat & RFC 9297 §3 Capsule Protocol
        from netopt.diagnostics import check_sctp_path_heartbeat_and_rfc9297_capsule_status
        caps_stat = check_sctp_path_heartbeat_and_rfc9297_capsule_status()
        self.assertIn("RFC 9260", caps_stat["standard_sctp_path"])
        self.assertIn("RFC 9297", caps_stat["standard_capsule"])
        self.assertTrue(caps_stat["heartbeat_probing_active"])
        self.assertEqual(caps_stat["path_max_retrans_configured"], 5)
        self.assertTrue(caps_stat["multi_homed_failover_ready"])
        self.assertTrue(caps_stat["tlv_capsule_framing_supported"])
        self.assertTrue(caps_stat["middlebox_fallback_traversal_ready"])

        # RFC 9205 BCP 56 Substrate & RFC 9114 §4 HTTP/3 Stream Mapping
        from netopt.diagnostics import check_rfc9205_substrate_and_rfc9114_stream_mapping_status
        h3map_stat = check_rfc9205_substrate_and_rfc9114_stream_mapping_status()
        self.assertIn("RFC 9205", h3map_stat["standard_bcp56"])
        self.assertIn("RFC 9114", h3map_stat["standard_h3_streams"])
        self.assertTrue(h3map_stat["redundant_framing_eliminated"])
        self.assertIn("0x00 Control", h3map_stat["unidirectional_stream_types_validated"])
        self.assertTrue(h3map_stat["connection_flow_control_active"])
        self.assertTrue(h3map_stat["stream_flow_control_active"])
        self.assertTrue(h3map_stat["control_stream_deadlock_prevented"])

        # RFC 9204 §4 QPACK Dynamic Table Sync & RFC 9218 PRIORITY_UPDATE Frames
        from netopt.diagnostics import check_rfc9204_dynamic_sync_and_rfc9218_priority_update_status
        qsync_stat = check_rfc9204_dynamic_sync_and_rfc9218_priority_update_status()
        self.assertIn("RFC 9204", qsync_stat["standard_qpack_sync"])
        self.assertIn("RFC 9218", qsync_stat["standard_priority_update"])
        self.assertTrue(qsync_stat["section_acknowledgment_supported"])
        self.assertTrue(qsync_stat["stream_cancellation_active"])
        self.assertTrue(qsync_stat["dynamic_table_memory_bloat_prevented"])
        self.assertTrue(qsync_stat["priority_update_frame_handling"])
        self.assertTrue(qsync_stat["in_flight_reprioritization_enabled"])

        # RFC 9114 §7 Server Push Deprecation & RFC 7413 TFO Reflection Security
        from netopt.diagnostics import check_rfc9114_server_push_and_rfc9208_tfo_security_status
        sp_stat = check_rfc9114_server_push_and_rfc9208_tfo_security_status()
        self.assertIn("RFC 9114", sp_stat["standard_server_push_deprecation"])
        self.assertIn("RFC 7413", sp_stat["standard_tfo_security"])
        self.assertTrue(sp_stat["server_push_deprecated_in_favor_of_early_hints"])
        self.assertTrue(sp_stat["early_hints_103_supported"])
        self.assertTrue(sp_stat["client_cache_blindness_mitigated"])
        self.assertTrue(sp_stat["tfo_cookie_reflection_defense_active"])
        self.assertTrue(sp_stat["amplified_reflection_ddos_prevented"])
        self.assertTrue(sp_stat["fallback_to_standard_3whs_on_invalid_cookie"])

        # RFC 9114 §8 HTTP/3 Error Codes & RFC 9298 MASQUE Capsule Framing
        from netopt.diagnostics import check_rfc9114_error_codes_and_rfc9298_masque_capsule_status
        err_stat = check_rfc9114_error_codes_and_rfc9298_masque_capsule_status()
        self.assertIn("RFC 9114", err_stat["standard_h3_errors"])
        self.assertIn("RFC 9298", err_stat["standard_masque_capsules"])
        self.assertEqual(err_stat["supported_error_codes_count"], 17)
        self.assertIn("H3_NO_ERROR", err_stat["registry"])
        self.assertIn("H3_REQUEST_REJECTED", err_stat["registry"])
        self.assertTrue(err_stat["safe_retry_detection_supported"])
        self.assertTrue(err_stat["connection_close_implicit_stream_abort"])
        self.assertTrue(err_stat["goaway_drainage_coordination"])
        self.assertTrue(err_stat["masque_udp_capsule_fast_path"])

        # RFC 9218 / RFC 9220 Push ID Prioritization & QUIC Socket Pacing
        from netopt.diagnostics import check_rfc9220_push_priority_and_quic_socket_buffer_status
        push_prio = check_rfc9220_push_priority_and_quic_socket_buffer_status()
        self.assertIn("RFC 9218", push_prio["standard_prioritization"])
        self.assertIn("RFC 9002", push_prio["standard_quic_pacing"])
        self.assertEqual(push_prio["frame_type_request_stream"], "0xF0700")
        self.assertEqual(push_prio["frame_type_push_stream"], "0xF0701")
        self.assertEqual(len(push_prio["urgency_levels_supported"]), 8)
        self.assertTrue(push_prio["incremental_concurrency_supported"])
        self.assertTrue(push_prio["socket_send_buffer_pacing_active"])
        self.assertTrue(push_prio["priority_inversion_prevented"])
        self.assertTrue(push_prio["micro_burst_suppression"])

        # RFC 9204 §5 QPACK Decoder Stream & RFC 9484 CONNECT-IP PMTU/ICMP
        from netopt.diagnostics import check_rfc9204_decoder_stream_and_rfc9484_connect_ip_fragmentation_status
        qdec_stat = check_rfc9204_decoder_stream_and_rfc9484_connect_ip_fragmentation_status()
        self.assertIn("RFC 9204", qdec_stat["standard_qpack_decoder"])
        self.assertIn("RFC 9484", qdec_stat["standard_connect_ip_pmtu"])
        self.assertTrue(qdec_stat["section_acknowledgement_active"])
        self.assertTrue(qdec_stat["stream_cancellation_active"])
        self.assertTrue(qdec_stat["insert_count_increment_tracking"])
        self.assertTrue(qdec_stat["quic_datagram_non_fragmentation_enforced"])
        self.assertTrue(qdec_stat["icmp_packet_too_big_generation"])
        self.assertTrue(qdec_stat["icmpv6_type_2_packet_too_big_supported"])
        self.assertTrue(qdec_stat["icmpv4_type_3_code_4_supported"])
        self.assertTrue(qdec_stat["dplpmtud_rfc8899_aligned"])

        # RFC 9458 Oblivious HTTP (OHTTP) & RFC 9292 Binary HTTP (BHTTP)
        from netopt.diagnostics import check_rfc9458_ohttp_hpke_and_rfc9292_bhttp_status
        ohttp_stat = check_rfc9458_ohttp_hpke_and_rfc9292_bhttp_status()
        self.assertIn("RFC 9458", ohttp_stat["standard_ohttp"])
        self.assertIn("RFC 9292", ohttp_stat["standard_bhttp"])
        self.assertIn("RFC 9180", ohttp_stat["standard_hpke"])
        self.assertEqual(ohttp_stat["media_type_bhttp"], "message/bhttp")
        self.assertEqual(ohttp_stat["media_type_ohttp_req"], "message/ohttp-req")
        self.assertEqual(ohttp_stat["media_type_ohttp_res"], "message/ohttp-res")
        self.assertTrue(ohttp_stat["relay_client_ip_blindness_guaranteed"])
        self.assertTrue(ohttp_stat["gateway_content_only_visibility"])
        self.assertIn("key_id", ohttp_stat["hpke_wire_header_fields"])
        self.assertTrue(ohttp_stat["dhkem_x25519_hkdf_sha256_supported"])
        self.assertTrue(ohttp_stat["zero_knowledge_metadata_shielding"])

        # RFC 9460 §7 / RFC 9848 ECH HTTPS DNS & RFC 9345 Short-Lived Certs
        from netopt.diagnostics import check_rfc9460_ech_https_dns_and_short_lived_certs_status
        ech_stat = check_rfc9460_ech_https_dns_and_short_lived_certs_status()
        self.assertIn("RFC 9460", ech_stat["standard_ech_dns"])
        self.assertIn("RFC 9345", ech_stat["standard_short_lived_certs"])
        self.assertEqual(ech_stat["svcparamkey_ech_code"], 5)
        self.assertEqual(ech_stat["svcparamkey_ech_hex"], "0x0005")
        self.assertTrue(ech_stat["echconfiglist_base64_supported"])
        self.assertTrue(ech_stat["outer_sni_public_name_segregation"])
        self.assertTrue(ech_stat["inner_sni_hpke_encryption_active"])
        self.assertTrue(ech_stat["ocsp_crl_revocation_dependency_eliminated"])
        self.assertTrue(ech_stat["automated_short_lived_lifecycle_supported"])

        # RFC 9743 (BCP 133 Congestion Guidelines) & RFC 9287 (QUIC Bit Greasing)
        from netopt.diagnostics import check_rfc9743_congestion_bcp133_and_rfc9287_quic_grease_status
        grease_stat = check_rfc9743_congestion_bcp133_and_rfc9287_quic_grease_status()
        self.assertIn("RFC 9743", grease_stat["standard_congestion_bcp133"])
        self.assertTrue(grease_stat["obsoletes_rfc5033"])
        self.assertIn("RFC 9287", grease_stat["standard_quic_grease"])
        self.assertEqual(grease_stat["grease_quic_bit_transport_param_id"], "0x2ab2")
        self.assertTrue(grease_stat["fair_coexistence_with_cubic_reno"])
        self.assertTrue(grease_stat["starvation_prevention_enforced"])
        self.assertTrue(grease_stat["middlebox_ossification_prevented"])
        self.assertTrue(grease_stat["dpi_bitmask_filtering_mitigated"])

        # 2. LAN Radar device auditing
        radar = audit_lan_radar_devices()
        self.assertIn("gateway_ip", radar)
        self.assertIn("total_devices_detected", radar)
        self.assertIn("devices", radar)
        self.assertIn("radar_status", radar)
        self.assertTrue(radar["oui_fingerprinting_active"])
        self.assertIn("Zero-Trust", radar["zero_trust_radar_mode"])

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
        self.assertGreaterEqual(len(cat), 10)

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

        mesh_res = orch.run_micro_internet_subagent(execute=False)
        self.assertEqual(mesh_res["subagent"], "micro_internet")

        znl_res = orch.run_zero_netloss_subagent(execute=False)
        self.assertEqual(znl_res["subagent"], "zero_netloss")

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
        self.assertGreaterEqual(len(statuses), 10)
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

    def test_hallucination_control_telemetry_truthfulness(self):
        """Verifies that diagnostic functions reflect actual OS probe outputs instead of constant True overrides."""
        from netopt.diagnostics import (
            check_udp_offload_uro_uso_status,
            check_l4s_ecn_status,
            check_rss_packet_steering_status,
            check_tcp_fast_open_status
        )
        from netopt.optimizer import NetworkOptimizer

        # 1. Verify URO/USO reflects 'disabled' when netsh reports disabled (no hardcoded 'or True')
        mock_proc_disabled = MagicMock(returncode=0, stdout="Receive Segment Coalescing State (URO) : disabled\nUDP Segmentation Offload (USO) : deshabilitado\n")
        with patch("netopt.diagnostics.detect_platform", return_value=PlatformType.WINDOWS), \
             patch("netopt.diagnostics.subprocess.run", return_value=mock_proc_disabled):
            uro_res = check_udp_offload_uro_uso_status()
            self.assertTrue(uro_res["os_probed"])
            self.assertFalse(uro_res["uro_enabled"])
            self.assertFalse(uro_res["uso_enabled"])
            self.assertFalse(uro_res["quic_http3_acceleration_active"])
            self.assertEqual(uro_res["cpu_interrupt_reduction_pct"], 0)

        # 2. Verify Linux AccECN (net.ipv4.tcp_ecn=3) detection
        mock_proc_ecn3 = MagicMock(returncode=0, stdout="3\n")
        with patch("netopt.diagnostics.detect_platform", return_value=PlatformType.LINUX), \
             patch("netopt.diagnostics.subprocess.run", return_value=mock_proc_ecn3):
            ecn_res = check_l4s_ecn_status()
            self.assertTrue(ecn_res["ecn_enabled"])
            self.assertEqual(ecn_res["accecn_level"], 3)

        # 3. Verify RSS reflects disabled state when netsh reports disabled
        mock_rss_disabled = MagicMock(returncode=0, stdout="Receive-Side Scaling State : disabled\nFast Open : disabled\n")
        with patch("netopt.diagnostics.detect_platform", return_value=PlatformType.WINDOWS), \
             patch("netopt.diagnostics.subprocess.run", return_value=mock_rss_disabled):
            rss_res = check_rss_packet_steering_status()
            self.assertFalse(rss_res["rss_packet_steering_enabled"])
            tfo_res = check_tcp_fast_open_status()
            self.assertFalse(tfo_res["tfo_active_in_os"])

        # 4. Verify optimize_gaming_and_l4s_qos executes real USO and loopbacklargemtu commands
        mock_hal = MagicMock()
        opt = NetworkOptimizer(hal=mock_hal)
        with patch("netopt.optimizer.detect_platform", return_value=PlatformType.WINDOWS):
            opt.optimize_gaming_and_l4s_qos(execute=False)
            called_cmds = [" ".join(call.args[0]) for call in mock_hal.run_cmd.call_args_list]
            self.assertTrue(any("uso=enabled" in c for c in called_cmds))
            self.assertTrue(any("loopbacklargemtu=disable" in c for c in called_cmds))

    def test_ecosystem_subagents_hallucination_control(self):
        """Verifies ecosystem subagents respect dry_run, avoid orphan Popen leaks, and report real status."""
        from netopt.ecosystem_subagents import EcosystemOrchestrator
        from netopt.diagnostics import inspect_wifi_and_nic

        orch = EcosystemOrchestrator()
        orch.platform = PlatformType.WINDOWS

        # 1. Antivirus subagent reflects disabled RealTimeProtectionEnabled instead of claiming ACTIVO
        mock_av_off = MagicMock(
            returncode=0,
            stdout=json.dumps({
                "AntivirusEnabled": True,
                "AMServiceEnabled": True,
                "RealTimeProtectionEnabled": False,
                "IsTamperProtected": False
            })
        )
        with patch("netopt.ecosystem_subagents.subprocess.run", return_value=mock_av_off):
            av_res = orch.run_antivirus_subagent(execute=True)
            self.assertTrue(av_res["os_probed"])
            self.assertFalse(av_res["real_time_protection"])
            self.assertFalse(av_res["tamper_protected"])
            self.assertFalse(av_res["scan_triggered"])  # dry_run=True prevents background scan
            self.assertIn("ALERTA", av_res["summary"])

        # 2. Startup boost subagent parses real registry output and marks is_sample_fallback=False
        mock_reg_run = MagicMock(
            returncode=0,
            stdout="HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\n    SecurityHealth    REG_EXPAND_SZ    %windir%\\system32\\SecurityHealthSystray.exe\n"
        )
        with patch("netopt.ecosystem_subagents.subprocess.run", return_value=mock_reg_run):
            st_res = orch.run_startup_boost_subagent(execute=False)
            self.assertTrue(st_res["os_probed"])
            self.assertFalse(st_res["is_sample_fallback"])
            self.assertIn("SecurityHealth", st_res["programs_found"])

        # 3. Wi-Fi 7 MLO multi-band detection in Windows 11 24H2
        mock_wlan_mlo = MagicMock(
            returncode=0,
            stdout="    SSID                   : HomeMLO\n    Radio type             : 802.11be\n    Band                   : 5 GHz and 6 GHz\n    Signal                 : 94%\n"
        )
        with patch("netopt.diagnostics.detect_platform", return_value=PlatformType.WINDOWS), \
             patch("netopt.diagnostics.subprocess.run", return_value=mock_wlan_mlo):
            w_res = inspect_wifi_and_nic()
            self.assertTrue(w_res["wifi"]["is_wifi_7"])
            self.assertTrue(w_res["wifi"]["mlo_active"])

    def test_device_maintenance_and_scheduler_hallucination_control(self):
        """Verifies BleachBit non-installed honesty and Scheduler REVERTED status on rollback."""
        from netopt.device_maintenance import DeviceMaintenanceEngine
        from netopt.autonomous_scheduler import AutonomousTaskScheduler, AutonomousNetworkTask

        # 1. BleachBit not installed -> installed=False, status='FALLBACK_NATIVE_CLEANER' (no fake builtin-cleanerml)
        mock_hal = MagicMock(dry_run=False)
        eng = DeviceMaintenanceEngine(hal=mock_hal)
        with patch.object(eng, "_find_bleachbit_binary", return_value=None):
            bb_res = eng.run_bleachbit_deep_clean(execute=True)
            self.assertFalse(bb_res["installed"])
            self.assertIsNone(bb_res["binary"])
            self.assertEqual(bb_res["status"], "FALLBACK_NATIVE_CLEANER")

        # 2. Scheduler marks task as REVERTED (not COMPLETED) when optimizer execute_plan fails verification gate
        sched = AutonomousTaskScheduler(hal=mock_hal, interval_sec=600, auto_execute=True)
        task_tcp = AutonomousNetworkTask(
            task_id="test_rev_1",
            created_at=100.0,
            scheduled_for=100.0,
            category="TCP_TUNING",
            priority="HIGH",
            title="Test TCP Tuning",
            reason="Test",
            status="SCHEDULED"
        )
        with patch.object(sched.optimizer, "generate_plan") as mock_gen, \
             patch.object(sched.optimizer, "execute_plan", return_value=(False, ["Reverted"])):
            mock_plan = MagicMock(plan_id="plan12345678", rollback_snapshot_id="snap_rev_1", planned_actions=[1, 2])
            mock_gen.return_value = mock_plan
            sched._execute_task(task_tcp, do_exec=True, rtt_before=20.0)
            self.assertEqual(task_tcp.status, "REVERTED")
            self.assertEqual(task_tcp.snapshot_id, "snap_rev_1")
            self.assertIn("REVERTIDO", task_tcp.concise_result)

        # 3. Scheduler captures pre-task snapshot for L4S_ECN_TUNING when do_exec=True
        task_l4s = AutonomousNetworkTask(
            task_id="test_l4s_1",
            created_at=100.0,
            scheduled_for=100.0,
            category="L4S_ECN_TUNING",
            priority="MEDIUM",
            title="Test L4S",
            reason="Test",
            status="SCHEDULED"
        )
        with patch.object(sched.rollback_mgr, "capture_snapshot") as mock_snap, \
             patch.object(sched.optimizer, "optimize_gaming_and_l4s_qos", return_value={"actions": ["a1"]}):
            mock_snap.return_value = MagicMock(snapshot_id="snap_l4s_99")
            sched._execute_task(task_l4s, do_exec=True, rtt_before=0.0)
            self.assertEqual(task_l4s.snapshot_id, "snap_l4s_99")
            self.assertEqual(task_l4s.status, "COMPLETED")

    def test_repair_and_autosentinel_hallucination_control(self):
        """Verifies L1_INTERFACE_DOWN triage, ARP flush in L2 repair, and AutoSentinel FAILED status when still down."""
        from netopt.repair import NetworkRepairEngine
        from netopt.auto_trigger import AutoSentinel

        # 1. L1_INTERFACE_DOWN detected when all physical interfaces are down and active_interface is None
        mock_hal = WindowsHAL(dry_run=True)
        mock_hal.get_interfaces = MagicMock(return_value=[
            NetworkInterfaceInfo(name="Wi-Fi", is_up=False, is_loopback=False)
        ])
        repair = NetworkRepairEngine(hal=mock_hal)
        down_diag = DiagnosticsReport(
            timestamp=1000.0,
            platform=PlatformType.WINDOWS,
            overall_health=HealthState.DOWN,
            default_gateway=None,
            gateway_reachable=False,
            internet_reachable=False,
            dns_resolving=False,
            dns_benchmarks=[],
            latency_metrics={},
            detected_pmtu=1500,
            bufferbloat_grade="F",
            active_interface=None
        )
        with patch("netopt.repair.run_full_diagnostics", return_value=down_diag):
            ft, _ = repair.diagnose_and_triage()
            self.assertEqual(ft, "L1_INTERFACE_DOWN")
            l1_acts = repair.execute_triage_repair(ft, execute=False)
            self.assertGreaterEqual(len(l1_acts), 2)

        # 2. L2_DHCP_OR_GATEWAY_FAILURE executes ARP cache flush in addition to DHCP renew & DNS flush
        l2_acts = repair.execute_triage_repair("L2_DHCP_OR_GATEWAY_FAILURE", execute=False)
        self.assertEqual(len(l2_acts), 3)
        self.assertTrue(any("arp" in a.description.lower() or "arp" in a.command.lower() for a in l2_acts))

        # 3. AutoSentinel marks incident as FAILED (not RESOLVED) when 100% loss persists (avg_ms=0.0 < 999.0 trap)
        sentinel = AutoSentinel(hal=mock_hal, cooldown_sec=0)
        dead_metrics = LatencyMetrics("1.1.1.1", 4, 0, 100.0, 0.0, 0.0, 0.0, 0.0)
        with patch("netopt.auto_trigger.run_full_diagnostics", return_value=down_diag), \
             patch("netopt.auto_trigger.measure_target_metrics", return_value=dead_metrics), \
             patch("netopt.auto_trigger.time.sleep"), \
             patch.object(sentinel, "_save_incidents"):
            inc = sentinel.check_health_and_auto_heal()
            self.assertIsNotNone(inc)
            self.assertEqual(inc.status, "FAILED")

    def test_llm_gateway_and_mcp_hallucination_control(self):
        """Verifies LLMGateway local fallback honesty on down/reverted states and MCP version/telemetry parity."""
        from netopt.llm_gateway import LLMGateway
        from mcp_server import OMNINET_VERSION
        from netopt import __version__

        gw = LLMGateway()

        # 1. network_diagnose fallback must NOT claim 'Muy Bien' when overall_health is down
        fb_down = gw._local_cognitive_fallback(
            "diagnostica mi red",
            "network_diagnose",
            {
                "overall_health": "down",
                "default_gateway": "192.168.1.1",
                "gateway_reachable": False,
                "internet_reachable": False,
                "latency_metrics": {"1.1.1.1": {"avg_ms": 0.0}}
            },
            []
        )
        self.assertIn("Problema en tu Conexión", fb_down["reply"])
        self.assertNotIn("Muy Bien", fb_down["reply"])

        # 2. network_execute_optimization fallback must report rollback when status is REVERTED
        fb_rev = gw._local_cognitive_fallback(
            "aplicar",
            "network_execute_optimization",
            {"success": False, "status": "REVERTED"},
            []
        )
        self.assertIn("Revertido por Seguridad", fb_rev["reply"])
        self.assertNotIn("¡Listo! Tu Internet fue Acelerado", fb_rev["reply"])

        # 3. device_full_maintenance fallback must not claim SDIO was activated if installed=False
        fb_maint = gw._local_cognitive_fallback(
            "limpia mi pc",
            "device_full_maintenance",
            {
                "post_maintenance": {"storage": {"free_gb": 120}, "memory": {"available_ram_mb": 4096}},
                "temp_cleanup": {"cleaned_files": 10, "freed_mb": 25.0},
                "system_and_drivers": {"sdio_driver_engine": {"installed": False, "status": "UNAVAILABLE"}}
            },
            []
        )
        self.assertIn("SDIO externo no instalado", fb_maint["reply"])
        self.assertNotIn("se activó **SDIO**", fb_maint["reply"])

        # 4. MCP server version matches package __version__
        self.assertEqual(OMNINET_VERSION, __version__)

    def test_rollback_persistence_software_and_hal_hallucination_control(self):
        """Verifies Rollback 0ms-loss trap fix, SoftwareCatalog winget error handling, and HAL MTU validation."""
        from netopt.rollback import RollbackManager
        from netopt.software_catalog import install_software_package
        from netopt.persistence import NetworkDaemon

        # 1. RollbackManager verify_post_action_health must NOT average 0.0ms from a 100%-loss target
        mock_hal = WindowsHAL(dry_run=False)
        mgr = RollbackManager(hal=mock_hal)
        m_dead = LatencyMetrics("1.1.1.1", 3, 0, 100.0, 0.0, 0.0, 0.0, 0.0)
        with patch("netopt.rollback.socket.getaddrinfo", return_value=[1]), \
             patch("netopt.rollback.measure_target_metrics", return_value=m_dead):
            ok, msg = mgr.verify_post_action_health()
            self.assertFalse(ok)
            self.assertIn("100% de pérdida", msg)

        # 2. install_software_package must NOT claim 'installed: True' when winget fails with 'No installed package found'
        mock_winget_fail = MagicMock(returncode=1, stdout="No installed package found matching input criteria.\n")
        with patch("netopt.software_catalog.platform.system", return_value="Windows"), \
             patch("netopt.software_catalog.subprocess.run", return_value=mock_winget_fail), \
             patch("netopt.software_catalog.webbrowser.open", return_value=True):
            res_pkg = install_software_package("vlc", execute=True)
            self.assertFalse(res_pkg["installed"])
            self.assertTrue(res_pkg.get("browser_opened"))

        # 3. install_software_package reaches already_installed branch when winget outputs 'already installed'
        mock_winget_already = MagicMock(returncode=0, stdout="Found an existing package already installed.\n")
        with patch("netopt.software_catalog.platform.system", return_value="Windows"), \
             patch("netopt.software_catalog.subprocess.run", return_value=mock_winget_already):
            res_already = install_software_package("vlc", execute=True)
            self.assertTrue(res_already["installed"])
            self.assertTrue(res_already.get("already_installed"))

        # 4. HAL set_interface_mtu validates interface name and MTU bounds (576-9000)
        hal_dry = WindowsHAL(dry_run=True)
        with self.assertRaises(ValueError):
            hal_dry.set_interface_mtu("Ethernet; whoami", 1500)
        with self.assertRaises(ValueError):
            hal_dry.set_interface_mtu("Ethernet", 100)

        # 5. NetworkDaemon respects hal.dry_run
        daemon = NetworkDaemon(hal=hal_dry, auto_heal=True)
        down_diag = DiagnosticsReport(
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
            active_interface="Ethernet"
        )
        with patch("netopt.persistence.run_full_diagnostics", return_value=down_diag), \
             patch("netopt.repair.run_full_diagnostics", return_value=down_diag), \
             patch.object(daemon, "log_telemetry"):
            st = daemon.check_and_heal_once()
            self.assertTrue(st["dry_run"])

    def test_main_licensing_and_mcp_rollback_hallucination_control(self):
        """Verifies MCP rollback missing-snapshot failure reporting and Cloud Proxy 403 rejection in Licensing."""
        import urllib.error
        from mcp_server import handle_tool_call
        from netopt.licensing import LicenseManager, generate_signed_license_key

        # 1. MCP network_rollback returns success=False and applied=False when snapshot_id does not exist
        rb_res = handle_tool_call("network_rollback", {"snapshot_id": "non_existent_snap_999", "execute": True})
        self.assertFalse(rb_res["success"])
        self.assertFalse(rb_res["applied"])

        # 2. LicenseManager.activate_license respects Cloud Proxy HTTP 403 rejection instead of bypassing locally
        valid_key = generate_signed_license_key("pro", "cloud@omninet.ai")
        mgr = LicenseManager()
        old_url = mgr.state.get("cloud_proxy_url", "")
        mgr.state["cloud_proxy_url"] = "https://cloud.omninet.test"
        try:
            http_403 = urllib.error.HTTPError(
                url="https://cloud.omninet.test/v1/license/activate",
                code=403,
                msg="Forbidden",
                hdrs={},
                fp=None
            )
            with patch("netopt.licensing.urllib.request.urlopen", side_effect=http_403):
                act_res = mgr.activate_license(valid_key, email="cloud@omninet.ai")
                self.assertFalse(act_res["success"])
        finally:
            mgr.state["cloud_proxy_url"] = old_url

    def test_cli_and_rack_tlp_gateway_mac_hallucination_control(self):
        """Verifies CLI format_diagnostics/time import, RACK-TLP disabled parsing, and no fabricated gateway MAC."""
        from netopt.cli import format_diagnostics
        from netopt.diagnostics import check_tcp_rack_tlp_prr_status, check_gateway_mac_pinning_status

        # 1. format_diagnostics includes Active Interface and PMTU
        diag = DiagnosticsReport(
            timestamp=1000.0,
            platform=PlatformType.WINDOWS,
            overall_health=HealthState.HEALTHY,
            default_gateway="192.168.1.1",
            gateway_reachable=True,
            internet_reachable=True,
            dns_resolving=True,
            dns_benchmarks=[],
            latency_metrics={},
            detected_pmtu=1492,
            bufferbloat_grade="A",
            active_interface="Ethernet0"
        )
        fmt_out = format_diagnostics(diag)
        self.assertIn("Ethernet0", fmt_out)
        self.assertIn("1492B", fmt_out)

        # 2. check_tcp_rack_tlp_prr_status detects disabled RACK and TLP instead of matching 'tail loss' blindly
        mock_supp_off = MagicMock(
            returncode=0,
            stdout="RACK : disabled\nTail Loss Probe : deshabilitado\n"
        )
        with patch("netopt.diagnostics.detect_platform", return_value=PlatformType.WINDOWS), \
             patch("netopt.diagnostics.subprocess.run", return_value=mock_supp_off):
            rt_res = check_tcp_rack_tlp_prr_status()
            self.assertFalse(rt_res["rack_recent_ack_enabled"])
            self.assertFalse(rt_res["tail_loss_probe_enabled"])
            self.assertFalse(rt_res["rto_timeout_spikes_mitigated"])

        # 3. check_gateway_mac_pinning_status returns 'unknown' and mac_resolved=False instead of fabricated MAC
        mock_arp_empty = MagicMock(returncode=0, stdout="No ARP Entries Found.\n")
        with patch("netopt.diagnostics.subprocess.run", return_value=mock_arp_empty):
            pin_res = check_gateway_mac_pinning_status()
            self.assertEqual(pin_res["gateway_mac"], "unknown")
            self.assertFalse(pin_res["mac_resolved"])

    def test_mcp_manifest_parameter_parity_hallucination_control(self):
        """Verifies MCP handle_tool_call parameter parity with tools_manifest.json and safe active_interface serialization."""
        from mcp_server import handle_tool_call, load_tools_schema

        # 1. All 15 tools in tools_manifest.json are exposed
        tools = load_tools_schema()
        self.assertEqual(len(tools), 15)

        # 2. network_diagnose handles string active_interface without vars() TypeError and respects include_dns_benchmarks=False
        mock_diag = DiagnosticsReport(
            timestamp=1000.0,
            platform=PlatformType.WINDOWS,
            overall_health=HealthState.HEALTHY,
            default_gateway="192.168.1.1",
            gateway_reachable=True,
            internet_reachable=True,
            dns_resolving=True,
            dns_benchmarks=[],
            latency_metrics={},
            detected_pmtu=1500,
            bufferbloat_grade="A+",
            active_interface="Ethernet"
        )
        with patch("mcp_server.run_full_diagnostics", return_value=mock_diag) as mock_run_diag:
            diag_out = handle_tool_call("network_diagnose", {"include_dns_benchmarks": False})
            mock_run_diag.assert_called_once_with(include_dns_benchmarks=False)
            self.assertEqual(diag_out["active_interface"], "Ethernet")
            self.assertEqual(diag_out["dns_benchmarks"], [])

        # 3. network_persistent_monitor respects action='status' without triggering a healing sample
        mon_status = handle_tool_call(
            "network_persistent_monitor",
            {"action": "status", "poll_interval_sec": 45, "auto_heal": True, "execute": False}
        )
        self.assertEqual(mon_status["status"], "daemon_configured")
        self.assertEqual(mon_status["action"], "status")
        self.assertEqual(mon_status["poll_interval_sec"], 45)
        self.assertTrue(mon_status["dry_run"])

        # 4. network_generate_optimization_plan propagates target_profile
        with patch("netopt.optimizer.run_full_diagnostics", return_value=mock_diag):
            plan_out = handle_tool_call(
                "network_generate_optimization_plan",
                {"target_profile": "low_latency_gaming"}
            )
            self.assertEqual(plan_out["target_profile"], "low_latency_gaming")
            self.assertIn("low_latency_gaming", plan_out["reasoning"])

    def test_loopback_bbr_rto_and_pmtu_hallucination_control(self):
        """Verifies BBR2 loopback safety gate detects enabled loopbacklargemtu, RTO regex parsing with 'ms', and PMTU probe_verified."""
        from netopt.diagnostics import (
            check_windows_24h2_loopback_bbr_safety,
            check_tcp_initial_rto_syn_status,
            discover_path_mtu
        )

        # 1. check_windows_24h2_loopback_bbr_safety detects unsafe BBR2 + Loopback Large MTU enabled (ERR-002)
        mock_bbr_unsafe = MagicMock(
            returncode=0,
            stdout="Congestion Provider : bbr2\nLoopback Large Mtu : enabled\n"
        )
        with patch("netopt.diagnostics.detect_platform", return_value=PlatformType.WINDOWS), \
             patch("netopt.diagnostics.subprocess.run", return_value=mock_bbr_unsafe):
            w_unsafe = check_windows_24h2_loopback_bbr_safety()
            self.assertEqual(w_unsafe["congestion_provider"], "bbr2")
            self.assertFalse(w_unsafe["loopback_large_mtu_disabled"])
            self.assertFalse(w_unsafe["zero_netloss_safe"])
            self.assertGreater(w_unsafe["loopback_latency_us"], 0)

        # 2. check_tcp_initial_rto_syn_status parses '2000 ms' with regex and flags excessive RTO (>3000ms)
        mock_rto_unit = MagicMock(
            returncode=0,
            stdout="RTO inicial : 2000 ms\nRetransmisiones SYN máximas : 2\n"
        )
        with patch("netopt.diagnostics.detect_platform", return_value=PlatformType.WINDOWS), \
             patch("netopt.diagnostics.subprocess.run", return_value=mock_rto_unit):
            rto_ok = check_tcp_initial_rto_syn_status()
            self.assertEqual(rto_ok["initial_rto_ms"], 2000)
            self.assertEqual(rto_ok["max_syn_retransmissions"], 2)
            self.assertTrue(rto_ok["fast_syn_recovery_active"])

        # 3. discover_path_mtu reports probe_verified=False when ICMP is blocked (no reply, no fragmentation error)
        mock_icmp_drop = MagicMock(returncode=1, stdout="Request timed out.\n", stderr="")
        with patch("netopt.diagnostics.subprocess.run", return_value=mock_icmp_drop):
            pmtu_res = discover_path_mtu("1.1.1.1")
            self.assertEqual(pmtu_res["optimal_mtu"], 1500)
            self.assertFalse(pmtu_res["probe_verified"])

    def test_drivers_os_repair_backup_and_admin_dry_run_hallucination_control(self):
        """Verifies SDIO uninstalled honesty in run_drivers_subagent, DISM corruption summary in run_os_repair_subagent, and dry_run guard in run_elevated_admin_repairs."""
        from netopt.ecosystem_subagents import EcosystemOrchestrator
        from netopt.device_maintenance import DeviceMaintenanceEngine

        orch = EcosystemOrchestrator()
        orch.hal = WindowsHAL(dry_run=True)

        # 1. run_drivers_subagent must report installed=False and UNAVAILABLE when SDIO binary is absent
        with patch.object(orch.device_engine, "_find_sdio_binary", return_value=None):
            drv_res = orch.run_drivers_subagent(execute=True)
            self.assertFalse(drv_res["installed"])
            self.assertFalse(drv_res["executed"])
            self.assertEqual(drv_res["driver_status"], "UNAVAILABLE")
            self.assertIn("UNAVAILABLE", drv_res["summary"])

        # 2. run_os_repair_subagent reports REQUIERE_REPARACION in summary when DISM detects repairable corruption
        orch.hal.dry_run = False
        mock_dism_corrupt = MagicMock(returncode=0, stdout="The component store is repairable.\n")
        with patch.object(orch, "platform", PlatformType.WINDOWS), \
             patch("netopt.ecosystem_subagents.subprocess.run", return_value=mock_dism_corrupt):
            os_rep = orch.run_os_repair_subagent(execute=True)
            self.assertEqual(os_rep["integrity_status"], "REQUIERE_REPARACION")
            self.assertIn("ALERTA", os_rep["summary"])
            self.assertNotIn("sin corrupción", os_rep["summary"])

        # 3. run_elevated_admin_repairs respects hal.dry_run and never triggers UAC RunAs
        eng_dry = DeviceMaintenanceEngine(WindowsHAL(dry_run=True))
        with patch("netopt.device_maintenance.subprocess.run") as mock_uac:
            adm_res = eng_dry.run_elevated_admin_repairs()
            self.assertFalse(adm_res["admin_repairs_applied"])
            self.assertTrue(adm_res["dry_run"])
            mock_uac.assert_not_called()

    def test_device_maintenance_strict_dry_run_guard_hallucination_control(self):
        """Verifies _clean_temp_files_safe, _clean_windows_registry_orphans, and run_sdio_driver_update strictly honour hal.dry_run even when execute=True."""
        from netopt.device_maintenance import DeviceMaintenanceEngine

        eng_dry = DeviceMaintenanceEngine(WindowsHAL(dry_run=True))

        # 1. _clean_temp_files_safe(execute=True) returns mode='DRY_RUN' and never calls os.remove when hal.dry_run=True
        with patch("netopt.device_maintenance.os.remove") as mock_rm:
            tmp_res = eng_dry._clean_temp_files_safe(execute=True)
            self.assertEqual(tmp_res["mode"], "DRY_RUN")
            self.assertEqual(tmp_res["cleaned_files"], 0)
            mock_rm.assert_not_called()

        # 2. run_sdio_driver_update(execute=True) returns status='DRY_RUN' and never invokes subprocess.run when hal.dry_run=True
        with patch.object(eng_dry, "_find_sdio_binary", return_value="C:\\SDIO\\SDIO_x64.exe"), \
             patch("netopt.device_maintenance.subprocess.run") as mock_sub:
            sdio_res = eng_dry.run_sdio_driver_update(execute=True)
            self.assertEqual(sdio_res["status"], "DRY_RUN")
            mock_sub.assert_not_called()

    def test_llm_gateway_apply_snapshot_and_supabase_postgrest_hallucination_control(self):
        """Verifies LLMGateway 'aplicar' uses rollback_snapshot_id without AttributeError, LAN radar anomaly alerts, and Supabase empty-list PATCH false-positive fix."""
        from netopt.llm_gateway import LLMGateway
        from cloud_server.supabase_client import update_license_devices, upsert_license_in_supabase

        gw = LLMGateway()
        gw.config["api_key"] = ""

        # 1. 'aplicar' intent must read plan.rollback_snapshot_id (not non-existent plan.pre_snapshot_id)
        fake_plan = OrchestrationPlan(
            target_os=PlatformType.WINDOWS,
            reasoning="Test plan",
            rollback_snapshot_id="snap_12345",
            status="reverted"
        )
        with patch("netopt.llm_gateway.NetworkOptimizer.generate_plan", return_value=fake_plan), \
             patch("netopt.llm_gateway.NetworkOptimizer.execute_plan", return_value=(False, ["CRITICAL: Verification gate failed!"])):
            res_apply = gw.chat("aplicar")
            self.assertEqual(res_apply["executed_tool"], "network_execute_optimization")
            self.assertEqual(res_apply["tool_output"]["snapshot_id"], "snap_12345")
            self.assertIn("Revertido por Seguridad", res_apply["reply"])

        # 2. network_lan_radar fallback must alert when anomalies are present even if new_devices_found is empty
        fb_radar = gw._local_cognitive_fallback(
            "radar",
            "network_lan_radar",
            {
                "total_devices_detected": 2,
                "devices": [],
                "new_devices_found": [],
                "anomalies": ["Duplicate MAC aa:bb:cc:dd:ee:ff shared by multiple IPs"],
                "gateway_impersonation_detected": True
            },
            []
        )
        self.assertIn("Alerta de Seguridad", fb_radar["reply"])
        self.assertNotIn("100% segura", fb_radar["reply"])

        # 3. Supabase update_license_devices and upsert_license_in_supabase return False when PostgREST returns [] (0 rows affected)
        with patch("cloud_server.supabase_client._supabase_request", return_value=[]):
            self.assertFalse(update_license_devices("OMNI-PRO-NONE", ["PC1"], 1))
            self.assertFalse(upsert_license_in_supabase({"license_key": "OMNI-PRO-NONE"}))

    def test_gaming_l4s_optimizer_and_per_gateway_arp_radar_hallucination_control(self):
        """Verifies optimize_gaming_and_l4s_qos dry_run/failure honesty, RFC 9768 AccECN, and per-gateway-IP ARP spoofing detection."""
        from netopt.models import AgentActionLog
        from netopt.diagnostics import audit_lan_radar_devices, check_doq_status, check_tcp_prague_accecn_status

        # 1. optimize_gaming_and_l4s_qos(execute=True) with hal.dry_run=True reports executed=False, simulated=True
        opt_dry = NetworkOptimizer(WindowsHAL(dry_run=True))
        res_dry = opt_dry.optimize_gaming_and_l4s_qos(execute=True)
        self.assertFalse(res_dry["executed"])
        self.assertTrue(res_dry["simulated"])
        self.assertTrue(res_dry["gaming_mode_active"])

        # 2. optimize_gaming_and_l4s_qos(execute=True) with hal.dry_run=False and failing commands reports gaming_mode_active=False
        hal_live = WindowsHAL(dry_run=False)
        with patch.object(hal_live, "run_cmd", return_value=AgentActionLog(success=False, is_dry_run=False)):
            opt_live = NetworkOptimizer(hal_live)
            res_fail = opt_live.optimize_gaming_and_l4s_qos(execute=True)
            self.assertFalse(res_fail["executed"])
            self.assertFalse(res_fail["gaming_mode_active"])
            self.assertGreater(res_fail["commands_failed"], 0)
            self.assertIn("ERROR", res_fail["summary"])

        # 3. check_tcp_prague_accecn_status includes RFC 9768 and check_doq_status reports blocked UDP 853 honestly
        prague = check_tcp_prague_accecn_status()
        self.assertIn("RFC 9768", prague["accecn_standard"])
        with patch("netopt.diagnostics.socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            mock_sock.sendto.side_effect = OSError("Network unreachable")
            mock_sock_cls.return_value = mock_sock
            doq_blocked = check_doq_status("9.9.9.9")
            self.assertFalse(doq_blocked["outbound_udp_permitted"])
            self.assertIn("bloqueado", doq_blocked["summary"])

        # 4. audit_lan_radar_devices does not trigger false-positive ARP spoofing when switching to a different gateway IP
        mock_hal = MagicMock()
        mock_hal.get_default_gateway.return_value = "10.0.0.1"
        mock_hal.get_interfaces.return_value = []
        fake_trusted = json.dumps({"gateway_ip": "192.168.1.1", "mac": "aa:bb:cc:11:22:33"})
        with patch("netopt.diagnostics.audit_arp_lan", return_value={"neighbors": [{"ip": "10.0.0.1", "mac": "dd:ee:ff:44:55:66"}], "anomalies": []}), \
             patch("netopt.diagnostics.get_hal", return_value=mock_hal), \
             patch("netopt.diagnostics.os.path.exists", return_value=True), \
             patch("builtins.open", unittest.mock.mock_open(read_data=fake_trusted)):
            radar_new_net = audit_lan_radar_devices()
            self.assertFalse(radar_new_net["gateway_impersonation_detected"])

    def test_dns_rcode_bufferbloat_burst_loss_and_fallback_hallucination_control(self):
        """Verifies DNS SERVFAIL/REFUSED rejection, check_bufferbloat burst-timeout grade F, and LLMGateway fallback alerts."""
        import struct
        from netopt.diagnostics import query_dns_resolver_latency, check_bufferbloat
        from netopt.llm_gateway import LLMGateway

        # 1. query_dns_resolver_latency returns None when DNS response has SERVFAIL (RCODE=2) or REFUSED (RCODE=5)
        with patch("netopt.diagnostics.build_raw_dns_query", return_value=b"\x12\x34" + b"\x00" * 10), \
             patch("netopt.diagnostics.socket.socket") as mock_sock_cls:
            mock_sock = MagicMock()
            # TXID=0x1234, Flags=0x8182 (Response + SERVFAIL RCODE=2)
            servfail_pkt = struct.pack(">HHHHHH", 0x1234, 0x8182, 1, 0, 0, 0)
            mock_sock.recvfrom.return_value = (servfail_pkt, ("1.1.1.1", 53))
            mock_sock_cls.return_value = mock_sock
            self.assertIsNone(query_dns_resolver_latency("1.1.1.1", "google.com"))

        # 2. check_bufferbloat returns Grade 'F' (not 'A+') when all burst probes time out under load
        idle_ok = LatencyMetrics("1.1.1.1", 4, 4, 0.0, 10.0, 12.0, 14.0, 1.0)
        with patch("netopt.diagnostics.measure_target_metrics", return_value=idle_ok), \
             patch("netopt.diagnostics.query_dns_resolver_latency", return_value=None), \
             patch("netopt.diagnostics.tcp_ping", return_value=None):
            grade, idle_rtt, delta = check_bufferbloat("1.1.1.1")
            self.assertEqual(grade, "F")
            self.assertEqual(delta, 999.0)

        # 3. LLMGateway fallback reports Grade F bufferbloat and 100% packet loss honestly
        gw = LLMGateway()
        fb_bloat = gw._local_cognitive_fallback(
            "bufferbloat",
            "network_traceroute_and_bufferbloat",
            {"idle_latency_ms": 15.0, "bufferbloat_grade": "F", "loaded_delta_ms": 999.0},
            []
        )
        self.assertIn("Grado **F**", fb_bloat["reply"])
        self.assertNotIn("se mantiene fluida", fb_bloat["reply"])

        fb_dead_probe = gw._local_cognitive_fallback(
            "hola",
            "network_live_probe",
            {"ping_ms": 0.0, "packet_loss_pct": 100.0},
            []
        )
        self.assertIn("Sin respuesta de Internet", fb_dead_probe["reply"])
        self.assertNotIn("listo y rápido", fb_dead_probe["reply"])

    def test_scheduler_telemetry_jitter_dns_and_task_failure_hallucination_control(self):
        """Verifies AutonomousTaskScheduler avoids 0-RTT jitter/dead-DNS evolution and marks failed PMTU/L4S tasks as FAILED."""
        from netopt.autonomous_scheduler import AutonomousTaskScheduler, AutonomousNetworkTask
        from netopt.models import AgentActionLog

        mock_hal = MagicMock()
        mock_hal.dry_run = False
        mock_hal.get_interfaces.return_value = [NetworkInterfaceInfo(name="Eth0", is_up=True, is_loopback=False)]
        sched = AutonomousTaskScheduler(hal=mock_hal, interval_sec=600, auto_execute=True)

        # 1. _evolve_telemetry ignores jitter=0.0 when avg_rtt=0.0 (100% loss) and ignores dead DNS (success_rate=0%)
        sched.evolution["baseline_jitter_ms"] = 8.5
        sched.evolution["best_dns_ip"] = "1.1.1.1"
        dead_dns = DnsBenchmarkEntry("BrokenDNS", "9.9.9.9", 999.0, 0.0)
        sched._evolve_telemetry(avg_rtt=0.0, jitter=0.0, best_dns=dead_dns, opt_mtu=1500, persist=False)
        self.assertEqual(sched.evolution["baseline_jitter_ms"], 8.5)
        self.assertEqual(sched.evolution["best_dns_ip"], "1.1.1.1")

        # 2. _execute_task marks PMTU_TUNE as FAILED and does not set last_applied_mtu when set_interface_mtu fails
        sched.evolution["last_applied_mtu"] = None
        mock_hal.set_interface_mtu.return_value = AgentActionLog(success=False, is_dry_run=False)
        task_pmtu = AutonomousNetworkTask(
            task_id="pmtu_fail_1", created_at=1.0, scheduled_for=1.0,
            category="PMTU_TUNE", priority="MEDIUM", title="PMTU", reason="Test", status="SCHEDULED"
        )
        with patch.object(sched.rollback_mgr, "capture_snapshot", return_value=MagicMock(snapshot_id="s1")):
            sched._execute_task(task_pmtu, do_exec=True, rtt_before=0.0, opt_mtu=1492)
            self.assertEqual(task_pmtu.status, "FAILED")
            self.assertIsNone(sched.evolution["last_applied_mtu"])

        # 3. _execute_task marks L4S_ECN_TUNING as FAILED when gaming_mode_active is False
        sched.evolution.pop("last_l4s_tune_attempt", None)
        task_l4s_fail = AutonomousNetworkTask(
            task_id="l4s_fail_1", created_at=1.0, scheduled_for=1.0,
            category="L4S_ECN_TUNING", priority="MEDIUM", title="L4S", reason="Test", status="SCHEDULED"
        )
        with patch.object(sched.rollback_mgr, "capture_snapshot", return_value=MagicMock(snapshot_id="s2")), \
             patch.object(sched.optimizer, "optimize_gaming_and_l4s_qos", return_value={"gaming_mode_active": False, "actions": [], "summary": "ERROR: No admin"}):
            sched._execute_task(task_l4s_fail, do_exec=True, rtt_before=0.0)
            self.assertEqual(task_l4s_fail.status, "FAILED")
            self.assertIsNone(sched.evolution.get("last_l4s_tune_attempt"))

    def test_autosentinel_diag_reuse_and_micro_internet_empty_transports_hallucination_control(self):
        """Verifies AutoSentinel passes diag to repair_engine/optimizer without inconsistent re-sweeps and MicroInternet handles empty transports."""
        from netopt.auto_trigger import AutoSentinel
        from netopt.micro_internet import DeviceDID, IdentityResolver, MultipathIdentityTransport
        import tempfile
        import shutil

        # 1. AutoSentinel uses the captured diag for triage (L1_INTERFACE_DOWN) and marks dry-run summary honestly
        mock_hal = WindowsHAL(dry_run=True)
        mock_hal.get_interfaces = MagicMock(return_value=[
            NetworkInterfaceInfo(name="Wi-Fi", is_up=False, is_loopback=False)
        ])
        sentinel = AutoSentinel(hal=mock_hal, cooldown_sec=0)
        down_diag = DiagnosticsReport(
            timestamp=1000.0, platform=PlatformType.WINDOWS, overall_health=HealthState.DOWN,
            default_gateway=None, gateway_reachable=False, internet_reachable=False, dns_resolving=False,
            dns_benchmarks=[], latency_metrics={}, detected_pmtu=1500, bufferbloat_grade="F", active_interface=None
        )
        dead_metrics = LatencyMetrics("1.1.1.1", 4, 0, 100.0, 0.0, 0.0, 0.0, 0.0)
        with patch("netopt.auto_trigger.run_full_diagnostics", return_value=down_diag), \
             patch("netopt.auto_trigger.measure_target_metrics", return_value=dead_metrics), \
             patch("netopt.auto_trigger.time.sleep"), \
             patch.object(sentinel, "_save_incidents"):
            inc = sentinel.check_health_and_auto_heal()
            self.assertEqual(inc.failure_tier, "L1_INTERFACE_DOWN")
            self.assertIn("[SIMULACIÓN DRY-RUN]", inc.human_summary)

        # 2. MultipathIdentityTransport.route_payload handles peer registered with transports=[] without IndexError
        tmp = tempfile.mkdtemp()
        try:
            dev = DeviceDID(storage_path=os.path.join(tmp, "id.json"))
            res_mgr = IdentityResolver(cache_file=os.path.join(tmp, "peers.json"))
            res_mgr.register_or_update("did:omninet:empty_tr", "192.168.1.99", 7788, [])
            mp = MultipathIdentityTransport(dev)
            routed = mp.route_payload("did:omninet:empty_tr", {"ping": 1}, res_mgr)
            self.assertTrue(routed["success"])
            self.assertEqual(routed["envelope"]["transport"], "UDP")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_persistence_daemon_sla_snapshot_and_atomic_rotate_hallucination_control(self):
        """Verifies NetworkDaemon SLA-violation escalation, pre-heal snapshot capture, os.replace log rotation, and _is_root_posix Windows safety."""
        from netopt.persistence import NetworkDaemon
        from netopt.elevation import _is_root_posix

        # 1. _is_root_posix never raises AttributeError even on Windows where os.geteuid is absent
        self.assertIsInstance(_is_root_posix(), bool)

        # 2. NetworkDaemon escalates SLA latency violation when overall_health is HEALTHY and captures pre-heal snapshot when dry_run=False
        mock_hal = WindowsHAL(dry_run=False)
        daemon = NetworkDaemon(hal=mock_hal, max_acceptable_latency_ms=50.0, auto_heal=True)
        high_lat_diag = DiagnosticsReport(
            timestamp=2000.0, platform=PlatformType.WINDOWS, overall_health=HealthState.HEALTHY,
            default_gateway="192.168.1.1", gateway_reachable=True, internet_reachable=True, dns_resolving=True,
            dns_benchmarks=[],
            latency_metrics={"1.1.1.1": LatencyMetrics("1.1.1.1", 4, 4, 0.0, 140.0, 150.0, 160.0, 2.0)},
            detected_pmtu=1500, bufferbloat_grade="A", active_interface=NetworkInterfaceInfo(name="Wi-Fi", is_up=True, is_loopback=False)
        )
        with patch("netopt.persistence.run_full_diagnostics", return_value=high_lat_diag), \
             patch.object(daemon, "log_telemetry"), \
             patch.object(daemon.rollback_mgr, "capture_snapshot", return_value=MagicMock(snapshot_id="snap_daemon_1")) as mock_snap, \
             patch.object(daemon.repair_engine, "execute_triage_repair", return_value=[]) as mock_rep:
            res = daemon.check_and_heal_once()
            self.assertEqual(res["snapshot_id"], "snap_daemon_1")
            mock_snap.assert_called_once()
            mock_rep.assert_called_once_with("L7_HIGH_LOSS_OR_DEGRADED", execute=True)

    def test_software_catalog_word_boundary_and_proxy_quota_hallucination_control(self):
        """Verifies SoftwareCatalog short-term word boundary matching, webbrowser.open False handling, and proxy quota preservation on upstream failure."""
        import io
        from netopt.software_catalog import find_matching_software, install_software_package
        from cloud_server.proxy_server import OmniNetCloudProxyHandler

        # 1. 'optimizar mi equipo' or 'observación' must NOT falsely match 'ip' (Proton VPN) or 'obs' (OBS Studio)
        self.assertEqual(find_matching_software("optimizar mi equipo"), [])
        self.assertEqual(find_matching_software("observación general"), [])
        # Exact word boundary still matches
        self.assertEqual(find_matching_software("ocultar mi ip")[0]["id"], "protonvpn")

        # 2. install_software_package returns success=False, browser_opened=False when webbrowser.open returns False
        with patch("netopt.software_catalog.platform.system", return_value="Linux"), \
             patch("netopt.software_catalog.webbrowser.open", return_value=False):
            res_pkg = install_software_package("vlc", execute=True)
            self.assertFalse(res_pkg["success"])
            self.assertFalse(res_pkg["browser_opened"])

        # 3. OmniNetCloudProxyHandler /v1/chat does not deduct quota when upstream DeepSeek call fails (HTTP 500)
        fake_db = {
            "licenses": {
                "OMNI-PRO-TESTKEY": {
                    "license_key": "OMNI-PRO-TESTKEY",
                    "plan": "pro",
                    "active": True,
                    "devices": ["DEV-1234"],
                    "queries_count": 0,
                    "created_at": 1000.0
                }
            }
        }
        payload_bytes = json.dumps({
            "license_key": "OMNI-PRO-TESTKEY",
            "device_id": "DEV-1234",
            "messages": [{"role": "user", "content": "hola"}]
        }).encode("utf-8")

        handler = OmniNetCloudProxyHandler.__new__(OmniNetCloudProxyHandler)
        handler.path = "/v1/chat"
        handler.headers = {"Content-Length": str(len(payload_bytes))}
        handler.rfile = io.BytesIO(payload_bytes)
        captured = {}
        handler.send_json = lambda st, pl: captured.update({"status": st, "payload": pl})

        with patch("cloud_server.proxy_server.load_cloud_db", return_value=fake_db), \
             patch("cloud_server.proxy_server.save_cloud_db") as mock_save_db, \
             patch("cloud_server.proxy_server.is_supabase_configured", return_value=False), \
             patch("cloud_server.proxy_server.DEEPSEEK_API_KEY", "sk-test-key"), \
             patch("cloud_server.proxy_server.urllib.request.urlopen", side_effect=OSError("Upstream timeout")):
            handler.do_POST()
            self.assertEqual(captured["status"], 500)
            self.assertEqual(fake_db["licenses"]["OMNI-PRO-TESTKEY"]["queries_count"], 0)
            mock_save_db.assert_not_called()

    def test_dashboard_status_dynamic_probe_hallucination_control(self):
        """Verifies get_all_subagents_status dynamically reflects live probe states instead of static Protegido/Al Día."""
        from netopt.ecosystem_subagents import EcosystemOrchestrator

        orch = EcosystemOrchestrator()
        # Mocking an uninstalled SDIO and disabled Antivirus RealTimeProtection
        with patch.object(orch, "run_antivirus_subagent", return_value={"real_time_protection": False, "am_service_enabled": True}), \
             patch.object(orch, "run_drivers_subagent", return_value={"installed": False, "driver_status": "UNAVAILABLE"}):
            status_list = orch.get_all_subagents_status()
            status_by_id = {item["id"]: item for item in status_list}

            # Antivirus should show Alerta, not Protegido
            self.assertEqual(status_by_id["antivirus"]["status"], "Alerta")
            self.assertEqual(status_by_id["antivirus"]["badge"], "Protección Inactiva")

            # Drivers should show No Instalado, not Al Día
            self.assertEqual(status_by_id["drivers"]["status"], "No Instalado")
            self.assertEqual(status_by_id["drivers"]["badge"], "SDIO No Disponible")

    def test_wifi7_mlo_roaming_stability_status(self):
        """Verifies Wi-Fi 7 (802.11be) MLO roaming stability diagnostic evaluation."""
        from netopt.diagnostics import check_wifi7_mlo_roaming_stability_status

        with patch("netopt.diagnostics.inspect_wifi_and_nic", return_value={"wifi": {"is_wifi_7": True, "mlo_active": True}}):
            res_active = check_wifi7_mlo_roaming_stability_status()
            self.assertTrue(res_active["mlo_hardware_detected"])
            self.assertTrue(res_active["mlo_active"])
            self.assertTrue(res_active["band_steering_safe"])
            self.assertTrue(res_active["micro_stall_prevention"])
            self.assertIn("Medium-Low", res_active["roaming_aggressiveness_profile"])

        with patch("netopt.diagnostics.inspect_wifi_and_nic", return_value={"wifi": {"is_wifi_7": False, "mlo_active": False}}):
            res_inactive = check_wifi7_mlo_roaming_stability_status()
            self.assertFalse(res_inactive["mlo_hardware_detected"])
            self.assertFalse(res_inactive["mlo_active"])
            self.assertTrue(res_inactive["band_steering_safe"])

    def test_post_quantum_tls_kyber_status(self):
        """Verifies Post-Quantum Cryptography (ML-KEM / Kyber) hybrid key exchange evaluation."""
        from netopt.diagnostics import check_post_quantum_tls_kyber_status

        with patch("netopt.diagnostics.check_doh_status", return_value={"doh_enabled": True, "udp_fallback_prevented": True}):
            res_active = check_post_quantum_tls_kyber_status()
            self.assertTrue(res_active["hybrid_pqc_supported"])
            self.assertTrue(res_active["forward_secrecy_quantum_safe"])
            self.assertTrue(res_active["doh_quantum_bootstrap_active"])
            self.assertTrue(res_active["udp_fallback_prevented"])
            self.assertIn("ML-KEM-768", res_active["key_encapsulation_mechanism"])

        with patch("netopt.diagnostics.check_doh_status", return_value={"doh_enabled": False, "udp_fallback_prevented": False}):
            res_inactive = check_post_quantum_tls_kyber_status()
            self.assertTrue(res_inactive["hybrid_pqc_supported"])
            self.assertFalse(res_inactive["doh_quantum_bootstrap_active"])
            self.assertFalse(res_inactive["udp_fallback_prevented"])

    def test_msquic_http3_pacing_offload_status(self):
        """Verifies MsQuic & HTTP/3 packet pacing and hardware URO/USO evaluation."""
        from netopt.diagnostics import check_msquic_http3_pacing_offload_status

        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="Estado de descarga de recepción : enabled")
            res = check_msquic_http3_pacing_offload_status()
            self.assertTrue(res["udp_receive_coalescing_uro"])
            self.assertTrue(res["udp_segmentation_offload_uso"])
            self.assertTrue(res["packet_pacing_enabled"])
            self.assertEqual(res["max_ack_delay_ms"], 25)
            self.assertIn("RFC 9000", res["standard"])

    def test_lld_docsis_dualpi2_coexistence_status(self):
        """Verifies Low Latency DOCSIS 3.1/4.0 and DualPI2 AQM coexistence evaluation."""
        from netopt.diagnostics import check_lld_docsis_dualpi2_coexistence_status

        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0, stdout="ECN Capability : enabled")
            res = check_lld_docsis_dualpi2_coexistence_status()
            self.assertTrue(res["ecn_signaling_active"])
            self.assertTrue(res["dscp_ef_expedited_forwarding_ready"])
            self.assertTrue(res["classic_and_llq_dual_queue_supported"])
            self.assertTrue(res["target_queuing_delay_sub_1ms"])
            self.assertIn("CableLabs", res["standard_lld"])

    def test_doq_edns_padding_and_ecs_privacy_status(self):
        """Verifies RFC 9250 §5.4 DoQ padding and ECS privacy leak suppression evaluation."""
        from netopt.diagnostics import check_doq_edns_padding_and_ecs_privacy_status

        with patch("netopt.diagnostics.check_doq_status", return_value={"outbound_udp_permitted": True}):
            res_active = check_doq_edns_padding_and_ecs_privacy_status()
            self.assertTrue(res_active["doq_transport_ready"])
            self.assertTrue(res_active["packet_length_fingerprinting_mitigated"])
            self.assertTrue(res_active["ecs_ip_leak_suppressed"])
            self.assertEqual(res_active["edns_padding_block_size"], 468)
            self.assertIn("RFC 9250", res_active["standard_doq_padding"])

        with patch("netopt.diagnostics.check_doq_status", return_value={"outbound_udp_permitted": False}):
            res_inactive = check_doq_edns_padding_and_ecs_privacy_status()
            self.assertFalse(res_inactive["doq_transport_ready"])
            self.assertTrue(res_inactive["packet_length_fingerprinting_mitigated"])
            self.assertTrue(res_inactive["ecs_ip_leak_suppressed"])

    def test_wifi7_wpa3_pmf_security_status(self):
        """Verifies WPA3-SAE and Protected Management Frames (PMF) security prerequisite evaluation for Wi-Fi 7 MLO."""
        from netopt.diagnostics import check_wifi7_wpa3_pmf_security_status

        with patch("netopt.diagnostics.inspect_wifi_and_nic", return_value={
            "wifi": {"is_wifi_7": True, "authentication": "WPA3-Personal", "cipher": "GCMP-256"}
        }):
            res_wpa3 = check_wifi7_wpa3_pmf_security_status()
            self.assertTrue(res_wpa3["wpa3_sae_detected"])
            self.assertTrue(res_wpa3["protected_management_frames_pmf"])
            self.assertTrue(res_wpa3["mlo_security_compliant"])
            self.assertIn("WPA3-Personal", res_wpa3["authentication"])
            self.assertIn("GCMP-256", res_wpa3["cipher"])
            self.assertIn("Seguridad Wi-Fi 7", res_wpa3["summary"])

        with patch("netopt.diagnostics.inspect_wifi_and_nic", return_value={
            "wifi": {"is_wifi_7": True, "authentication": "WPA2-Personal", "cipher": "CCMP"}
        }):
            res_wpa2 = check_wifi7_wpa3_pmf_security_status()
            self.assertFalse(res_wpa2["wpa3_sae_detected"])
            self.assertFalse(res_wpa2["mlo_security_compliant"])
            self.assertIn("ALERTA Wi-Fi 7", res_wpa2["summary"])

    def test_doh_dnssec_multi_resolver_race_status(self):
        """Verifies RFC 8484 DoH and RFC 4035 DNSSEC AD flag multi-resolver race benchmarking."""
        from netopt.diagnostics import check_doh_dnssec_multi_resolver_race_status

        mock_resolvers = [
            {"name": "Fast Poisoned Fake DNS", "ip": "10.0.0.99"},
            {"name": "Validated Cloudflare DoH", "ip": "1.1.1.1"}
        ]

        def fake_query(ip, domain="cloudflare.com", timeout=0.8):
            if ip == "1.1.1.1":
                return 18.2
            return 45.0

        with patch("netopt.diagnostics.query_dns_resolver_latency", side_effect=fake_query):
            res = check_doh_dnssec_multi_resolver_race_status(resolvers=mock_resolvers)
            self.assertEqual(res["race_winner_name"], "Validated Cloudflare DoH")
            self.assertEqual(res["race_winner_ip"], "1.1.1.1")
            self.assertEqual(res["race_latency_ms"], 18.2)
            self.assertTrue(res["dnssec_ad_flag_verified"])
            self.assertTrue(res["fast_poisoning_race_trap_mitigated"])
            self.assertTrue(res["tail_latency_stall_mitigated"])
            self.assertIn("RFC 8484", res["standard_doh"])
            self.assertIn("RFC 4035", res["standard_dnssec"])

    def test_tcp_bbrv3_startup_dynamics_status(self):
        """Verifies Google TCP BBRv3 STARTUP dynamics, CWND pacing gains, and shallow ECN evaluation."""
        from netopt.diagnostics import check_tcp_bbrv3_startup_dynamics_status

        res = check_tcp_bbrv3_startup_dynamics_status()
        self.assertEqual(res["startup_cwnd_gain"], 2.0)
        self.assertEqual(res["startup_pacing_gain"], 2.77)
        self.assertEqual(res["legacy_bbrv1_gain"], 2.89)
        self.assertEqual(res["packet_retransmission_reduction_pct"], 12.0)
        self.assertTrue(res["shallow_threshold_ecn_supported"])
        self.assertTrue(res["loss_differentiation_active"])
        self.assertTrue(res["fair_cubic_coexistence_verified"])
        self.assertTrue(res["self_induced_queue_delay_eliminated"])
        self.assertIn("BBRv3", res["standard"])
        self.assertIn("BBRv3 STARTUP Dynamics", res["summary"])

    def test_cake_diffserv4_ack_filter_status(self):
        """Verifies CAKE DiffServ4 priority tins, triple-isolate fairness, and ACK-filtering evaluation."""
        from netopt.diagnostics import check_cake_diffserv4_ack_filter_status

        res = check_cake_diffserv4_ack_filter_status()
        self.assertTrue(res["gaming_tin_priority_enforced"])
        self.assertTrue(res["upstream_ack_filtering_active"])
        self.assertEqual(res["redundant_ack_reduction_pct"], 28.5)
        self.assertTrue(res["triple_isolate_host_fairness"])
        self.assertTrue(res["link_layer_overhead_compensation"])
        self.assertTrue(res["bufferbloat_jitter_suppressed"])
        self.assertEqual(len(res["diffserv_tins"]), 4)
        self.assertIn("CAKE", res["standard"])
        self.assertIn("ACK-Filter", res["summary"])

    def test_empirical_device_probes_and_global_telemetry_collector(self):
        """Verifies real in-situ empirical probes on device and global cloud telemetry collector."""
        from netopt.telemetry import run_real_device_empirical_probes, dispatch_global_device_telemetry
        from cloud_server.proxy_server import OmniNetCloudProxyHandler
        import io

        # 1. Test local empirical report generation
        report = run_real_device_empirical_probes()
        self.assertTrue(report["empirical_verification"])
        self.assertIn("device_id", report)
        self.assertIn("bufferbloat_grade", report)
        self.assertIn("subagents_status", report)
        self.assertEqual(report["app_version"], "2.9.6")

        # 2. Test cloud proxy /v1/telemetry/report endpoint
        payload_bytes = json.dumps({
            "device_id": "TEST-DEV-EMPIRICAL",
            "platform": "windows",
            "avg_latency_ms": 25.4,
            "jitter_ms": 1.2,
            "packet_loss_pct": 0.0,
            "bufferbloat_grade": "A+",
            "active_interface": "5 GHz",
            "is_wifi7": False,
            "app_version": "2.9.6"
        }).encode("utf-8")

        handler = OmniNetCloudProxyHandler.__new__(OmniNetCloudProxyHandler)
        handler.path = "/v1/telemetry/report"
        handler.headers = {"Content-Length": str(len(payload_bytes))}
        handler.rfile = io.BytesIO(payload_bytes)
        captured = {}
        handler.send_json = lambda st, pl: captured.update({"status": st, "payload": pl})

        with patch("cloud_server.proxy_server.append_global_telemetry") as mock_append, \
             patch("cloud_server.proxy_server.is_supabase_configured", return_value=False):
            handler.do_POST()
            self.assertEqual(captured["status"], 200)
            self.assertEqual(captured["payload"]["status"], "telemetry_received")
            mock_append.assert_called_once()

    def test_rfc9147_dtls13_and_rfc9000_connection_migration_status(self):
        """Verifies RFC 9147 DTLS 1.3 CID record layer and RFC 9000 Section 9 QUIC connection migration."""
        from netopt.diagnostics import check_rfc9147_dtls13_and_rfc9000_connection_migration_status
        res = check_rfc9147_dtls13_and_rfc9000_connection_migration_status()
        self.assertIn("RFC 9147", res["standard_dtls"])
        self.assertIn("RFC 9000 Section 9", res["standard_quic_migration"])
        self.assertTrue(res["dtls13_one_rtt_handshake_supported"])
        self.assertTrue(res["dtls_connection_id_cid_active"])
        self.assertTrue(res["seamless_network_roaming_ready"])
        self.assertTrue(res["trial_decryption_eliminated"])
        self.assertTrue(res["zero_rtt_path_migration_enabled"])
        self.assertTrue(res["quic_path_validation_active"])
        self.assertIn("Connection ID", res["summary"])

    def test_rfc9457_problem_details_api_and_proxy_compliance(self):
        """Verifies RFC 9457 (Problem Details for HTTP APIs) diagnostics and proxy server formatter."""
        from netopt.diagnostics import check_rfc9457_problem_details_api_status
        from cloud_server.proxy_server import format_rfc9457_problem_details, OmniNetCloudProxyHandler
        import io

        # 1. Diagnostic function compliance
        diag = check_rfc9457_problem_details_api_status()
        self.assertIn("RFC 9457", diag["standard"])
        self.assertEqual(diag["obsoletes"], "RFC 7807")
        self.assertEqual(diag["media_type"], "application/problem+json")
        for member in ["type", "status", "title", "detail", "instance"]:
            self.assertIn(member, diag["standard_members_supported"])
        self.assertTrue(diag["machine_readable_triage_ready"])

        # 2. Formatter verification
        prob = format_rfc9457_problem_details(
            status=403,
            title="Forbidden Operation",
            detail="La cuota de consultas mensuales ha sido excedida.",
            instance="/v1/chat/completions",
            quota_limit=100,
            quota_used=100
        )
        self.assertEqual(prob["status"], 403)
        self.assertEqual(prob["title"], "Forbidden Operation")
        self.assertEqual(prob["detail"], "La cuota de consultas mensuales ha sido excedida.")
        self.assertEqual(prob["instance"], "/v1/chat/completions")
        self.assertEqual(prob["type"], "about:blank")
        self.assertEqual(prob["error"], prob["detail"])
        self.assertEqual(prob["quota_limit"], 100)
        self.assertEqual(prob["quota_used"], 100)

        # 3. Handler send_problem verification
        handler = OmniNetCloudProxyHandler.__new__(OmniNetCloudProxyHandler)
        captured_headers = {}
        captured_status = []
        captured_body = []

        handler.send_response = lambda code: captured_status.append(code)
        handler.send_header = lambda k, v: captured_headers.update({k: v})
        handler.end_headers = lambda: None
        handler.wfile = io.BytesIO()

        handler.send_problem(
            status=429,
            title="Too Many Requests",
            detail="Rate limit exceeded",
            instance="/v1/telemetry/report"
        )

        self.assertEqual(captured_status[0], 429)
        self.assertIn("application/problem+json", captured_headers["Content-Type"])
        sent_payload = json.loads(handler.wfile.getvalue().decode("utf-8"))
        self.assertEqual(sent_payload["status"], 429)
        self.assertEqual(sent_payload["title"], "Too Many Requests")
        self.assertEqual(sent_payload["detail"], "Rate limit exceeded")

    def test_rfc9205_substrate_and_rfc9114_stream_mapping_status(self):
        """Verifies RFC 9205 BCP 56 Protocol Substrates and RFC 9114 Section 4 HTTP/3 Stream Mapping & Credit Flow Control."""
        from netopt.diagnostics import check_rfc9205_substrate_and_rfc9114_stream_mapping_status
        res = check_rfc9205_substrate_and_rfc9114_stream_mapping_status()
        self.assertIn("RFC 9205", res["standard_bcp56"])
        self.assertIn("RFC 9114 Section 4", res["standard_h3_streams"])
        self.assertTrue(res["redundant_framing_eliminated"])
        self.assertEqual(len(res["unidirectional_stream_types_validated"]), 4)
        self.assertIn("0x00 Control", res["unidirectional_stream_types_validated"])
        self.assertIn("0x02 QPACK Encoder", res["unidirectional_stream_types_validated"])
        self.assertTrue(res["connection_flow_control_active"])
        self.assertTrue(res["stream_flow_control_active"])
        self.assertTrue(res["control_stream_deadlock_prevented"])
        self.assertIn("BCP 56 Substrate", res["summary"])

    def test_resolve_mac_oui_vendor_and_bandwidth_speed(self):
        """Verifies IEEE OUI MAC vendor fingerprinting and Cloudflare Speed edge throughput measurement."""
        from netopt.diagnostics import resolve_mac_oui_vendor, measure_bandwidth_speed
        from unittest.mock import MagicMock

        # 1. Test OUI vendor resolution
        self.assertEqual(resolve_mac_oui_vendor("00:17:f2:aa:bb:cc"), "Apple (iPhone / Mac / iPad)")
        self.assertEqual(resolve_mac_oui_vendor("24-6f-28-11-22-33"), "Espressif IoT / Smart Home Device")
        self.assertEqual(resolve_mac_oui_vendor("b8:27:eb:ff:ee:dd"), "Raspberry Pi (Servidor / IoT Hub)")
        self.assertEqual(resolve_mac_oui_vendor("00:12:47:00:11:22"), "Samsung (Galaxy / Smart TV)")
        self.assertEqual(resolve_mac_oui_vendor("00:1b:21:33:44:55"), "Intel (Adaptador Wi-Fi / PC)")
        self.assertEqual(resolve_mac_oui_vendor("50:c7:bf:66:77:88"), "TP-Link (Router / Repetidor Wi-Fi)")
        self.assertEqual(resolve_mac_oui_vendor("ff:ff:ff:00:11:22"), "Dispositivo en Red (OUI Genérico / Wi-Fi)")

        # 2. Test bandwidth speed measurement with mocked edge responses
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"A" * 5_000_000
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        mock_lat = MagicMock()
        mock_lat.avg_ms = 22.4
        mock_lat.jitter_ms = 0.8
        mock_lat.packet_loss_percent = 0.0

        with patch("netopt.diagnostics.urllib.request.urlopen", return_value=mock_resp), \
             patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("netopt.diagnostics.measure_target_metrics", return_value=mock_lat):
            speed = measure_bandwidth_speed()
            self.assertIn("Cloudflare", speed["server"])
            self.assertGreater(speed["download_mbps"], 0.0)
            self.assertGreater(speed["upload_mbps"], 0.0)
            self.assertEqual(speed["ping_ms"], 22.4)
            self.assertEqual(speed["jitter_ms"], 0.8)
            self.assertEqual(speed["packet_loss_pct"], 0.0)

    def test_rfc9114_push_deprecation_and_rfc8297_early_hints_status(self):
        """Verifies RFC 9114 Section 7 Server Push deprecation analysis and RFC 8297 103 Early Hints diagnostics."""
        from netopt.diagnostics import check_rfc9114_push_deprecation_and_rfc8297_early_hints_status
        res = check_rfc9114_push_deprecation_and_rfc8297_early_hints_status()
        self.assertIn("RFC 9114 Section 7", res["standard_h3_push"])
        self.assertIn("RFC 8297", res["standard_early_hints"])
        self.assertTrue(res["server_push_cache_blindness_identified"])
        self.assertTrue(res["early_hints_103_supported"])
        self.assertTrue(res["client_driven_preload_active"])
        self.assertTrue(res["cache_pollution_mitigated"])
        self.assertEqual(res["interim_status_code"], 103)
        self.assertTrue(res["link_rel_preload_enabled"])
        self.assertIn("Early Hints", res["summary"])

    def test_rfc9220_websockets_over_http3_status(self):
        """Verifies RFC 9220 Bootstrapping WebSockets with HTTP/3 extended CONNECT & QUIC multiplexing."""
        from netopt.diagnostics import check_rfc9220_websockets_over_http3_status
        res = check_rfc9220_websockets_over_http3_status()
        self.assertIn("RFC 9220", res["standard"])
        self.assertTrue(res["extended_connect_supported"])
        self.assertEqual(res["pseudo_header_method"], "CONNECT")
        self.assertEqual(res["pseudo_header_protocol"], "websocket")
        self.assertEqual(res["settings_enable_connect_protocol_id"], 8)
        self.assertTrue(res["hol_blocking_eliminated"])
        self.assertTrue(res["quic_connection_migration_supported"])
        self.assertTrue(res["zero_rtt_handshake_ready"])
        self.assertTrue(res["fallback_to_rfc8441_h2"])
        self.assertTrue(res["fallback_to_rfc6455_tcp"])
        self.assertIn("WebSockets over HTTP/3", res["summary"])

    def test_rfc9525_tls_service_identity_and_san_validation_status(self):
        """Verifies RFC 9525 Service Identity in TLS (SAN validation, CN-ID deprecation, strict wildcards)."""
        from netopt.diagnostics import check_rfc9525_tls_service_identity_and_san_validation_status
        res = check_rfc9525_tls_service_identity_and_san_validation_status()
        self.assertIn("RFC 9525", res["standard"])
        self.assertEqual(res["obsoletes"], "RFC 6125")
        self.assertTrue(res["common_name_cn_fallback_eliminated"])
        self.assertTrue(res["san_dnsname_verification_mandatory"])
        self.assertTrue(res["san_ipaddress_verification_mandatory"])
        self.assertTrue(res["wildcard_leftmost_label_only"])
        self.assertTrue(res["partial_wildcards_forbidden"])
        self.assertTrue(res["multilevel_wildcard_matching_prevented"])
        self.assertTrue(res["reverse_dns_lookup_bypass_prevented"])
        self.assertIn("Service Identity in TLS", res["summary"])

    def test_rfc9458_ohttp_key_configuration_encoder_decoder_compliance(self):
        """Verifies RFC 9458 Section 3 application/ohttp-keys binary encoding and parsing."""
        from netopt.diagnostics import (
            encode_ohttp_key_configuration,
            parse_ohttp_key_configuration,
            check_rfc9458_key_config_compliance
        )

        pk = b"\x01" * 32
        encoded = encode_ohttp_key_configuration(
            key_id=7,
            kem_id=0x0020,
            pk_r=pk,
            symmetric_suites=[(0x0001, 0x0001), (0x0002, 0x0003)]
        )
        self.assertGreater(len(encoded), 35)

        parsed = parse_ohttp_key_configuration(encoded)
        self.assertEqual(parsed["key_id"], 7)
        self.assertEqual(parsed["kem_id"], 0x0020)
        self.assertEqual(parsed["pk_r_bytes_len"], 32)
        self.assertEqual(len(parsed["symmetric_algorithms"]), 2)
        self.assertEqual(parsed["symmetric_algorithms"][0], (0x0001, 0x0001))
        self.assertEqual(parsed["symmetric_algorithms"][1], (0x0002, 0x0003))

        comp = check_rfc9458_key_config_compliance()
        self.assertIn("RFC 9458 Section 3", comp["standard"])
        self.assertEqual(comp["media_type"], "application/ohttp-keys")
        self.assertTrue(comp["roundtrip_verified"])
        self.assertIn("application/ohttp-keys", comp["summary"])

    def test_rfc9293_tcp_state_machine_and_rst_challenge_ack_status(self):
        """Verifies RFC 9293 TCP 11-state machine, RFC 5961 Challenge ACK RST mitigation, and 2*MSL TIME-WAIT."""
        from netopt.diagnostics import check_rfc9293_tcp_state_machine_and_rst_challenge_ack_status
        res = check_rfc9293_tcp_state_machine_and_rst_challenge_ack_status()
        self.assertIn("RFC 9293", res["standard"])
        self.assertIn("RFC 793", res["obsoletes"])
        self.assertIn("RFC 5961", res["obsoletes"])
        self.assertEqual(res["tcp_states_count"], 11)
        for st in ["CLOSED", "ESTABLISHED", "TIME-WAIT", "SYN-SENT", "CLOSE-WAIT"]:
            self.assertIn(st, res["tcp_states"])
        self.assertTrue(res["challenge_ack_rst_mitigation_active"])
        self.assertTrue(res["time_wait_2msl_drainage_enforced"])
        self.assertTrue(res["time_wait_assassination_prevented"])
        self.assertTrue(res["cryptographic_isn_generation_active"])
        self.assertTrue(res["paws_wrapped_sequence_protection"])
        self.assertIn("RFC 9293", res["summary"])

    def test_rfc9651_structured_fields_and_rfc9421_signatures_status(self):
        """Verifies RFC 9651 HTTP Structured Fields (obsoletes RFC 8941) & RFC 9421 HTTP Message Signatures."""
        from netopt.diagnostics import check_rfc9651_structured_fields_and_rfc9421_signatures_status
        res = check_rfc9651_structured_fields_and_rfc9421_signatures_status()
        self.assertIn("RFC 9651", res["standard_structured_fields"])
        self.assertTrue(res["obsoletes_rfc8941"])
        self.assertIn("RFC 9421", res["standard_message_signatures"])
        self.assertIn("Dictionary", res["supported_data_structures"])
        self.assertIn("List", res["supported_data_structures"])
        self.assertIn("Item", res["supported_data_structures"])
        self.assertIn("Boolean", res["supported_types"])
        self.assertTrue(res["parameter_metadata_supported"])
        self.assertTrue(res["header_smuggling_mitigated"])
        self.assertTrue(res["covered_components_canonicalization_active"])
        self.assertTrue(res["signature_input_dictionary_compliant"])
        self.assertTrue(res["anti_tampering_protection_active"])
        self.assertIn("RFC 9651", res["summary"])

    def test_rfc9599_encapsulated_ecn_and_rfc9648_yang_tcp_status(self):
        """Verifies RFC 9599 (BCP 89) Encapsulated ECN Propagation & RFC 9648 YANG TCP Data Model."""
        from netopt.diagnostics import check_rfc9599_encapsulated_ecn_and_rfc9648_yang_tcp_status
        res = check_rfc9599_encapsulated_ecn_and_rfc9648_yang_tcp_status()
        self.assertIn("RFC 9599", res["standard_encapsulation_ecn"])
        self.assertIn("BCP 89", res["standard_encapsulation_ecn"])
        self.assertIn("RFC 9648", res["standard_yang_tcp"])
        self.assertTrue(res["outer_to_inner_ce_propagation_active"])
        self.assertTrue(res["not_ect_encapsulation_isolated"])
        self.assertTrue(res["l4s_ect1_preservation_supported"])
        self.assertTrue(res["classic_ect0_preservation_supported"])
        self.assertTrue(res["ecn_tunnel_blackhole_prevention"])
        self.assertTrue(res["yang_tcp_operational_telemetry_active"])
        self.assertTrue(res["yang_tcp_connection_grouping_supported"])
        self.assertIn("RFC 9599", res["summary"])

    def test_wifi8_80211bn_uhr_readiness_status(self):
        """Verifies IEEE 802.11bn (Wi-Fi 8 - Ultra High Reliability / UHR) readiness evaluation."""
        from netopt.diagnostics import check_wifi8_80211bn_uhr_readiness_status
        res = check_wifi8_80211bn_uhr_readiness_status()
        self.assertIn("802.11bn", res["standard"])
        self.assertIn("Wi-Fi 8", res["standard"])
        self.assertIn("Ultra High Reliability", res["standard"])
        self.assertTrue(res["multi_ap_coordinated_beamforming_ready"])
        self.assertTrue(res["multi_ap_coordinated_spatial_reuse_ready"])
        self.assertEqual(res["deterministic_latency_p95_reduction_pct"], 25.0)
        self.assertEqual(res["edge_throughput_improvement_pct"], 25.0)
        self.assertEqual(res["seamless_roaming_mpdu_loss_reduction_pct"], 25.0)
        self.assertTrue(res["dynamic_subchannel_operation_supported"])
        self.assertTrue(res["non_primary_channel_access_supported"])
        self.assertTrue(res["rf_in_device_coexistence_active"])
        self.assertIn("Wi-Fi 8", res["summary"])

    @patch("netopt.adapters.SystemResourceAdapter.get_power_telemetry")
    def test_hardware_thermal_subagent_uses_mature_power_telemetry(self, mock_power):
        """Verifies hardware thermal subagent leverages mature psutil power adapter."""
        from netopt.ecosystem_subagents import EcosystemOrchestrator
        mock_power.return_value = {
            "available": True,
            "has_battery": True,
            "power_plugged": False,
            "battery_percent": 82.0,
            "seconds_left": 5400,
            "is_power_saving": False
        }
        orch = EcosystemOrchestrator()
        res = orch.run_hardware_thermal_subagent()
        self.assertEqual(res["subagent"], "hardware_thermal")
        self.assertTrue(res["has_battery"])
        self.assertFalse(res["power_plugged"])
        self.assertEqual(res["battery_percent"], 82)
        self.assertIn("82%", res["summary"])
        self.assertIn("Modo batería", res["summary"])

    def test_rfc9543_ietf_network_slicing_and_nrp_status(self):
        """Verifies RFC 9543 IETF Network Slicing and Network Resource Partitions (NRP) evaluation."""
        from netopt.diagnostics import check_rfc9543_ietf_network_slicing_and_nrp_status
        res = check_rfc9543_ietf_network_slicing_and_nrp_status()
        self.assertIn("RFC 9543", res["standard"])
        self.assertTrue(res["service_demarcation_points_defined"])
        self.assertTrue(res["network_resource_partitions_active"])
        self.assertTrue(res["dscp_to_nrp_traffic_steering"])
        self.assertTrue(res["slo_sle_deterministic_guarantees"])
        self.assertTrue(res["buffer_and_queue_isolation_supported"])
        self.assertTrue(res["sr_mpls_srv6_transport_interworking_ready"])
        self.assertTrue(res["multi_queue_qos_hardware_aligned"])
        self.assertIn("RFC 9543", res["summary"])

    def test_cross_platform_zero_trust_arp_pinning_methods(self):
        """Verifies cross-platform Zero-Trust ARP pinning and unpinning in WindowsHAL, LinuxHAL, and DarwinHAL."""
        from netopt.hal import WindowsHAL, LinuxHAL, DarwinHAL
        from netopt.models import ActionType

        # Windows
        win_hal = WindowsHAL(dry_run=True)
        log_win_pin = win_hal.pin_gateway_mac("Ethernet", "192.168.1.1", "AA:BB:CC:DD:EE:FF", execute=False)
        self.assertEqual(log_win_pin.action_type, ActionType.OPTIMIZATION)
        self.assertIn('netsh interface ipv4 add neighbors "Ethernet" 192.168.1.1 AA-BB-CC-DD-EE-FF', log_win_pin.command)
        log_win_unpin = win_hal.unpin_gateway_mac("Ethernet", "192.168.1.1", execute=False)
        self.assertEqual(log_win_unpin.action_type, ActionType.REPAIR)
        self.assertIn('netsh interface ipv4 delete neighbors "Ethernet" 192.168.1.1', log_win_unpin.command)

        # Linux
        linux_hal = LinuxHAL(dry_run=True)
        log_linux_pin = linux_hal.pin_gateway_mac("eth0", "192.168.1.1", "AA-BB-CC-DD-EE-FF", execute=False)
        self.assertEqual(log_linux_pin.action_type, ActionType.OPTIMIZATION)
        self.assertIn("ip neigh replace 192.168.1.1 lladdr aa:bb:cc:dd:ee:ff nud permanent dev eth0", log_linux_pin.command)
        log_linux_unpin = linux_hal.unpin_gateway_mac("eth0", "192.168.1.1", execute=False)
        self.assertEqual(log_linux_unpin.action_type, ActionType.REPAIR)
        self.assertIn("ip neigh del 192.168.1.1 dev eth0", log_linux_unpin.command)

        # Darwin (macOS)
        darwin_hal = DarwinHAL(dry_run=True)
        log_darwin_pin = darwin_hal.pin_gateway_mac("en0", "192.168.1.1", "AA-BB-CC-DD-EE-FF", execute=False)
        self.assertEqual(log_darwin_pin.action_type, ActionType.OPTIMIZATION)
        self.assertIn("arp -s 192.168.1.1 aa:bb:cc:dd:ee:ff", log_darwin_pin.command)
        log_darwin_unpin = darwin_hal.unpin_gateway_mac("en0", "192.168.1.1", execute=False)
        self.assertEqual(log_darwin_unpin.action_type, ActionType.REPAIR)
        self.assertIn("arp -d 192.168.1.1", log_darwin_unpin.command)

    def test_pqc_hybrid_tls_and_oversize_hello_readiness_status(self):
        """Verifies Post-Quantum Cryptography (PQC / FIPS 203 ML-KEM) TLS 1.3 readiness evaluation."""
        from netopt.diagnostics import check_pqc_hybrid_tls_and_oversize_hello_readiness_status
        res = check_pqc_hybrid_tls_and_oversize_hello_readiness_status()
        self.assertIn("ML-KEM", res["standard"])
        self.assertTrue(res["pqc_hybrid_key_exchange_supported"])
        self.assertEqual(res["active_pqc_algorithm"], "X25519MLKEM768")
        self.assertGreater(res["pqc_client_hello_size_bytes"], 1500)
        self.assertTrue(res["multisegment_client_hello_fragility_mitigated"])
        self.assertTrue(res["middlebox_tls_hello_drop_mitigation"])
        self.assertTrue(res["harvest_now_decrypt_later_shielded"])
        self.assertTrue(res["fips203_ml_kem_standardized"])
        self.assertTrue(res["plpmtud_blackhole_resilience_active"])
        self.assertIn("FIPS 203", res["summary"])





if __name__ == "__main__":
    unittest.main()

