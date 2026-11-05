"""
Non-destructive, cross-platform network diagnostics and telemetry engine.
Measures latency, RFC 3550 jitter, packet loss, DNS resolution times, PMTU, and bufferbloat.
"""

from __future__ import annotations
import os
import json
import socket
import time
import struct
import platform
import subprocess
import concurrent.futures
from typing import List, Dict, Tuple, Optional, Any
from .models import (
    PlatformType,
    HealthState,
    LatencyMetrics,
    DnsBenchmarkEntry,
    DiagnosticsReport
)
from .hal import detect_platform, get_hal


POPULAR_PUBLIC_DNS = [
    {"name": "Cloudflare", "ip": "1.1.1.1"},
    {"name": "Cloudflare Secondary", "ip": "1.0.0.1"},
    {"name": "Google Primary", "ip": "8.8.8.8"},
    {"name": "Google Secondary", "ip": "8.8.4.4"},
    {"name": "Quad9 (Malware Blocking)", "ip": "9.9.9.9"},
    {"name": "OpenDNS Home", "ip": "208.67.222.222"}
]

BENCHMARK_DOMAINS = [
    "cloudflare.com",
    "google.com",
    "wikipedia.org",
    "github.com"
]


def tcp_ping(host: str, port: int = 80, timeout: float = 1.5) -> Optional[float]:
    """Measures TCP handshake RTT in milliseconds. Reliable across all OS without root/admin."""
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        sock.close()
        return (time.perf_counter() - start) * 1000.0
    except (socket.timeout, OSError):
        return None
    finally:
        try:
            sock.close()
        except Exception:
            pass


def measure_target_metrics(target: str, count: int = 5, port: int = 80) -> LatencyMetrics:
    """Computes Min/Avg/Max RTT, Loss %, and RFC 3550 Jitter."""
    samples: List[float] = []
    sent = count

    for _ in range(count):
        lat = tcp_ping(target, port=port, timeout=1.5)
        if lat is not None:
            samples.append(lat)
        time.sleep(0.05)

    recv = len(samples)
    loss = ((sent - recv) / sent) * 100.0

    if not samples:
        return LatencyMetrics(
            target=target,
            packets_sent=sent,
            packets_received=0,
            packet_loss_percent=100.0,
            min_ms=0.0,
            avg_ms=0.0,
            max_ms=0.0,
            jitter_ms=0.0
        )

    min_ms = min(samples)
    max_ms = max(samples)
    avg_ms = sum(samples) / len(samples)

    # RFC 3550 Jitter: J = J + (|D(i-1, i)| - J) / 16
    jitter = 0.0
    for i in range(1, len(samples)):
        diff = abs(samples[i] - samples[i - 1])
        jitter += (diff - jitter) / 16.0

    return LatencyMetrics(
        target=target,
        packets_sent=sent,
        packets_received=recv,
        packet_loss_percent=loss,
        min_ms=round(min_ms, 2),
        avg_ms=round(avg_ms, 2),
        max_ms=round(max_ms, 2),
        jitter_ms=round(jitter, 2)
    )


def build_raw_dns_query(domain: str, qtype: int = 1) -> bytes:
    """Builds a minimal standard RFC 1035 UDP DNS query packet."""
    import random
    qid = random.randint(0, 65535)
    # Flags: standard query, recursion desired (0x0100)
    header = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    qname = b""
    for part in domain.split("."):
        bpart = part.encode("ascii")
        qname += bytes([len(bpart)]) + bpart
    qname += b"\x00"
    question = qname + struct.pack(">HH", qtype, 1)
    return header + question


def query_dns_resolver_latency(resolver_ip: str, domain: str = "google.com", timeout: float = 1.2) -> Optional[float]:
    """Measures direct UDP DNS round-trip latency in milliseconds."""
    query = build_raw_dns_query(domain)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    start = time.perf_counter()
    try:
        sock.sendto(query, (resolver_ip, 53))
        data, _ = sock.recvfrom(512)
        elapsed = (time.perf_counter() - start) * 1000.0
        if len(data) >= 12:
            return elapsed
        return None
    except Exception:
        return None
    finally:
        sock.close()


def benchmark_all_resolvers() -> List[DnsBenchmarkEntry]:
    """Benchmarks major DNS resolvers concurrently."""
    results: List[DnsBenchmarkEntry] = []

    def probe_resolver(entry: dict) -> DnsBenchmarkEntry:
        ip = entry["ip"]
        name = entry["name"]
        samples = []
        for d in BENCHMARK_DOMAINS:
            lat = query_dns_resolver_latency(ip, domain=d)
            if lat is not None:
                samples.append(lat)
            time.sleep(0.02)
        success_rate = (len(samples) / len(BENCHMARK_DOMAINS)) * 100.0
        avg_lat = sum(samples) / len(samples) if samples else 999.0
        return DnsBenchmarkEntry(
            provider=name,
            ip=ip,
            avg_latency_ms=round(avg_lat, 2),
            success_rate_percent=round(success_rate, 1)
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(probe_resolver, r) for r in POPULAR_PUBLIC_DNS]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Sort best latency first
    results.sort(key=lambda x: (100 - x.success_rate_percent, x.avg_latency_ms))
    return results


def check_bufferbloat(target: str = "1.1.1.1") -> Tuple[str, float, float]:
    """
    Evaluates bufferbloat grade by comparing idle latency vs latency during concurrent multi-socket burst load.
    Grades: A+ (<5ms), A (<15ms), B (<30ms), C (<60ms), D (<120ms), F (>=120ms or loss).
    """
    idle_metrics = measure_target_metrics(target, count=4, port=80)
    idle_rtt = idle_metrics.avg_ms

    if idle_metrics.packet_loss_percent >= 50.0:
        return ("F", idle_rtt, 999.0)

    def _burst_worker():
        for d in BENCHMARK_DOMAINS:
            query_dns_resolver_latency(target, domain=d, timeout=0.6)
        tcp_ping(target, port=443, timeout=0.8)

    burst_samples = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        load_futures = [pool.submit(_burst_worker) for _ in range(4)]
        for _ in range(3):
            lat = tcp_ping(target, port=80, timeout=1.0)
            if lat is not None:
                burst_samples.append(lat)
        concurrent.futures.wait(load_futures, timeout=1.5)

    active_rtt = sum(burst_samples) / len(burst_samples) if burst_samples else idle_rtt
    delta = max(0.0, active_rtt - idle_rtt)

    if delta < 5.0:
        grade = "A+"
    elif delta < 15.0:
        grade = "A"
    elif delta < 30.0:
        grade = "B"
    elif delta < 60.0:
        grade = "C"
    elif delta < 120.0:
        grade = "D"
    else:
        grade = "F"

    return (grade, round(idle_rtt, 2), round(delta, 2))


def run_full_diagnostics() -> DiagnosticsReport:
    """Executes complete diagnostic sweep and returns a structured health report."""
    hal = get_hal(dry_run=True)
    plat = detect_platform()
    gateway = hal.get_default_gateway()

    # Cloudflare / Google reachability
    cf_metrics = measure_target_metrics("1.1.1.1", count=4, port=53)
    google_metrics = measure_target_metrics("8.8.8.8", count=4, port=53)
    internet_reachable = (cf_metrics.packet_loss_percent < 100.0 or google_metrics.packet_loss_percent < 100.0)

    # Reachability checks
    gateway_reachable = False
    if gateway and gateway not in ["0.0.0.0", "::"]:
        gw_lat = (
            tcp_ping(gateway, port=80, timeout=0.5)
            or tcp_ping(gateway, port=443, timeout=0.5)
            or tcp_ping(gateway, port=53, timeout=0.5)
        )
        if gw_lat is not None:
            gateway_reachable = True
        elif internet_reachable:
            # If public internet is reaching external endpoints, the gateway hop is forwarding traffic
            gateway_reachable = True

    # DNS benchmark
    dns_bench = benchmark_all_resolvers()
    dns_resolving = any(b.success_rate_percent > 0 for b in dns_bench)

    # Bufferbloat
    bloat_grade, _, _ = check_bufferbloat("1.1.1.1")

    # Health assessment & Anomaly detection
    anomalies: List[str] = []
    if not internet_reachable:
        anomalies.append("CRITICAL: No public internet access detected (1.1.1.1 and 8.8.8.8 unreachable).")
    if not dns_resolving:
        anomalies.append("CRITICAL: DNS resolution completely failing across all standard resolvers.")
    if cf_metrics.packet_loss_percent > 10.0:
        anomalies.append(f"HIGH: Elevated packet loss detected ({cf_metrics.packet_loss_percent}% to Cloudflare).")
    if cf_metrics.jitter_ms > 25.0:
        anomalies.append(f"MEDIUM: High jitter detected ({cf_metrics.jitter_ms}ms).")
    if bloat_grade in ["D", "F"]:
        anomalies.append(f"WARNING: Poor bufferbloat grade ({bloat_grade}), TCP pacing or CoDel needed.")

    health = HealthState.HEALTHY
    if not internet_reachable or not dns_resolving:
        health = HealthState.DOWN
    elif anomalies:
        health = HealthState.DEGRADED

    return DiagnosticsReport(
        timestamp=time.time(),
        platform=plat,
        overall_health=health,
        default_gateway=gateway,
        gateway_reachable=gateway_reachable,
        internet_reachable=internet_reachable,
        dns_resolving=dns_resolving,
        dns_benchmarks=dns_bench,
        latency_metrics={"1.1.1.1": cf_metrics, "8.8.8.8": google_metrics},
        detected_pmtu=1500,
        bufferbloat_grade=bloat_grade,
        active_interface=None,
        anomalies=anomalies
    )


def inspect_active_sockets() -> Dict[str, Any]:
    """Audits active TCP/UDP sockets, state distribution, top remote IPs, and top bandwidth/socket processes."""
    plat = detect_platform()
    cmd = ["netstat", "-ano"] if plat == PlatformType.WINDOWS else ["netstat", "-an"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=8)
        raw = res.stdout or ""
    except Exception as e:
        return {"error": str(e), "states": {}, "total_tcp": 0, "top_processes": []}

    states: Dict[str, int] = {}
    remote_ips: Dict[str, int] = {}
    pid_counts: Dict[str, int] = {}
    total_tcp = 0
    total_udp = 0

    for line in raw.splitlines():
        parts = line.split()
        if not parts:
            continue
        proto = parts[0].upper()
        if proto.startswith("TCP") and len(parts) >= 4:
            total_tcp += 1
            state = parts[3].upper()
            states[state] = states.get(state, 0) + 1
            remote = parts[2]
            if ":" in remote:
                rip = remote.rsplit(":", 1)[0].strip("[]")
                if rip not in ("0.0.0.0", "127.0.0.1", "::", "::1", "*"):
                    remote_ips[rip] = remote_ips.get(rip, 0) + 1
            if len(parts) >= 5 and parts[4].isdigit() and parts[4] != "0":
                pid_counts[parts[4]] = pid_counts.get(parts[4], 0) + 1
        elif proto.startswith("UDP"):
            total_udp += 1
            if len(parts) >= 4 and parts[-1].isdigit() and parts[-1] != "0":
                pid_counts[parts[-1]] = pid_counts.get(parts[-1], 0) + 1

    # Map top PIDs to process executable names on Windows
    pid_names: Dict[str, str] = {}
    if plat == PlatformType.WINDOWS and pid_counts:
        try:
            tres = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace", timeout=5)
            if tres.returncode == 0 and tres.stdout:
                for tline in tres.stdout.splitlines():
                    cols = [c.strip('"') for c in tline.split('","')]
                    if len(cols) >= 2:
                        pid_names[cols[1]] = cols[0]
        except Exception:
            pass

    app_sockets: Dict[str, int] = {}
    for pid, cnt in pid_counts.items():
        pname = pid_names.get(pid, f"PID-{pid}")
        app_sockets[pname] = app_sockets.get(pname, 0) + cnt

    top_processes = [
        {"process": app, "sockets": cnt}
        for app, cnt in sorted(app_sockets.items(), key=lambda x: x[1], reverse=True)[:6]
    ]
    top_remotes = sorted(remote_ips.items(), key=lambda x: x[1], reverse=True)[:5]
    anomalies = []
    if states.get("TIME_WAIT", 0) > 250:
        anomalies.append(f"Elevated TIME_WAIT sockets ({states['TIME_WAIT']})")
    if states.get("CLOSE_WAIT", 0) > 30:
        anomalies.append(f"Socket leak indicator: {states['CLOSE_WAIT']} CLOSE_WAIT connections")
    if states.get("SYN_SENT", 0) > 15:
        anomalies.append(f"Possible outbound connection bottleneck ({states['SYN_SENT']} SYN_SENT)")

    return {
        "platform": plat.value,
        "total_tcp": total_tcp,
        "total_udp": total_udp,
        "states": states,
        "top_processes": top_processes,
        "top_remote_ips": [{"ip": ip, "connections": cnt} for ip, cnt in top_remotes],
        "anomalies": anomalies
    }


def discover_path_mtu(target: str = "1.1.1.1") -> Dict[str, Any]:
    """Fast DF-bit Path MTU discovery (distinguishes real DF fragmentation from ICMP filtering)."""
    plat = detect_platform()

    def _probe_df(payload: int) -> Tuple[bool, bool]:
        if plat == PlatformType.WINDOWS:
            cmd = ["ping", "-n", "1", "-w", "600", "-f", "-l", str(payload), target]
        elif plat == PlatformType.LINUX:
            cmd = ["ping", "-c", "1", "-W", "1", "-M", "do", "-s", str(payload), target]
        else:
            cmd = ["ping", "-c", "1", "-W", "600", "-D", "-s", str(payload), target]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=2)
            out_lower = ((res.stdout or "") + (res.stderr or "")).lower()
            explicit_frag = any(k in out_lower for k in [
                "fragment", "frag", "demasiado grande", "message too long", "df set"
            ])
            ok = (res.returncode == 0 and not explicit_frag and "100%" not in out_lower)
            return ok, explicit_frag
        except Exception:
            return False, False

    # Fast path: check 1472B (1500 MTU) first
    ok_1500, frag_1500 = _probe_df(1472)
    if ok_1500 or not frag_1500:
        return {
            "target": target,
            "max_unfragmented_payload": 1472,
            "optimal_mtu": 1500,
            "needs_tuning": False
        }

    low = 1200
    high = 1471
    best_payload = 1472

    while low <= high:
        mid = (low + high) // 2
        ok, explicit_frag = _probe_df(mid)
        if ok or not explicit_frag:
            best_payload = mid
            low = mid + 1
        else:
            high = mid - 1

    optimal_mtu = best_payload + 28
    return {
        "target": target,
        "max_unfragmented_payload": best_payload,
        "optimal_mtu": optimal_mtu,
        "needs_tuning": optimal_mtu < 1500
    }


def audit_arp_lan() -> Dict[str, Any]:
    """Scans local ARP neighbor cache and checks for duplicate MACs (ARP spoofing/conflict)."""
    try:
        res = subprocess.run(["arp", "-a"], capture_output=True, text=True, errors="replace", timeout=5)
        raw = res.stdout or ""
    except Exception as e:
        return {"error": str(e), "neighbors": [], "anomalies": []}

    neighbors = []
    mac_to_ips: Dict[str, List[str]] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 3 and "." in parts[0] and ("-" in parts[1] or ":" in parts[1]):
            ip = parts[0]
            mac = parts[1].lower().replace("-", ":")
            ntype = parts[2]
            if mac in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00") or ip.startswith("224.") or ip.startswith("239.") or ip.endswith(".255"):
                continue
            neighbors.append({"ip": ip, "mac": mac, "type": ntype})
            mac_to_ips.setdefault(mac, []).append(ip)

    anomalies = []
    for mac, ips in mac_to_ips.items():
        if len(ips) > 1:
            anomalies.append(f"Duplicate MAC {mac} shared by multiple IPs: {', '.join(ips)}")

    return {
        "neighbor_count": len(neighbors),
        "neighbors": neighbors[:15],
        "anomalies": anomalies
    }


def inspect_wifi_and_nic() -> Dict[str, Any]:
    """Audits Layer-1 Wi-Fi radio quality (SSID, Signal %, Band, Channel, Link Rate) and active NIC adapters."""
    plat = detect_platform()
    hal = get_hal(dry_run=True)
    interfaces = [
        {"name": i.name, "mac": i.mac_address, "up": i.is_up}
        for i in hal.get_interfaces() if i.is_up
    ]
    wifi_info: Dict[str, Any] = {
        "connected": False,
        "ssid": None,
        "signal_percent": None,
        "radio_type": None,
        "band": None,
        "channel": None,
        "rx_mbps": None,
        "tx_mbps": None
    }
    anomalies: List[str] = []

    if plat == PlatformType.WINDOWS:
        try:
            res = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, errors="replace", timeout=5)
            if res.returncode == 0 and res.stdout:
                import re
                for line in res.stdout.splitlines():
                    if ":" not in line:
                        continue
                    k, v = [x.strip() for x in line.split(":", 1)]
                    kl = k.lower()
                    if "ssid" in kl and "bssid" not in kl and not wifi_info["ssid"]:
                        wifi_info["ssid"] = v
                        wifi_info["connected"] = bool(v)
                    elif "%" in v:
                        m = re.search(r"(\d+)\s*%", v)
                        if m:
                            wifi_info["signal_percent"] = int(m.group(1))
                    elif any(w in kl for w in ["radio", "tipo de radio"]):
                        wifi_info["radio_type"] = v
                    elif any(w in kl for w in ["band", "banda"]):
                        wifi_info["band"] = v
                    elif any(w in kl for w in ["channel", "canal"]):
                        m = re.search(r"(\d+)", v)
                        if m:
                            ch = int(m.group(1))
                            wifi_info["channel"] = ch
                            if not wifi_info["band"]:
                                wifi_info["band"] = "5 GHz / 6 GHz" if ch > 14 else "2.4 GHz"
                    elif any(w in kl for w in ["receive rate", "velocidad de recepci"]):
                        wifi_info["rx_mbps"] = v
                    elif any(w in kl for w in ["transmit rate", "velocidad de transmisi"]):
                        wifi_info["tx_mbps"] = v
        except Exception:
            pass

    sig = wifi_info.get("signal_percent")
    if sig is not None and sig < 60:
        anomalies.append(f"Weak Wi-Fi signal ({sig}%) — risk of packet retransmissions and jitter spikes")
    if wifi_info.get("band") and "2.4" in str(wifi_info.get("band")):
        anomalies.append("Connected on 2.4 GHz band — switch to 5 GHz for lower latency and higher throughput")

    rad = str(wifi_info.get("radio_type") or "").lower()
    if any(w in rad for w in ["802.11be", "wifi 7", "wi-fi 7"]):
        wifi_info["is_wifi_7"] = True
        wifi_info["mlo_capable"] = True

    return {
        "platform": plat.value,
        "wifi": wifi_info,
        "active_nics": interfaces,
        "anomalies": anomalies
    }


def measure_bandwidth_speed() -> Dict[str, Any]:
    """
    Measures real live Download (Mbps), Upload (Mbps), and Ping/Jitter
    against Cloudflare's global edge (__down / __up) using stdlib urllib.
    """
    import urllib.request
    lat = measure_target_metrics("1.1.1.1", count=2)
    dl_mbps = 0.0
    ul_mbps = 0.0
    dl_duration_s = 0.0
    ul_duration_s = 0.0

    # 1. Download test (5 MB payload from Cloudflare Speed edge)
    try:
        t0 = time.perf_counter()
        req_dl = urllib.request.Request(
            "https://speed.cloudflare.com/__down?bytes=5000000",
            headers={"User-Agent": "OmniNetPro/2.0"}
        )
        with urllib.request.urlopen(req_dl, timeout=10) as resp:
            data = resp.read()
        dl_duration_s = round(max(time.perf_counter() - t0, 0.001), 2)
        dl_mbps = round((len(data) * 8) / (dl_duration_s * 1_000_000), 2)
    except Exception:
        pass

    # 2. Upload test (1 MB payload to Cloudflare Speed edge)
    try:
        payload = b"0" * 1_000_000
        t1 = time.perf_counter()
        req_ul = urllib.request.Request(
            "https://speed.cloudflare.com/__up",
            data=payload,
            headers={"User-Agent": "OmniNetPro/2.0", "Content-Type": "application/octet-stream"},
            method="POST"
        )
        with urllib.request.urlopen(req_ul, timeout=10) as resp:
            resp.read()
        ul_duration_s = round(max(time.perf_counter() - t1, 0.001), 2)
        ul_mbps = round((len(payload) * 8) / (ul_duration_s * 1_000_000), 2)
    except Exception:
        pass

    return {
        "server": "Cloudflare Anycast Edge (speed.cloudflare.com)",
        "download_mbps": dl_mbps,
        "upload_mbps": ul_mbps,
        "ping_ms": lat.avg_ms,
        "jitter_ms": lat.jitter_ms,
        "packet_loss_pct": lat.packet_loss_percent,
        "download_time_sec": dl_duration_s,
        "upload_time_sec": ul_duration_s
    }


def check_doh_status() -> Dict[str, Any]:
    """Inspects if DNS-over-HTTPS (DoH) / DNS-over-TLS (DoT) is enabled."""
    plat = detect_platform()
    doh_configured = False
    templates = []
    if plat == PlatformType.WINDOWS:
        try:
            res = subprocess.run(["netsh", "dns", "show", "encryption"], capture_output=True, text=True, errors="replace", timeout=5)
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    if "https://" in line:
                        templates.append(line.split(":", 1)[1].strip() if ":" in line else line.strip())
                        doh_configured = True
        except Exception:
            pass
    elif plat == PlatformType.LINUX:
        try:
            res = subprocess.run(["resolvectl", "status"], capture_output=True, text=True, errors="replace", timeout=5)
            if res.returncode == 0 and "DNSOverTLS=yes" in res.stdout:
                doh_configured = True
        except Exception:
            pass
    return {
        "platform": plat.value,
        "doh_enabled": doh_configured,
        "templates": templates[:4],
        "is_encrypted": doh_configured,
        "privacy_status": "ALTA (Cifrado DoH activo contra espionaje)" if doh_configured else "ESTÁNDAR (Consultas en texto plano)"
    }


def check_l4s_ecn_status() -> Dict[str, Any]:
    """Inspects if Explicit Congestion Notification (ECN) and low-latency transport signaling are enabled."""
    plat = detect_platform()
    ecn_enabled = False
    congestion_provider = "default"
    if plat == PlatformType.WINDOWS:
        try:
            res = subprocess.run(["netsh", "int", "tcp", "show", "global"], capture_output=True, text=True, errors="replace", timeout=5)
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    ll = line.lower()
                    if "ecn" in ll and "enabled" in ll:
                        ecn_enabled = True
                    elif "congesti" in ll and ":" in line:
                        congestion_provider = line.split(":", 1)[1].strip()
        except Exception:
            pass
    elif plat == PlatformType.LINUX:
        try:
            res = subprocess.run(["sysctl", "-n", "net.ipv4.tcp_ecn"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip() in ("1", "2"):
                ecn_enabled = True
        except Exception:
            pass
    return {
        "platform": plat.value,
        "ecn_enabled": ecn_enabled,
        "congestion_provider": congestion_provider,
        "l4s_ready": ecn_enabled,
        "latency_mode": "Ultra-baja latencia (L4S / ECN activo)" if ecn_enabled else "Estándar (Posible acumulación en colas de router)"
    }


def audit_lan_radar_devices() -> Dict[str, Any]:
    """
    Performs comprehensive LAN Radar scan identifying Gateway, Host PC, and all connected devices,
    catalogs new vs known devices in ~/.netopt_state/known_devices.json, and flags rogue intruders or ARP spoofing.
    """
    base_arp = audit_arp_lan()
    raw_neighbors = base_arp.get("neighbors", [])
    hal = get_hal(dry_run=True)
    gateway_ip = hal.get_default_gateway() or "192.168.1.1"

    local_ips = set()
    local_macs = set()
    for iface in hal.get_interfaces():
        if iface.is_up:
            for ip in iface.ipv4_addresses:
                local_ips.add(ip)
            if iface.mac_address:
                local_macs.add(iface.mac_address.lower().replace("-", ":"))

    known_file = os.path.expanduser("~/.netopt_state/known_devices.json")
    os.makedirs(os.path.dirname(known_file), exist_ok=True)
    known_macs = set()
    if os.path.exists(known_file):
        try:
            with open(known_file, "r", encoding="utf-8") as f:
                known_macs = set(json.load(f))
        except Exception:
            known_macs = set()

    # Zero-Trust Gateway MAC baseline and impersonation check
    gw_mac_file = os.path.expanduser("~/.netopt_state/trusted_gateway.json")
    trusted_gw_mac = None
    if os.path.exists(gw_mac_file):
        try:
            with open(gw_mac_file, "r", encoding="utf-8") as f:
                trusted_gw_mac = json.load(f).get("mac")
        except Exception:
            trusted_gw_mac = None

    current_gw_mac = None
    for n in raw_neighbors:
        if n.get("ip") == gateway_ip:
            current_gw_mac = n.get("mac", "").lower()
            break

    gateway_impersonation = False
    anomalies = list(base_arp.get("anomalies", []))
    if current_gw_mac:
        if trusted_gw_mac and trusted_gw_mac != current_gw_mac:
            gateway_impersonation = True
            anomalies.append(
                f"ALERTA CRÍTICA: Posible suplantación de gateway (ARP Spoofing/MitM). MAC del router cambió de {trusted_gw_mac} a {current_gw_mac}."
            )
        elif not trusted_gw_mac:
            try:
                with open(gw_mac_file, "w", encoding="utf-8") as f:
                    json.dump({"gateway_ip": gateway_ip, "mac": current_gw_mac, "locked_at": time.time()}, f, indent=2)
            except Exception:
                pass

    devices = []
    new_devices = []

    for n in raw_neighbors:
        ip = n.get("ip", "")
        mac = n.get("mac", "").lower()
        is_gw = (ip == gateway_ip)
        is_me = (ip in local_ips or mac in local_macs)

        role = "Router / Puerta de Enlace" if is_gw else ("Este Computador" if is_me else "Dispositivo en Red")
        vendor = "Desconocido / Dispositivo Wi-Fi"
        if is_gw:
            vendor = "Router Principal (ISP)"
        elif is_me:
            vendor = "Equipo Local"
        elif mac.startswith(("f8:ed:fc", "74:24:9f", "a4:e8:8d", "ac:bc:32")):
            vendor = "Dispositivo Móvil / Smart TV"
        elif mac.startswith(("b8:27:eb", "dc:a6:32", "e4:5f:01")):
            vendor = "Microcontrolador / IoT"

        is_new = (mac not in known_macs and not is_gw and not is_me)
        if is_new:
            new_devices.append({"ip": ip, "mac": mac, "role": role, "vendor": vendor})
        known_macs.add(mac)

        devices.append({
            "ip": ip,
            "mac": mac,
            "role": role,
            "vendor": vendor,
            "is_gateway": is_gw,
            "is_local_host": is_me,
            "is_new": is_new
        })

    try:
        with open(known_file, "w", encoding="utf-8") as f:
            json.dump(list(known_macs), f, indent=2)
    except Exception:
        pass

    return {
        "gateway_ip": gateway_ip,
        "total_devices_detected": len(devices),
        "devices": devices,
        "new_devices_found": new_devices,
        "anomalies": anomalies,
        "gateway_impersonation_detected": gateway_impersonation,
        "radar_status": "SEGURO (Sin intrusos ni conflictos ARP)" if not new_devices and not anomalies else "ALERTA (Nuevos dispositivos o anomalías detectadas)"
    }





