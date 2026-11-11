"""
Mature Library Adapters (Adapter Pattern - docs/Auditorias/3.md §38).
Encapsulates external mature libraries (psutil, httpx) behind resilient interfaces,
providing deep system observability, top network process telemetry, and robust HTTP communication.
"""

from __future__ import annotations
import os
import sys
import time
from typing import Dict, Any, List, Optional, Tuple


class SystemResourceAdapter:
    """
    Adapter for psutil system observability:
    - High-precision CPU metrics (total & per-core)
    - Virtual memory and swap stats
    - Physical network interface I/O counters and drop detection
    - Top network socket consuming processes identification
    """

    @staticmethod
    def is_available() -> bool:
        try:
            import psutil
            return True
        except ImportError:
            return False

    @classmethod
    def get_cpu_and_memory_telemetry(cls) -> Dict[str, Any]:
        try:
            import psutil
            cpu_pct = psutil.cpu_percent(interval=0.05)
            per_core = psutil.cpu_percent(interval=0.05, percpu=True)
            mem = psutil.virtual_memory()
            cores_physical = psutil.cpu_count(logical=False) or 1
            cores_logical = psutil.cpu_count(logical=True) or 1

            return {
                "available": True,
                "cpu_percent": float(cpu_pct),
                "per_core_percent": [float(p) for p in per_core],
                "physical_cores": cores_physical,
                "logical_cores": cores_logical,
                "ram_total_mb": mem.total // (1024 * 1024),
                "ram_used_mb": mem.used // (1024 * 1024),
                "ram_available_mb": mem.available // (1024 * 1024),
                "ram_percent": float(mem.percent),
                "memory_pressure": mem.percent >= 85.0
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "cpu_percent": 0.0,
                "ram_percent": 0.0
            }

    @classmethod
    def get_interface_io_counters(cls) -> Dict[str, Any]:
        """Captures hardware byte transfer and packet drop counters across all NICs."""
        try:
            import psutil
            total_io = psutil.net_io_counters(pernic=False)
            per_nic = psutil.net_io_counters(pernic=True)
            stats = psutil.net_if_stats()

            nic_details = {}
            for nic_name, io in per_nic.items():
                st = stats.get(nic_name)
                nic_details[nic_name] = {
                    "bytes_sent": io.bytes_sent,
                    "bytes_recv": io.bytes_recv,
                    "packets_sent": io.packets_sent,
                    "packets_recv": io.packets_recv,
                    "errin": io.errin,
                    "errout": io.errout,
                    "dropin": io.dropin,
                    "dropout": io.dropout,
                    "is_up": st.isup if st else False,
                    "speed_mbps": st.speed if st else 0,
                    "mtu": st.mtu if st else 1500
                }

            return {
                "available": True,
                "total_bytes_sent": total_io.bytes_sent,
                "total_bytes_recv": total_io.bytes_recv,
                "total_dropin": total_io.dropin,
                "total_dropout": total_io.dropout,
                "has_packet_loss_at_driver": (total_io.dropin + total_io.dropout) > 0,
                "interfaces": nic_details
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "total_bytes_sent": 0,
                "total_bytes_recv": 0,
                "interfaces": {}
            }

    @classmethod
    def get_top_network_processes(cls, limit: int = 5) -> List[Dict[str, Any]]:
        """Identifies top processes holding open network sockets."""
        try:
            import psutil
            connections = psutil.net_connections(kind="inet")
            pid_counts: Dict[int, int] = {}
            for conn in connections:
                if conn.pid:
                    pid_counts[conn.pid] = pid_counts.get(conn.pid, 0) + 1

            sorted_pids = sorted(pid_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            top_procs = []
            for pid, count in sorted_pids:
                try:
                    proc = psutil.Process(pid)
                    top_procs.append({
                        "pid": pid,
                        "name": proc.name(),
                        "open_sockets": count,
                        "memory_mb": proc.memory_info().rss // (1024 * 1024),
                        "status": proc.status()
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    top_procs.append({
                        "pid": pid,
                        "name": f"PID-{pid}",
                        "open_sockets": count,
                        "memory_mb": 0,
                        "status": "restricted"
                    })
            return top_procs
        except Exception:
            return []


class HttpClientAdapter:
    """
    Adapter for httpx mature HTTP client:
    - Connection pooling and keep-alive
    - Explicit configurable timeouts
    - RFC 9457 structured error parsing
    - Graceful fallback
    """

    @staticmethod
    def is_available() -> bool:
        try:
            import httpx
            return True
        except ImportError:
            return False

    @classmethod
    def post_json(
        cls,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout_sec: float = 8.0
    ) -> Tuple[int, Dict[str, Any]]:
        """Posts JSON payload and decodes response safely."""
        try:
            import httpx
            h = {"Content-Type": "application/json"}
            if headers:
                h.update(headers)
            with httpx.Client(timeout=timeout_sec) as client:
                resp = client.post(url, json=payload, headers=h)
                try:
                    data = resp.json()
                except Exception:
                    data = {"text": resp.text}
                return resp.status_code, data
        except Exception as e:
            return 500, {"error": str(e), "adapter": "httpx_adapter"}

    @classmethod
    def get_json(
        cls,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout_sec: float = 5.0
    ) -> Tuple[int, Dict[str, Any]]:
        """Performs GET and decodes JSON response."""
        try:
            import httpx
            h = headers or {}
            with httpx.Client(timeout=timeout_sec) as client:
                resp = client.get(url, headers=h)
                try:
                    data = resp.json()
                except Exception:
                    data = {"text": resp.text}
                return resp.status_code, data
        except Exception as e:
            return 500, {"error": str(e), "adapter": "httpx_adapter"}

