"""
Autonomous 10-Minute Network Task Discovery, Self-Evolution & Self-Scheduler.
Proactively scans network health, sockets, DNS drift, PMTU, and ARP every 10 minutes (600s),
evolves adaptive thresholds from empirical telemetry, schedules optimization/repair tasks,
and executes them with Admin privileges under Zero NetLoss safety.
"""

from __future__ import annotations
import json
import os
import time
import uuid
import threading
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any

from .models import HealthState
from .hal import NetworkHAL, get_hal
from .elevation import is_elevated
from .diagnostics import (
    run_full_diagnostics,
    measure_target_metrics,
    inspect_active_sockets,
    discover_path_mtu,
    audit_arp_lan
)
from .optimizer import NetworkOptimizer
from .repair import NetworkRepairEngine
from .rollback import RollbackManager
from .device_maintenance import DeviceMaintenanceEngine


STATE_DIR = os.path.join(os.path.expanduser("~"), ".netopt_state")
TASKS_FILE = os.path.join(STATE_DIR, "scheduled_tasks.json")
EVOLUTION_FILE = os.path.join(STATE_DIR, "evolution_state.json")


@dataclass
class AutonomousNetworkTask:
    task_id: str
    created_at: float
    scheduled_for: float
    category: str       # DNS_OPTIMIZATION, TCP_TUNING, SOCKET_HYGIENE, PMTU_TUNE, TRIAGE_REPAIR, ROUTINE_AUDIT
    priority: str       # CRITICAL, HIGH, MEDIUM, LOW
    title: str
    reason: str
    status: str         # SCHEDULED, COMPLETED, SIMULATED, FAILED
    executed_at: Optional[float] = None
    snapshot_id: Optional[str] = None
    concise_result: str = ""


class AutonomousTaskScheduler:
    """Self-directed, self-evolving 10-minute (600s) task discovery and execution engine."""

    def __init__(
        self,
        hal: Optional[NetworkHAL] = None,
        interval_sec: int = 600,
        auto_execute: bool = True
    ):
        self.hal = hal or get_hal(dry_run=not auto_execute)
        self.interval_sec = interval_sec
        self.auto_execute = auto_execute
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self.optimizer = NetworkOptimizer(self.hal)
        self.repair_engine = NetworkRepairEngine(self.hal)
        self.rollback_mgr = RollbackManager(self.hal)
        self.tasks: List[AutonomousNetworkTask] = self._load_tasks()
        self.evolution: Dict[str, Any] = self._load_evolution()
        self.last_cycle_ts: float = 0.0
        self.next_cycle_ts: float = time.time() + self.interval_sec

    def _load_tasks(self) -> List[AutonomousNetworkTask]:
        if not os.path.exists(TASKS_FILE):
            return []
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return [AutonomousNetworkTask(**item) for item in raw]
        except Exception:
            return []

    def _save_tasks(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        try:
            with open(TASKS_FILE, "w", encoding="utf-8") as f:
                json.dump([asdict(t) for t in self.tasks[-50:]], f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_evolution(self) -> Dict[str, Any]:
        default_evo = {
            "generation": 0,
            "baseline_rtt_ms": None,
            "baseline_jitter_ms": None,
            "adaptive_rtt_threshold_ms": 240.0,
            "adaptive_jitter_threshold_ms": 15.0,
            "best_dns_provider": "Cloudflare",
            "best_dns_ip": "1.1.1.1",
            "optimal_mtu": 1500,
            "last_applied_mtu": None,
            "action_rewards": {
                "TCP_TUNING": {"runs": 0, "avg_rtt_gain_ms": 0.0},
                "DNS_OPTIMIZATION": {"runs": 0, "avg_rtt_gain_ms": 0.0},
                "PMTU_TUNE": {"runs": 0, "avg_rtt_gain_ms": 0.0},
                "TRIAGE_REPAIR": {"runs": 0, "avg_rtt_gain_ms": 0.0}
            }
        }
        if not os.path.exists(EVOLUTION_FILE):
            return default_evo
        try:
            with open(EVOLUTION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_evo.update(data)
                return default_evo
        except Exception:
            return default_evo

    def _save_evolution(self):
        os.makedirs(STATE_DIR, exist_ok=True)
        try:
            with open(EVOLUTION_FILE, "w", encoding="utf-8") as f:
                json.dump(self.evolution, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _evolve_telemetry(self, avg_rtt: float, jitter: float, best_dns: Any, opt_mtu: int, persist: bool = True):
        """Updates EWMA baselines and self-evolves anomaly detection thresholds."""
        self.evolution["generation"] = int(self.evolution.get("generation", 0)) + 1
        if avg_rtt > 0:
            base_rtt = self.evolution.get("baseline_rtt_ms")
            new_rtt = avg_rtt if base_rtt is None else round(0.8 * float(base_rtt) + 0.2 * avg_rtt, 2)
            self.evolution["baseline_rtt_ms"] = new_rtt
            self.evolution["adaptive_rtt_threshold_ms"] = round(max(180.0, new_rtt * 1.45), 2)

        if jitter >= 0:
            base_jit = self.evolution.get("baseline_jitter_ms")
            new_jit = jitter if base_jit is None else round(0.8 * float(base_jit) + 0.2 * jitter, 2)
            self.evolution["baseline_jitter_ms"] = new_jit
            self.evolution["adaptive_jitter_threshold_ms"] = round(max(12.0, new_jit * 2.2), 2)

        if best_dns:
            self.evolution["best_dns_provider"] = best_dns.provider
            self.evolution["best_dns_ip"] = best_dns.ip

        self.evolution["optimal_mtu"] = opt_mtu
        if persist:
            self._save_evolution()

    def _record_action_reward(self, category: str, rtt_before: float, rtt_after: float):
        rewards = self.evolution.setdefault("action_rewards", {})
        entry = rewards.setdefault(category, {"runs": 0, "avg_rtt_gain_ms": 0.0})
        runs = int(entry.get("runs", 0)) + 1
        gain = round(rtt_before - rtt_after, 2) if (rtt_before > 0 and rtt_after > 0) else 0.0
        prev_avg = float(entry.get("avg_rtt_gain_ms", 0.0))
        entry["runs"] = runs
        entry["avg_rtt_gain_ms"] = round(((prev_avg * (runs - 1)) + gain) / runs, 2)
        self._save_evolution()

    def discover_and_schedule_cycle(self, execute: Optional[bool] = None) -> Dict[str, Any]:
        """
        Scans all network layers, evolves baselines, autonomously generates tasks,
        executes them safely with Admin privileges, and schedules the next 10-minute cycle.
        """
        do_exec = self.auto_execute if execute is None else execute
        now = time.time()
        self.last_cycle_ts = now
        self.next_cycle_ts = now + self.interval_sec

        diag = run_full_diagnostics()
        sock_info = inspect_active_sockets()
        arp_info = audit_arp_lan()
        pmtu_info = discover_path_mtu("1.1.1.1")

        cf = diag.latency_metrics.get("1.1.1.1")
        avg_rtt = cf.avg_ms if cf else 0.0
        jitter = cf.jitter_ms if cf else 0.0
        best_dns = diag.dns_benchmarks[0] if diag.dns_benchmarks else None
        opt_mtu = int(pmtu_info.get("optimal_mtu", 1500))

        self._evolve_telemetry(avg_rtt, jitter, best_dns, opt_mtu, persist=do_exec)
        rtt_limit = float(self.evolution.get("adaptive_rtt_threshold_ms", 240.0))
        jit_limit = float(self.evolution.get("adaptive_jitter_threshold_ms", 15.0))

        discovered: List[AutonomousNetworkTask] = []

        # 1. Check L1-L7 connectivity failure
        if diag.overall_health == HealthState.DOWN or not diag.internet_reachable or not diag.dns_resolving:
            discovered.append(AutonomousNetworkTask(
                task_id=f"task_{int(now)}_{uuid.uuid4().hex[:4]}",
                created_at=now,
                scheduled_for=now,
                category="TRIAGE_REPAIR",
                priority="CRITICAL",
                title="Autorreparación L1-L7 de conectividad",
                reason="Corte de internet o fallo DNS detectado en barrido autónomo.",
                status="SCHEDULED"
            ))

        # 2. Check Bufferbloat / Latency / TCP tuning need using evolved adaptive thresholds
        if diag.bufferbloat_grade in ("C", "D", "F") or avg_rtt > rtt_limit or jitter > jit_limit:
            discovered.append(AutonomousNetworkTask(
                task_id=f"task_{int(now)}_{uuid.uuid4().hex[:4]}",
                created_at=now,
                scheduled_for=now,
                category="TCP_TUNING",
                priority="HIGH",
                title="Afinamiento TCP/BBR/RSS y mitigación Bufferbloat",
                reason=f"RTT={avg_rtt}ms (Umbral={rtt_limit}ms), Jitter={jitter}ms, Bloat={diag.bufferbloat_grade}.",
                status="SCHEDULED"
            ))

        # 3. Check DNS Resolver optimization opportunity (avoid flip-flopping among fast Anycast resolvers)
        if best_dns:
            current_dns = self.hal.get_dns_servers()
            fast_ips = {b.ip for b in diag.dns_benchmarks if b.avg_latency_ms <= best_dns.avg_latency_ms + 12.0}
            already_fast = any(ip in fast_ips for ip in current_dns)
            if (
                not already_fast
                and best_dns.avg_latency_ms < 45.0
                and self.evolution.get("last_applied_dns") != best_dns.ip
            ):
                discovered.append(AutonomousNetworkTask(
                    task_id=f"task_{int(now)}_{uuid.uuid4().hex[:4]}",
                    created_at=now,
                    scheduled_for=now,
                    category="DNS_OPTIMIZATION",
                    priority="MEDIUM",
                    title=f"Conmutación a DNS Anycast rápido ({best_dns.provider} {best_dns.ip})",
                    reason=f"Resolver óptimo responde en {best_dns.avg_latency_ms}ms (actual: {current_dns[:2]}).",
                    status="SCHEDULED"
                ))

        # 4. Check Socket Hygiene
        if sock_info.get("anomalies"):
            discovered.append(AutonomousNetworkTask(
                task_id=f"task_{int(now)}_{uuid.uuid4().hex[:4]}",
                created_at=now,
                scheduled_for=now,
                category="SOCKET_HYGIENE",
                priority="MEDIUM",
                title="Purga de caché DNS y reciclaje de sockets estancados",
                reason="; ".join(sock_info["anomalies"]),
                status="SCHEDULED"
            ))

        # 5. Check PMTU mismatch (only if not already converged to opt_mtu)
        if pmtu_info.get("needs_tuning") and self.evolution.get("last_applied_mtu") != opt_mtu:
            discovered.append(AutonomousNetworkTask(
                task_id=f"task_{int(now)}_{uuid.uuid4().hex[:4]}",
                created_at=now,
                scheduled_for=now,
                category="PMTU_TUNE",
                priority="MEDIUM",
                title=f"Ajuste automático de PMTU sin fragmentación ({opt_mtu}B)",
                reason=f"Fragmentación detectada sobre {opt_mtu} bytes hacia 1.1.1.1.",
                status="SCHEDULED"
            ))

        # 6. Check Device-Wide Faults (RAM pressure, hung processes, temp files accumulation)
        dev_maint = DeviceMaintenanceEngine(self.hal)
        dev_audit = dev_maint.diagnose_all_device_faults()
        if dev_audit.get("faults_detected"):
            discovered.append(AutonomousNetworkTask(
                task_id=f"task_{int(now)}_{uuid.uuid4().hex[:4]}",
                created_at=now,
                scheduled_for=now,
                category="DEVICE_MAINTENANCE",
                priority="MEDIUM",
                title="Mantenimiento integral del dispositivo y sistema operativo",
                reason="; ".join(dev_audit["faults_detected"][:2]),
                status="SCHEDULED"
            ))

        # 6. Always ensure at least a proactive hygiene/audit task is logged per 10-min cycle
        if not discovered:
            best_dns_str = f"{best_dns.provider} ({best_dns.avg_latency_ms}ms)" if best_dns else "OK"
            discovered.append(AutonomousNetworkTask(
                task_id=f"task_{int(now)}_{uuid.uuid4().hex[:4]}",
                created_at=now,
                scheduled_for=now,
                category="ROUTINE_AUDIT",
                priority="LOW",
                title="Auditoría evolutiva 10-min y refresco DNS",
                reason=f"Red saludable (RTT {avg_rtt}ms, Bloat {diag.bufferbloat_grade}, DNS {best_dns_str}).",
                status="SCHEDULED"
            ))

        # Execute discovered tasks safely
        for task in discovered:
            self._execute_task(task, do_exec=do_exec, rtt_before=avg_rtt, opt_mtu=opt_mtu, diag=diag)
            self.tasks.append(task)

        if do_exec:
            self._save_tasks()
        admin_flag = is_elevated()
        gen = self.evolution.get("generation", 1)

        concise_summary = (
            f"Ciclo 10m (Gen #{gen} | Admin={'SÍ' if admin_flag else 'NO'}) | "
            f"Salud: {diag.overall_health.value.upper()} | "
            f"Ping: {avg_rtt}ms (Base {self.evolution.get('baseline_rtt_ms')}ms, Jitter {jitter}ms, Bloat {diag.bufferbloat_grade}) | "
            f"PMTU: {opt_mtu}B | Sockets TCP: {sock_info.get('total_tcp', 0)} | "
            f"Tareas: {len(discovered)} | Próximo: +10m."
        )

        return {
            "cycle_timestamp": now,
            "next_cycle_in_sec": self.interval_sec,
            "generation": gen,
            "admin_elevated": admin_flag,
            "health": diag.overall_health.value,
            "rtt_ms": avg_rtt,
            "baseline_rtt_ms": self.evolution.get("baseline_rtt_ms"),
            "adaptive_rtt_threshold_ms": rtt_limit,
            "jitter_ms": jitter,
            "bufferbloat": diag.bufferbloat_grade,
            "optimal_mtu": opt_mtu,
            "active_tcp_sockets": sock_info.get("total_tcp", 0),
            "arp_neighbors": arp_info.get("neighbor_count", 0),
            "tasks_executed": [asdict(t) for t in discovered],
            "concise_summary": concise_summary
        }

    def _execute_task(self, task: AutonomousNetworkTask, do_exec: bool, rtt_before: float = 0.0, opt_mtu: int = 1500, diag: Any = None):
        mutating_categories = ("TRIAGE_REPAIR", "TCP_TUNING", "DNS_OPTIMIZATION", "PMTU_TUNE")
        if do_exec and task.category in ("TRIAGE_REPAIR", "PMTU_TUNE"):
            snap = self.rollback_mgr.capture_snapshot(description=f"AutoTask {task.task_id} ({task.category})")
            task.snapshot_id = snap.snapshot_id

        try:
            if task.category == "TRIAGE_REPAIR":
                ft, _ = self.repair_engine.diagnose_and_triage()
                acts = self.repair_engine.execute_triage_repair(ft, execute=do_exec)
                task.concise_result = f"Triage {ft}: {len(acts)} acciones ({'APLICADO' if do_exec else 'SIMULADO'})."
            elif task.category in ("TCP_TUNING", "DNS_OPTIMIZATION"):
                plan = self.optimizer.generate_plan(diag=diag)
                ok, logs = self.optimizer.execute_plan(plan, execute=do_exec)
                if plan.rollback_snapshot_id:
                    task.snapshot_id = plan.rollback_snapshot_id
                if do_exec and task.category == "DNS_OPTIMIZATION" and diag and diag.dns_benchmarks:
                    self.evolution["last_applied_dns"] = diag.dns_benchmarks[0].ip
                    self._save_evolution()
                task.concise_result = f"Plan {plan.plan_id[:8]}: {'OK' if ok else 'REVERTIDO'} ({len(plan.planned_actions)} ajustes)."
            elif task.category == "SOCKET_HYGIENE":
                res = self.hal.flush_dns_cache(execute=do_exec)
                task.concise_result = f"Caché DNS y tabla de resolución depuradas (success={res.success})."
            elif task.category == "PMTU_TUNE":
                if do_exec:
                    for iface in self.hal.get_interfaces():
                        if iface.is_up and not iface.is_loopback:
                            self.hal.set_interface_mtu(iface.name, opt_mtu, execute=True)
                    self.evolution["last_applied_mtu"] = opt_mtu
                    self._save_evolution()
                task.concise_result = f"PMTU óptimo ({opt_mtu}B) {'aplicado' if do_exec else 'simulado'}."
            elif task.category == "DEVICE_MAINTENANCE":
                dev_res = DeviceMaintenanceEngine(self.hal).run_full_device_maintenance(execute=do_exec)
                task.snapshot_id = dev_res.get("snapshot_id")
                task.concise_result = (
                    f"Mantenimiento OS ({dev_res['platform']}): "
                    f"{len(dev_res.get('actions_executed', []))} rutinas ejecutadas, "
                    f"{dev_res.get('temp_cleanup', {}).get('freed_mb', 0)} MB liberados."
                )
            else:
                self.hal.flush_dns_cache(execute=do_exec)
                task.concise_result = "Auditoría 10m sin anomalías; caché DNS refrescada."

            if do_exec and task.category in mutating_categories and rtt_before > 0:
                after_m = measure_target_metrics("1.1.1.1", count=2, port=53)
                self._record_action_reward(task.category, rtt_before, after_m.avg_ms)

            task.status = "COMPLETED" if do_exec else "SIMULATED"
        except Exception as e:
            task.status = "FAILED"
            task.concise_result = f"Error: {str(e)}"
        finally:
            task.executed_at = round(time.time(), 2)

    def _loop(self):
        while self.running:
            try:
                self.discover_and_schedule_cycle(execute=self.auto_execute)
            except Exception:
                pass
            time.sleep(self.interval_sec)

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="Autonomous10MinScheduler")
        self._thread.start()

    def stop(self):
        self.running = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "interval_sec": self.interval_sec,
            "interval_human": "10 minutes (600s)",
            "auto_execute": self.auto_execute,
            "admin_elevated": is_elevated(),
            "evolution": self.evolution,
            "last_cycle_ts": self.last_cycle_ts,
            "next_cycle_ts": self.next_cycle_ts,
            "total_tasks_history": len(self.tasks),
            "recent_tasks": [asdict(t) for t in self.tasks[-10:]]
        }


_SCHEDULER_INSTANCE: Optional[AutonomousTaskScheduler] = None


def get_task_scheduler() -> AutonomousTaskScheduler:
    global _SCHEDULER_INSTANCE
    if _SCHEDULER_INSTANCE is None:
        _SCHEDULER_INSTANCE = AutonomousTaskScheduler(interval_sec=600, auto_execute=True)
    return _SCHEDULER_INSTANCE
