"""
Hierarchical Network Triage and Auto-Repair Engine.
Executes systematic, layered diagnosis and self-healing across OSI Layers 1-7.
Guarantees verifiable recovery with safe dry-run capabilities.
"""

from __future__ import annotations
from typing import List, Dict, Optional, Tuple
import time
from .models import (
    PlatformType,
    HealthState,
    DiagnosticsReport,
    AgentActionLog,
    ActionType
)
from .hal import NetworkHAL, get_hal, detect_platform
from .diagnostics import (
    run_full_diagnostics,
    tcp_ping,
    measure_target_metrics,
    query_dns_resolver_latency,
    check_duplicate_default_gateways_status
)


class NetworkRepairEngine:
    """Triage decision tree for automated network failure recovery."""

    def __init__(self, hal: Optional[NetworkHAL] = None):
        self.hal = hal or get_hal(dry_run=True)

    def diagnose_and_triage(self, diag: Optional[DiagnosticsReport] = None) -> Tuple[str, List[str]]:
        """
        Runs triage to identify exact failure level:
        - L1_INTERFACE_DOWN
        - L2_DHCP_OR_GATEWAY_FAILURE
        - L3_ROUTING_OR_INTERNET_CUT
        - L4_DNS_FAILURE
        - L7_HIGH_LOSS_OR_DEGRADED
        - HEALTHY
        """
        diag = diag or run_full_diagnostics()
        logs = []

        if diag.overall_health == HealthState.HEALTHY:
            return "HEALTHY", ["Network is currently healthy. No triage repair needed."]

        # Check Layer 1: Physical/logical interface state (when HAL provides a concrete non-empty list of down interfaces)
        ifaces = self.hal.get_interfaces()
        if isinstance(ifaces, list) and len(ifaces) > 0:
            non_loop = [i for i in ifaces if not getattr(i, "is_loopback", False)]
            if non_loop and not any(getattr(i, "is_up", False) for i in non_loop) and not diag.active_interface:
                logs.append("All physical/logical non-loopback network interfaces are DOWN (Layer 1).")
                return "L1_INTERFACE_DOWN", logs

        # Check Layer 2: Gateway reachability
        if not diag.gateway_reachable:
            logs.append(f"Gateway {diag.default_gateway or 'Unknown'} is unreachable.")
            return "L2_DHCP_OR_GATEWAY_FAILURE", logs

        # Check Layer 3 & 4: Internet vs DNS
        if not diag.internet_reachable:
            # Check for Windows 11 24H2 duplicate default gateway conflict before full reset
            dup_status = check_duplicate_default_gateways_status()
            if dup_status.get("has_duplicate_gateways"):
                logs.append("Conflicto de enrutamiento detectado: Múltiples puertas de enlace 0.0.0.0/0 en Windows 11 24H2.")
                return "L3_DUPLICATE_GATEWAY_CONFLICT", logs
            logs.append("Public IP reachability test failed (1.1.1.1 and 8.8.8.8 unreachable).")
            return "L3_ROUTING_OR_INTERNET_CUT", logs

        if not diag.dns_resolving:
            logs.append("Public internet is reachable, but DNS name resolution is failing.")
            return "L4_DNS_FAILURE", logs

        # Check Path MTU Black Hole (RFC 4821 PLPMTUD)
        if diag.detected_pmtu and 0 < diag.detected_pmtu < 1400:
            logs.append(f"Posible agujero negro de MTU detectado (Path MTU={diag.detected_pmtu} < 1400).")
            return "L3_PMTU_BLACKHOLE", logs

        if diag.overall_health == HealthState.DEGRADED:
            logs.append("High packet loss or extreme jitter detected.")
            return "L7_HIGH_LOSS_OR_DEGRADED", logs

        return "UNKNOWN_DEGRADATION", logs

    def execute_triage_repair(self, failure_type: str, execute: bool = False) -> List[AgentActionLog]:
        """
        Executes targeted remedial action for the diagnosed failure tier
        while enforcing dry-run HAL safety invariants.
        """
        should_apply = bool(execute and not (getattr(self.hal, "dry_run", False) is True))
        handlers = {
            "L1_INTERFACE_DOWN": self._repair_l1_interface_down,
            "L2_DHCP_OR_GATEWAY_FAILURE": self._repair_l2_dhcp_gateway,
            "L4_DNS_FAILURE": self._repair_l4_dns,
            "L3_DUPLICATE_GATEWAY_CONFLICT": self._repair_l3_duplicate_gateways,
            "L3_PMTU_BLACKHOLE": self._repair_l3_pmtu_blackhole,
            "L3_ROUTING_OR_INTERNET_CUT": self._repair_soft_reset,
            "L7_HIGH_LOSS_OR_DEGRADED": self._repair_soft_reset,
        }
        handler = handlers.get(failure_type)
        if handler is None:
            return []
        return handler(should_apply)

    def _repair_l1_interface_down(self, execute: bool) -> List[AgentActionLog]:
        actions: List[AgentActionLog] = list(self.hal.reset_network_stack(execute=execute))
        act_dhcp = self.hal.renew_dhcp_lease(execute=execute)
        act_dhcp.description = "Re-enable interface and request fresh DHCP lease"
        actions.append(act_dhcp)
        return actions

    def _repair_l2_dhcp_gateway(self, execute: bool) -> List[AgentActionLog]:
        act1 = self.hal.renew_dhcp_lease(execute=execute)
        act1.description = "Renew DHCP lease to re-acquire valid gateway and IP lease"
        plat = detect_platform()
        arp_cmd = (
            ["netsh", "interface", "ip", "delete", "arpcache"]
            if plat == PlatformType.WINDOWS
            else (["ip", "neigh", "flush", "all"] if plat == PlatformType.LINUX else ["arp", "-d", "-a"])
        )
        act_arp = self.hal.run_cmd(arp_cmd, execute=execute)
        act_arp.description = "Flush stale ARP / Neighbor MAC cache"
        act2 = self.hal.flush_dns_cache(execute=execute)
        return [act1, act_arp, act2]

    def _repair_l4_dns(self, execute: bool) -> List[AgentActionLog]:
        actions: List[AgentActionLog] = [self.hal.flush_dns_cache(execute=execute)]
        for iface in self.hal.get_interfaces():
            if iface.is_up and not iface.is_loopback:
                act_dns = self.hal.set_dns_servers(
                    iface.name,
                    ["1.1.1.1", "8.8.8.8", "9.9.9.9"],
                    execute=execute,
                )
                act_dns.description = f"Override broken DNS on {iface.name} with Cloudflare/Google/Quad9"
                actions.append(act_dns)
        return actions

    def _repair_l3_duplicate_gateways(self, execute: bool) -> List[AgentActionLog]:
        actions: List[AgentActionLog] = list(self.hal.prune_duplicate_default_gateways(execute=execute))
        actions.append(self.hal.flush_dns_cache(execute=execute))
        return actions

    def _repair_l3_pmtu_blackhole(self, execute: bool) -> List[AgentActionLog]:
        actions: List[AgentActionLog] = []
        plat = detect_platform()
        if plat == PlatformType.WINDOWS:
            act = self.hal.run_cmd([
                "reg", "add", "HKLM\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters",
                "/v", "EnablePMTUBHDetect", "/t", "REG_DWORD", "/d", "1", "/f",
            ], execute=execute)
            act.description = "Enable RFC 4821 PLPMTUD Black Hole Detection in Windows Registry"
            actions.append(act)
        elif plat == PlatformType.LINUX:
            act = self.hal.run_cmd(["sysctl", "-w", "net.ipv4.tcp_mtu_probing=1"], execute=execute)
            act.description = "Enable RFC 4821 PLPMTUD in Linux kernel (tcp_mtu_probing=1)"
            actions.append(act)
        elif plat == PlatformType.DARWIN:
            act = self.hal.run_cmd(["sysctl", "-w", "net.inet.tcp.path_mtu_discovery=1"], execute=execute)
            act.description = "Enable RFC 4821 PLPMTUD in macOS kernel (path_mtu_discovery=1)"
            actions.append(act)
        actions.append(self.hal.flush_dns_cache(execute=execute))
        return actions

    def _repair_soft_reset(self, execute: bool) -> List[AgentActionLog]:
        return list(self.hal.reset_network_stack(execute=execute))

