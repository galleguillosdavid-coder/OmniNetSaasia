"""
OmniNet Telemetry & Global Metrics Collector Engine (`netopt/telemetry.py`).
Responsible for:
  1. Real in-situ empirical testing on the host device (Wi-Fi, sockets, ARP, PMTU, DNS).
  2. Worldwide anonymized device performance metrics collection (latency, jitter, bufferbloat, subagents).
  3. AI conversation & feedback collection to drive continuous prompt and heuristics self-improvement.
"""

from __future__ import annotations
import os
import sys
import json
import time
import hashlib
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from .hal import detect_platform, get_hal
from .diagnostics import (
    measure_target_metrics,
    query_dns_resolver_latency,
    check_bufferbloat,
    inspect_wifi_and_nic,
    inspect_active_sockets,
    discover_path_mtu,
    audit_arp_lan
)
from .ecosystem_subagents import get_ecosystem_orchestrator


DEFAULT_CLOUD_COLLECTOR_URL = os.environ.get("OMNINET_CLOUD_URL", "http://127.0.0.1:9988")
LOCAL_METRICS_LOG = os.path.expanduser("~/.netopt_state/local_empirical_metrics.json")


def run_real_device_empirical_probes(target: str = "1.1.1.1") -> Dict[str, Any]:
    """
    Executes real empirical network, hardware, and OS probes directly on the physical host machine.
    Guarantees that telemetry is grounded in real hardware signals rather than mocks or simulations.
    """
    plat = detect_platform()
    hal = get_hal(dry_run=True)

    # 1. Real latency, jitter, and packet loss
    metrics = measure_target_metrics(target, count=3)

    # 2. Real DNS probe latency
    dns_lat = query_dns_resolver_latency(target, domain="cloudflare.com", timeout=1.0)

    # 3. Real Wi-Fi and interface state
    wifi_data = inspect_wifi_and_nic()

    # 4. Real active sockets
    sockets_data = inspect_active_sockets()

    # 5. Real gateway and ARP status
    gateway = hal.get_default_gateway()
    arp_data = audit_arp_lan()

    # 6. Real bufferbloat evaluation
    bloat_grade, idle_ms, delta_ms = check_bufferbloat(target)

    # 7. 10 Ecosystem Subagents Live Status
    orch = get_ecosystem_orchestrator()
    subagents_summary = {sa["id"]: sa.get("status", "Al Día") for sa in orch.get_all_subagents_status()}

    device_raw = f"{plat.value}:{gateway}:{wifi_data.get('wifi', {}).get('ssid', 'LAN')}"
    anon_device_id = hashlib.sha256(device_raw.encode("utf-8")).hexdigest()[:16]

    report = {
        "timestamp": time.time(),
        "device_id": anon_device_id,
        "platform": plat.value,
        "gateway": gateway,
        "empirical_verification": True,
        "ping_avg_ms": metrics.avg_ms,
        "jitter_ms": metrics.jitter_ms,
        "packet_loss_pct": metrics.packet_loss_percent,
        "dns_resolution_ms": dns_lat or 999.0,
        "bufferbloat_grade": bloat_grade,
        "bufferbloat_delta_ms": delta_ms,
        "total_tcp_sockets": sockets_data.get("total_tcp", 0),
        "total_udp_sockets": sockets_data.get("total_udp", 0),
        "is_wifi": bool(wifi_data.get("wifi", {}).get("connected", False)),
        "wifi_signal_pct": wifi_data.get("wifi", {}).get("signal_percent"),
        "wifi_band": wifi_data.get("wifi", {}).get("band"),
        "is_wifi7": bool(wifi_data.get("wifi", {}).get("is_wifi_7", False)),
        "arp_devices_count": len(arp_data.get("neighbors", [])),
        "arp_anomalies": arp_data.get("anomalies", []),
        "subagents_status": subagents_summary,
        "app_version": "2.9.6"
    }

    # Persist locally for device historical trending
    _persist_local_empirical_metrics(report)
    return report


def _persist_local_empirical_metrics(entry: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(LOCAL_METRICS_LOG), exist_ok=True)
        items = []
        if os.path.exists(LOCAL_METRICS_LOG):
            try:
                with open(LOCAL_METRICS_LOG, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    if not isinstance(items, list):
                        items = []
            except Exception:
                items = []
        items.append(entry)
        with open(LOCAL_METRICS_LOG, "w", encoding="utf-8") as f:
            json.dump(items[-200:], f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def dispatch_global_device_telemetry(
    empirical_report: Optional[Dict[str, Any]] = None,
    collector_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Dispatches anonymized real-world device performance metrics to the global OmniNet cloud collector.
    Feeds global telemetry to improve network optimization heuristics worldwide.
    """
    report = empirical_report or run_real_device_empirical_probes()
    base_url = (collector_url or DEFAULT_CLOUD_COLLECTOR_URL).rstrip("/")
    endpoint = f"{base_url}/v1/telemetry/report"

    payload = {
        "device_id": report.get("device_id"),
        "platform": report.get("platform"),
        "avg_latency_ms": report.get("ping_avg_ms"),
        "jitter_ms": report.get("jitter_ms"),
        "packet_loss_pct": report.get("packet_loss_pct"),
        "bufferbloat_grade": report.get("bufferbloat_grade"),
        "active_interface": report.get("wifi_band") or "Ethernet",
        "subagents_status": report.get("subagents_status"),
        "is_wifi7": report.get("is_wifi7", False),
        "app_version": report.get("app_version", "2.9.6")
    }

    # Try mature HttpClientAdapter (httpx) first
    try:
        from .adapters import HttpClientAdapter
        if HttpClientAdapter.is_available():
            status, data = HttpClientAdapter.post_json(endpoint, payload, timeout_sec=5.0)
            if status == 200:
                return {
                    "success": True,
                    "dispatched": True,
                    "status": data.get("status"),
                    "device_hash": data.get("device_hash")
                }
            return {
                "success": False,
                "dispatched": False,
                "error": data.get("error", f"HTTP {status}"),
                "payload_cached_locally": True
            }
    except Exception:
        pass

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            return {
                "success": True,
                "dispatched": True,
                "status": resp_data.get("status"),
                "device_hash": resp_data.get("device_hash")
            }
    except Exception as e:
        return {
            "success": False,
            "dispatched": False,
            "error": str(e),
            "payload_cached_locally": True
        }

