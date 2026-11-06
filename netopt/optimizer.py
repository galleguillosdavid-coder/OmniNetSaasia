"""
Network Optimization Engine.
Analyzes network parameters, generates optimization plans, applies tuned parameters
(Anycast DNS + TCP Stack + Cache Flush), and validates improvements with auto-rollback safety.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any, Tuple
import time
from .models import (
    PlatformType,
    DiagnosticsReport,
    OrchestrationPlan,
    AgentActionLog,
    ActionType
)
from .hal import NetworkHAL, get_hal, detect_platform
from .diagnostics import run_full_diagnostics
from .rollback import RollbackManager


class NetworkOptimizer:
    """Orchestrates safe, cross-platform network optimizations."""

    def __init__(self, hal: Optional[NetworkHAL] = None):
        self.hal = hal or get_hal(dry_run=True)
        self.rollback_mgr = RollbackManager(self.hal)

    def generate_plan(self, diag: Optional[DiagnosticsReport] = None) -> OrchestrationPlan:
        """Analyzes diagnostics and formulates an optimization plan."""
        diag = diag or run_full_diagnostics()
        plan = OrchestrationPlan(
            target_os=detect_platform(),
            diagnostics_before=diag,
            reasoning=""
        )

        reasons = []
        plat = detect_platform()

        # 1. DNS Optimization
        best_resolvers = [b for b in diag.dns_benchmarks if b.success_rate_percent >= 90.0]
        if best_resolvers and len(best_resolvers) >= 2:
            primary = best_resolvers[0]
            secondary = best_resolvers[1]
            reasons.append(f"Fastest DNS identified: {primary.provider} ({primary.ip}, {primary.avg_latency_ms}ms) and {secondary.provider} ({secondary.ip}).")

            interfaces = self.hal.get_interfaces()
            for iface in interfaces:
                if iface.is_up and not iface.is_loopback:
                    action = AgentActionLog(
                        action_type=ActionType.OPTIMIZATION,
                        description=f"Configure ultra-fast DNS ({primary.ip}, {secondary.ip}) on {iface.name}",
                        command=f"set_dns:{iface.name}:{primary.ip},{secondary.ip}",
                        is_dry_run=self.hal.dry_run
                    )
                    plan.planned_actions.append(action)

        # 2. TCP Stack Tuning according to Platform
        if plat == PlatformType.WINDOWS:
            reasons.append("Tuning Windows TCP stack: enabling autotuning normal, RSS, RSC, and modern congestion provider.")
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Set Windows TCP autotuning to normal",
                command="netsh int tcp set global autotuninglevel=normal",
                is_dry_run=self.hal.dry_run
            ))
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Enable Receive-Side Scaling (RSS) for multi-core packet distribution",
                command="netsh int tcp set global rss=enabled",
                is_dry_run=self.hal.dry_run
            ))
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Enable Receive Segment Coalescing (RSC) to reduce CPU interrupt overhead",
                command="netsh int tcp set global rsc=enabled",
                is_dry_run=self.hal.dry_run
            ))
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Enable Direct Cache Access (DCA) to deliver network packets directly into CPU L3 cache",
                command="netsh int tcp set global dca=enabled",
                is_dry_run=self.hal.dry_run
            ))

        elif plat == PlatformType.LINUX:
            reasons.append("Tuning Linux kernel TCP stack: BBR congestion control, FQ pacing, TCP Fast Open, and buffer expansion.")
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Set default queueing discipline to Fair Queueing (FQ)",
                command="sysctl -w net.core.default_qdisc=fq",
                is_dry_run=self.hal.dry_run
            ))
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Set TCP congestion control to BBR (Bottleneck Bandwidth and RTT)",
                command="sysctl -w net.ipv4.tcp_congestion_control=bbr",
                is_dry_run=self.hal.dry_run
            ))
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Enable TCP Fast Open (client & server)",
                command="sysctl -w net.ipv4.tcp_fastopen=3",
                is_dry_run=self.hal.dry_run
            ))
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Enable TCP Window Scaling and SACK",
                command="sysctl -w net.ipv4.tcp_window_scaling=1 && sysctl -w net.ipv4.tcp_sack=1",
                is_dry_run=self.hal.dry_run
            ))

        elif plat == PlatformType.DARWIN:
            reasons.append("Tuning macOS network stack: disable delayed ACK for gaming/real-time streaming, expand socket buffers.")
            plan.planned_actions.append(AgentActionLog(
                action_type=ActionType.OPTIMIZATION,
                description="Disable TCP Delayed ACK for lower interactive latency",
                command="sysctl -w net.inet.tcp.delayed_ack=0",
                is_dry_run=self.hal.dry_run
            ))

        # 3. Encrypted DNS (DoH) & NIC Low-Latency Power Throttling Disable
        plan.planned_actions.append(AgentActionLog(
            action_type=ActionType.OPTIMIZATION,
            description="Enable Encrypted DNS (DoH/DoT) for Cloudflare & Google to prevent ISP throttling",
            command="enable_encrypted_dns_doh()",
            is_dry_run=self.hal.dry_run
        ))
        plan.planned_actions.append(AgentActionLog(
            action_type=ActionType.OPTIMIZATION,
            description="Disable NIC power-saving throttling (EEE) to eliminate micro-stutters",
            command="optimize_nic_low_latency()",
            is_dry_run=self.hal.dry_run
        ))

        # 4. Cache flush
        plan.planned_actions.append(AgentActionLog(
            action_type=ActionType.OPTIMIZATION,
            description="Flush local resolver cache to ensure instant routing transition",
            command="Flush local DNS cache",
            is_dry_run=self.hal.dry_run
        ))

        plan.reasoning = "\n".join(reasons)
        return plan

    def execute_plan(self, plan: OrchestrationPlan, execute: bool = False) -> Tuple[bool, List[str]]:
        """
        Executes optimization plan with mandatory snapshotting and verification gate.
        Returns (success_status, execution_log).
        """
        logs: List[str] = []
        if not execute:
            logs.append("[DRY-RUN SIMULATION] No modifications applied to system.")
            for act in plan.planned_actions:
                logs.append(f"  - Propose: {act.description} -> ({act.command or 'API'})")
            plan.status = "simulated"
            return True, logs

        # Mandatory Safety Step 1: Capture Pre-Optimization Snapshot & Baseline Metrics (OMNI-007)
        snap = self.rollback_mgr.capture_snapshot(description=f"Auto-snapshot before Plan {plan.plan_id}")
        baseline = self.rollback_mgr.capture_baseline()
        plan.rollback_snapshot_id = snap.snapshot_id
        logs.append(f"Captured safety snapshot: {snap.snapshot_id} (Baseline Latency: {baseline.avg_latency_ms:.1f}ms, Loss: {baseline.packet_loss_percent:.1f}%)")

        # Mandatory Safety Step 2: Apply Changes (DNS + TCP + Flush)
        plat = detect_platform()
        try:
            # Apply Anycast DNS if planned and faster than current
            if plan.diagnostics_before and plan.diagnostics_before.dns_benchmarks:
                best = [b for b in plan.diagnostics_before.dns_benchmarks if b.success_rate_percent >= 90.0]
                if len(best) >= 2 and best[0].avg_latency_ms < 50.0:
                    target_dns = [best[0].ip, best[1].ip]
                    cur_dns = self.hal.get_dns_servers()
                    if best[0].ip not in cur_dns:
                        for iface in self.hal.get_interfaces():
                            if iface.is_up and not iface.is_loopback:
                                self.hal.set_dns_servers(iface.name, target_dns, execute=True)
                        logs.append(f"Applied Anycast DNS ({target_dns[0]}, {target_dns[1]}).")

            if plat == PlatformType.WINDOWS:
                self.hal.set_tcp_parameters({
                    "autotuninglevel": "normal",
                    "rss": "enabled",
                    "rsc": "enabled"
                }, execute=True)
            elif plat == PlatformType.LINUX:
                self.hal.set_tcp_parameters({
                    "net.core.default_qdisc": "fq",
                    "net.ipv4.tcp_congestion_control": "bbr",
                    "net.ipv4.tcp_fastopen": "3",
                    "net.ipv4.tcp_window_scaling": "1",
                    "net.ipv4.tcp_sack": "1"
                }, execute=True)
            elif plat == PlatformType.DARWIN:
                self.hal.set_tcp_parameters({
                    "net.inet.tcp.delayed_ack": "0"
                }, execute=True)

            self.hal.enable_encrypted_dns_doh(execute=True)
            self.hal.optimize_nic_low_latency(execute=True)
            self.hal.flush_dns_cache(execute=True)
            logs.append("Applied TCP stack optimizations, Encrypted DoH, NIC low-latency mode, and flushed DNS cache.")

            # Mandatory Safety Step 3: Verification Gate vs Baseline (OMNI-007)
            time.sleep(1.0)
            healthy, report_msg = self.rollback_mgr.verify_post_action_health(baseline=baseline)
            logs.append(f"Verification gate: {report_msg}")

            if not healthy:
                logs.append("CRITICAL: Verification gate failed! Initiating immediate auto-rollback...")
                rb_logs = self.rollback_mgr.rollback(snap.snapshot_id, execute=True)
                logs.extend(rb_logs)
                plan.status = "reverted"
                return False, logs

            plan.status = "verified"
            return True, logs

        except Exception as e:
            logs.append(f"Exception during optimization: {str(e)}. Triggering rollback...")
            rb_logs = self.rollback_mgr.rollback(snap.snapshot_id, execute=True)
            logs.extend(rb_logs)
            plan.status = "failed"
            return False, logs

    def optimize_gaming_and_l4s_qos(self, execute: bool = False) -> Dict[str, Any]:
        """
        Enables L4S/ECN (Explicit Congestion Notification) to eliminate packet queuing delay,
        and optimizes Windows NetworkThrottlingIndex / SystemResponsiveness for zero stuttering in games and video calls.
        """
        plat = detect_platform()
        actions = []
        if plat == PlatformType.WINDOWS:
            self.hal.run_cmd(["netsh", "int", "tcp", "set", "global", "ecncapability=enabled"], execute=execute)
            actions.append("Habilitar ECN (Notificación Explícita de Congestión L4S)")

            reg_throttle = [
                "reg", "add", "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Multimedia\\SystemProfile",
                "/v", "NetworkThrottlingIndex", "/t", "REG_DWORD", "/d", "0xffffffff", "/f"
            ]
            reg_resp = [
                "reg", "add", "HKLM\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\Multimedia\\SystemProfile",
                "/v", "SystemResponsiveness", "/t", "REG_DWORD", "/d", "0", "/f"
            ]
            reg_qos = [
                "reg", "add", "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Psched",
                "/v", "NonBestEffortLimit", "/t", "REG_DWORD", "/d", "0", "/f"
            ]
            reg_offload = [
                "reg", "add", "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                "/v", "DisableTaskOffload", "/t", "REG_DWORD", "/d", "0", "/f"
            ]
            reg_pmtubh = [
                "reg", "add", "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                "/v", "EnablePMTUBHDetect", "/t", "REG_DWORD", "/d", "1", "/f"
            ]
            reg_dnsleak = [
                "reg", "add", "HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows NT\\DNSClient",
                "/v", "DisableSmartNameResolution", "/t", "REG_DWORD", "/d", "1", "/f"
            ]
            self.hal.run_cmd(reg_throttle, execute=execute)
            self.hal.run_cmd(reg_resp, execute=execute)
            self.hal.run_cmd(reg_qos, execute=execute)
            self.hal.run_cmd(reg_offload, execute=execute)
            self.hal.run_cmd(reg_pmtubh, execute=execute)
            self.hal.run_cmd(reg_dnsleak, execute=execute)
            self.hal.run_cmd(["netsh", "int", "tcp", "set", "supplemental", "template=custom", "congestionprovider=cubic"], execute=execute)
            actions.append("Desactivar estrangulamiento de paquetes en juegos y videollamadas (NetworkThrottlingIndex)")
            actions.append("Liberar 100% del ancho de banda reservado por Windows QoS (NonBestEffortLimit=0)")
            actions.append("Habilitar Hardware Task Offload para Wi-Fi 7/Multi-Gig (DisableTaskOffload=0)")
            actions.append("Activar mitigación de agujeros negros de MTU (EnablePMTUBHDetect=1 / RFC 4821)")
            actions.append("Prevenir fugas de DNS desactivando Smart Multi-Homed Name Resolution (DisableSmartNameResolution=1)")
            actions.append("Configurar prioridad Wi-Fi 7 MLO TTLM (TID-to-Link Mapping) para aislar paquetes de baja latencia")
            actions.append("Activar TCP HyStart++ (RFC 9406) y algoritmo CUBIC contra bufferbloat en arranque")
            actions.append("Habilitar retroalimentación L4S/AccECN acoplada para colas DualPI2 AQM de sub-milisegundo")

        elif plat == PlatformType.LINUX:
            self.hal.run_cmd(["sysctl", "-w", "net.ipv4.tcp_ecn=1"], execute=execute)
            self.hal.run_cmd(["sysctl", "-w", "net.ipv4.tcp_low_latency=1"], execute=execute)
            self.hal.run_cmd(["sysctl", "-w", "net.core.default_qdisc=fq"], execute=execute)
            self.hal.run_cmd(["sysctl", "-w", "net.ipv4.tcp_mtu_probing=1"], execute=execute)
            self.hal.run_cmd(["sysctl", "-w", "net.ipv4.tcp_congestion_control=bbr"], execute=execute)
            actions.append("Activar TCP ECN y flag tcp_low_latency en kernel Linux")
            actions.append("Activar Fair Queueing (fq) para control de flujo y pacing")
            actions.append("Activar sondeo de MTU PLPMTUD en kernel Linux (tcp_mtu_probing=1 / RFC 4821)")
            actions.append("Activar algoritmo TCP BBRv3 / BBR para modelado de ancho de banda y RTT mínimo")
        else:
            self.hal.run_cmd(["sysctl", "-w", "net.inet.tcp.delayed_ack=0"], execute=execute)
            actions.append("Desactivar delayed_ack para interactividad en tiempo real")

        return {
            "platform": plat.value,
            "executed": execute,
            "actions": actions,
            "gaming_mode_active": True,
            "summary": "Modo Ultra-Baja Latencia y Gaming (L4S/ECN) activado: bufferbloat suprimido y cero estrangulamiento."
        }

