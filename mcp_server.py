"""
Model Context Protocol (MCP) Server for OmniNet.
Exposes 15 network diagnostics, optimization, repair, deep telemetry, and 10-minute
autonomous task scheduling tools over JSON-RPC 2.0 stdio.
"""

from __future__ import annotations
import sys
import json
import os
from typing import Dict, Any, List

from netopt import __version__ as OMNINET_VERSION
from netopt.hal import get_hal
from netopt.diagnostics import (
    run_full_diagnostics,
    benchmark_all_resolvers,
    inspect_active_sockets,
    discover_path_mtu,
    audit_arp_lan,
    check_bufferbloat,
    inspect_wifi_and_nic,
    measure_bandwidth_speed
)
from netopt.optimizer import NetworkOptimizer
from netopt.repair import NetworkRepairEngine
from netopt.rollback import RollbackManager
from netopt.persistence import NetworkDaemon
from netopt.autonomous_scheduler import get_task_scheduler
from netopt.device_maintenance import DeviceMaintenanceEngine
from netopt.llm_gateway import run_fast_traceroute


MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "tools_manifest.json")
if not os.path.exists(MANIFEST_PATH):
    MANIFEST_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools_manifest.json")


def load_tools_schema() -> List[Dict[str, Any]]:
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("tools", [])
    return []


def handle_tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    execute = bool(arguments.get("execute", False))
    hal = get_hal(dry_run=not execute)

    if name == "network_diagnose":
        include_dns = bool(arguments.get("include_dns_benchmarks", True))
        diag = run_full_diagnostics(include_dns_benchmarks=include_dns)
        return {
            "platform": diag.platform.value,
            "overall_health": diag.overall_health.value,
            "active_interface": (
                diag.active_interface
                if isinstance(diag.active_interface, str)
                else (vars(diag.active_interface) if diag.active_interface else None)
            ),
            "default_gateway": diag.default_gateway,
            "gateway_reachable": diag.gateway_reachable,
            "internet_reachable": diag.internet_reachable,
            "dns_resolving": diag.dns_resolving,
            "detected_pmtu": diag.detected_pmtu,
            "bufferbloat_grade": diag.bufferbloat_grade,
            "anomalies": diag.anomalies,
            "latency_metrics": {k: vars(v) for k, v in diag.latency_metrics.items()},
            "dns_benchmarks": [vars(b) for b in diag.dns_benchmarks]
        }

    elif name == "network_benchmark_dns":
        domains = arguments.get("domains")
        bench = benchmark_all_resolvers(domains=domains if isinstance(domains, list) else None)
        return {
            "benchmarks": [vars(b) for b in bench]
        }

    elif name == "network_generate_optimization_plan":
        target_profile = str(arguments.get("target_profile", "balanced_standard"))
        optimizer = NetworkOptimizer(hal)
        plan = optimizer.generate_plan(target_profile=target_profile)
        return {
            "plan_id": plan.plan_id,
            "target_os": plan.target_os.value,
            "target_profile": target_profile,
            "reasoning": plan.reasoning,
            "planned_actions": [vars(a) for a in plan.planned_actions],
            "requires_elevation": plan.requires_elevation
        }

    elif name == "network_execute_optimization":
        optimizer = NetworkOptimizer(hal)
        plan = optimizer.generate_plan()
        success, logs = optimizer.execute_plan(plan, execute=execute)
        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "applied": execute,
            "success": success,
            "logs": logs
        }

    elif name == "network_triage_repair":
        repair = NetworkRepairEngine(hal)
        failure_type, triage_logs = repair.diagnose_and_triage()
        actions = repair.execute_triage_repair(failure_type, execute=execute)
        return {
            "failure_type": failure_type,
            "triage_logs": triage_logs,
            "applied": execute,
            "actions": [vars(a) for a in actions]
        }

    elif name == "network_rollback":
        snapshot_id = arguments.get("snapshot_id", "")
        mgr = RollbackManager(hal)
        logs = mgr.rollback(snapshot_id, execute=execute)
        ok = bool(logs) and not any(str(l).startswith("ERROR:") for l in logs)
        return {
            "snapshot_id": snapshot_id,
            "applied": execute and ok,
            "success": ok,
            "logs": logs
        }

    elif name == "network_persistent_monitor":
        action = str(arguments.get("action", "sample_once"))
        poll_sec = int(arguments.get("poll_interval_sec", 60))
        auto_heal = bool(arguments.get("auto_heal", False))
        daemon = NetworkDaemon(
            hal=hal,
            poll_interval_sec=poll_sec,
            auto_heal=auto_heal
        )
        if action == "status":
            return {
                "status": "daemon_configured",
                "action": action,
                "poll_interval_sec": poll_sec,
                "auto_heal": auto_heal,
                "dry_run": hal.dry_run
            }
        sample = daemon.check_and_heal_once()
        return {
            "status": "sample_recorded",
            "action": action,
            "telemetry": sample
        }

    elif name == "network_discover_and_schedule_tasks":
        exec_tasks = bool(arguments.get("execute", False))
        sched = get_task_scheduler()
        return sched.discover_and_schedule_cycle(execute=exec_tasks)

    elif name == "network_inspect_sockets":
        return inspect_active_sockets()

    elif name == "network_discover_pmtu":
        target = str(arguments.get("target", "1.1.1.1"))
        return discover_path_mtu(target=target)

    elif name == "network_audit_arp_lan":
        return audit_arp_lan()

    elif name == "network_inspect_wifi_nic":
        return inspect_wifi_and_nic()

    elif name == "network_traceroute":
        target = str(arguments.get("target", "1.1.1.1"))
        max_hops = int(arguments.get("max_hops", 8))
        trace = run_fast_traceroute(target=target, max_hops=max_hops)
        grade, idle_rtt, delta = check_bufferbloat(target=target)
        return {
            "bufferbloat_grade": grade,
            "idle_latency_ms": idle_rtt,
            "loaded_delta_ms": delta,
            "traceroute": trace
        }

    elif name == "network_speedtest":
        return measure_bandwidth_speed()

    elif name == "device_full_maintenance":
        execute = bool(arguments.get("execute", False))
        hal = get_hal(dry_run=not execute)
        return DeviceMaintenanceEngine(hal).run_full_device_maintenance(execute=execute)

    return {"error": f"Unknown tool: {name}"}


def main():
    """Main JSON-RPC stdio loop for MCP."""
    tools = load_tools_schema()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception:
            continue

        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "omninet-mcp-server",
                        "version": OMNINET_VERSION
                    },
                    "capabilities": {
                        "tools": {}
                    }
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": msg_id, "result": {}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": t["name"],
                            "description": t["description"],
                            "inputSchema": t["parameters"]
                        } for t in tools
                    ]
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                res = handle_tool_call(tool_name, tool_args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res, indent=2)
                            }
                        ]
                    }
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32000,
                        "message": str(e)
                    }
                }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
