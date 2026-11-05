"""
Command-Line Interface for OmniNet Network Orchestrator.
Provides human and AI agents with direct commands. Default mode is strictly DRY-RUN.
"""

from __future__ import annotations
import argparse
import json
import sys
from .diagnostics import run_full_diagnostics, benchmark_all_resolvers
from .optimizer import NetworkOptimizer
from .repair import NetworkRepairEngine
from .rollback import RollbackManager, SNAPSHOT_DIR
from .persistence import NetworkDaemon
from .hal import get_hal, detect_platform
import os


def format_diagnostics(diag) -> str:
    lines = [
        "=" * 60,
        f" OMNINET DIAGNOSTICS REPORT - OS: {diag.platform.value.upper()}",
        "=" * 60,
        f"Overall Health   : {diag.overall_health.value.upper()}",
        f"Gateway Reachable: {'YES' if diag.gateway_reachable else 'NO'} ({diag.default_gateway or 'None'})",
        f"Internet Access  : {'YES' if diag.internet_reachable else 'NO'}",
        f"DNS Resolving    : {'YES' if diag.dns_resolving else 'NO'}",
        f"Bufferbloat Grade: {diag.bufferbloat_grade}",
        "-" * 60,
        "LATENCY & LOSS METRICS:"
    ]
    for target, m in diag.latency_metrics.items():
        lines.append(f"  [{target}] Avg: {m.avg_ms}ms | Min: {m.min_ms}ms | Max: {m.max_ms}ms | Loss: {m.packet_loss_percent}% | Jitter: {m.jitter_ms}ms")

    lines.append("-" * 60)
    lines.append("TOP DNS BENCHMARKS:")
    for b in diag.dns_benchmarks[:4]:
        lines.append(f"  {b.provider:<20} {b.ip:<16} Latency: {b.avg_latency_ms:>5}ms  (Success: {b.success_rate_percent}%)")

    if diag.anomalies:
        lines.append("-" * 60)
        lines.append("DETECTED ANOMALIES:")
        for an in diag.anomalies:
            lines.append(f"  ! {an}")
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="OmniNet - Autonomous Cross-Platform Network Optimizer & Healer"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # diagnose
    diag_parser = subparsers.add_parser("diagnose", help="Run non-destructive network health sweep")
    diag_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # benchmark-dns
    dns_parser = subparsers.add_parser("benchmark-dns", help="Benchmark public DNS resolvers")
    dns_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # optimize
    opt_parser = subparsers.add_parser("optimize", help="Generate or apply network optimization plan")
    opt_parser.add_argument("--apply", action="store_true", help="Apply optimizations (requires elevated admin privileges)")
    opt_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # repair
    rep_parser = subparsers.add_parser("repair", help="Run triage and auto-repair broken network connectivity")
    rep_parser.add_argument("--apply", action="store_true", help="Apply repair actions (requires elevated admin privileges)")
    rep_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # rollback
    rb_parser = subparsers.add_parser("rollback", help="Restore configuration from a previous snapshot")
    rb_parser.add_argument("--snapshot-id", type=str, help="Specific snapshot ID to restore")
    rb_parser.add_argument("--list", action="store_true", help="List available snapshots")
    rb_parser.add_argument("--apply", action="store_true", help="Execute rollback on system")

    # daemon
    daemon_parser = subparsers.add_parser("daemon", help="Run background persistent monitor and self-healing loop")
    daemon_parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    daemon_parser.add_argument("--auto-heal", action="store_true", help="Automatically trigger self-healing upon failure")
    daemon_parser.add_argument("--cycles", type=int, default=None, help="Max cycles before stopping")

    args = parser.parse_args()

    if args.command == "diagnose":
        diag = run_full_diagnostics()
        if args.json:
            print(json.dumps({
                "platform": diag.platform.value,
                "overall_health": diag.overall_health.value,
                "gateway_reachable": diag.gateway_reachable,
                "internet_reachable": diag.internet_reachable,
                "dns_resolving": diag.dns_resolving,
                "bufferbloat_grade": diag.bufferbloat_grade,
                "anomalies": diag.anomalies,
                "latency_metrics": {k: vars(v) for k, v in diag.latency_metrics.items()},
                "dns_benchmarks": [vars(b) for b in diag.dns_benchmarks]
            }, indent=2))
        else:
            print(format_diagnostics(diag))

    elif args.command == "benchmark-dns":
        bench = benchmark_all_resolvers()
        if args.json:
            print(json.dumps([vars(b) for b in bench], indent=2))
        else:
            print(f"{'Provider':<24} {'IP':<16} {'Latency':<10} {'Success %':<10}")
            print("-" * 62)
            for b in bench:
                print(f"{b.provider:<24} {b.ip:<16} {b.avg_latency_ms:>6.2f}ms    {b.success_rate_percent:>5.1f}%")

    elif args.command == "optimize":
        hal = get_hal(dry_run=not args.apply)
        optimizer = NetworkOptimizer(hal)
        plan = optimizer.generate_plan()
        success, logs = optimizer.execute_plan(plan, execute=args.apply)
        if args.json:
            print(json.dumps({
                "plan_id": plan.plan_id,
                "status": plan.status,
                "reasoning": plan.reasoning,
                "applied": args.apply,
                "success": success,
                "logs": logs
            }, indent=2))
        else:
            print(f"Plan ID: {plan.plan_id}")
            print(f"Reasoning:\n{plan.reasoning}\n")
            print("Execution Log:")
            for l in logs:
                print(f"  {l}")

    elif args.command == "repair":
        hal = get_hal(dry_run=not args.apply)
        repair_engine = NetworkRepairEngine(hal)
        failure_type, triage_logs = repair_engine.diagnose_and_triage()
        actions = repair_engine.execute_triage_repair(failure_type, execute=args.apply)
        if args.json:
            print(json.dumps({
                "failure_type": failure_type,
                "triage_logs": triage_logs,
                "applied": args.apply,
                "actions": [vars(a) for a in actions]
            }, indent=2))
        else:
            print(f"Diagnosed Failure Tier: {failure_type}")
            for tl in triage_logs:
                print(f"  - {tl}")
            print("\nRepair Actions:")
            for act in actions:
                status = "DRY-RUN" if act.is_dry_run else ("SUCCESS" if act.success else "FAILED")
                print(f"  [{status}] {act.description} -> {act.command or 'API'}")

    elif args.command == "rollback":
        hal = get_hal(dry_run=not args.apply)
        mgr = RollbackManager(hal)
        if args.list:
            if not os.path.exists(SNAPSHOT_DIR):
                print("No snapshots found.")
                return
            snaps = [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json")]
            print(f"Available Snapshots ({len(snaps)}):")
            for s in snaps:
                print(f"  - {s.replace('.json', '')}")
        elif args.snapshot_id:
            logs = mgr.rollback(args.snapshot_id, execute=args.apply)
            print(f"Rollback status for {args.snapshot_id} (Execute: {args.apply}):")
            for l in logs:
                print(f"  {l}")
        else:
            print("Please specify --snapshot-id <id> or --list.")

    elif args.command == "daemon":
        hal = get_hal(dry_run=True)
        daemon = NetworkDaemon(
            hal=hal,
            poll_interval_sec=args.interval,
            auto_heal=args.auto_heal
        )
        print(f"Starting OmniNet Daemon (Interval: {args.interval}s, Auto-Heal: {args.auto_heal})...")
        def print_cb(res):
            print(f"[{time.strftime('%X')}] Health: {res['health'].upper()} | Actions: {len(res['actions_taken'])}")
            for a in res["actions_taken"]:
                print(f"   * {a}")
        daemon.run_loop(max_cycles=args.cycles, callback=print_cb)


if __name__ == "__main__":
    main()

