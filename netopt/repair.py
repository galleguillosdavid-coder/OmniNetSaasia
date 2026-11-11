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

        if diag.overall_health == HealthState.DEGRADED:
            logs.append("High packet loss or extreme jitter detected.")
            return "L7_HIGH_LOSS_OR_DEGRADED", logs

        return "UNKNOWN_DEGRADATION", logs

    def execute_triage_repair(self, failure_type: str, execute: bool = False) -> List[AgentActionLog]:
        """
        Executes targeted remedial action for the diagnosed failure tier.
        """
        actions: List[AgentActionLog] = []

        if failure_type == "L1_INTERFACE_DOWN":
            reset_logs = self.hal.reset_network_stack(execute=execute)
            actions.extend(reset_logs)
            act_dhcp = self.hal.renew_dhcp_lease(execute=execute)
            act_dhcp.description = "Re-enable interface and request fresh DHCP lease"
            actions.append(act_dhcp)

        elif failure_type == "L2_DHCP_OR_GATEWAY_FAILURE":
            # Action: Renew DHCP lease, clear local ARP neighbor cache, and flush DNS cache
            act1 = self.hal.renew_dhcp_lease(execute=execute)
            act1.description = "Renew DHCP lease to re-acquire valid gateway and IP lease"
            actions.append(act1)

            plat = detect_platform()
            arp_cmd = (
                ["netsh", "interface", "ip", "delete", "arpcache"]
                if plat == PlatformType.WINDOWS
                else (["ip", "neigh", "flush", "all"] if plat == PlatformType.LINUX else ["arp", "-d", "-a"])
            )
            act_arp = self.hal.run_cmd(arp_cmd, execute=execute)
            act_arp.description = "Flush stale ARP / Neighbor MAC cache"
            actions.append(act_arp)

            act2 = self.hal.flush_dns_cache(execute=execute)
            actions.append(act2)

        elif failure_type == "L4_DNS_FAILURE":
            # Action: Flush DNS cache, then assign resilient public Anycast DNS
            act_flush = self.hal.flush_dns_cache(execute=execute)
            actions.append(act_flush)

            interfaces = self.hal.get_interfaces()
            for iface in interfaces:
                if iface.is_up and not iface.is_loopback:
                    act_dns = self.hal.set_dns_servers(
                        iface.name,
                        ["1.1.1.1", "8.8.8.8", "9.9.9.9"],
                        execute=execute
                    )
                    act_dns.description = f"Override broken DNS on {iface.name} with Cloudflare/Google/Quad9"
                    actions.append(act_dns)

        elif failure_type == "L3_DUPLICATE_GATEWAY_CONFLICT":
            # Action: Prune rogue/stale duplicate gateways and flush DNS
            prune_logs = self.hal.prune_duplicate_default_gateways(execute=execute)
            actions.extend(prune_logs)
            act_flush = self.hal.flush_dns_cache(execute=execute)
            actions.append(act_flush)

        elif failure_type in ["L3_ROUTING_OR_INTERNET_CUT", "L7_HIGH_LOSS_OR_DEGRADED"]:
            # Action: Soft reset of network stack
            reset_logs = self.hal.reset_network_stack(execute=execute)
            actions.extend(reset_logs)

        return actions

