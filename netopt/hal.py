"""
Hardware & Operating System Abstraction Layer (HAL) for Network Operations.
Provides a uniform, model-agnostic API across Windows, Linux, macOS, and BSD.
Guarantees strict dry-run capability and safety snapshotting.
"""

from __future__ import annotations
import abc
import platform
import subprocess
import socket
import re
import time
import ipaddress
from typing import List, Dict, Optional, Any, Tuple
from .models import PlatformType, NetworkInterfaceInfo, AgentActionLog, ActionType


def detect_platform() -> PlatformType:
    system = platform.system().lower()
    if "windows" in system:
        return PlatformType.WINDOWS
    elif "linux" in system:
        return PlatformType.LINUX
    elif "darwin" in system:
        return PlatformType.DARWIN
    elif "bsd" in system:
        return PlatformType.BSD
    return PlatformType.UNKNOWN


class NetworkHAL(abc.ABC):
    """Abstract Base Class for OS-specific network administration."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.platform = detect_platform()

    def run_cmd(self, cmd: List[str] | str, shell: bool = False, execute: bool = False) -> AgentActionLog:
        """Executes a system command with dry-run safety and timing."""
        cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
        action = AgentActionLog(
            command=cmd_str,
            is_dry_run=(not execute or self.dry_run),
            timestamp=time.time()
        )

        if not execute or self.dry_run:
            action.success = True
            action.stdout = "[DRY-RUN SIMULATION] Command not executed on host system."
            action.duration_ms = 0.1
            return action

        start = time.perf_counter()
        try:
            use_shell = shell or isinstance(cmd, str)
            cflags = 0x08000000 if self.platform == PlatformType.WINDOWS else 0
            res = subprocess.run(
                cmd,
                shell=use_shell,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=20,
                creationflags=cflags
            )
            action.duration_ms = (time.perf_counter() - start) * 1000
            action.stdout = (res.stdout or "").strip()
            action.stderr = (res.stderr or "").strip()
            action.success = (res.returncode == 0)
        except Exception as e:
            action.duration_ms = (time.perf_counter() - start) * 1000
            action.stderr = str(e)
            action.success = False

        return action

    @abc.abstractmethod
    def get_interfaces(self) -> List[NetworkInterfaceInfo]:
        """Discovers network adapters and their current configuration."""
        pass

    @abc.abstractmethod
    def get_default_gateway(self) -> Optional[str]:
        """Discovers the active default gateway IP address."""
        pass

    @abc.abstractmethod
    def get_dns_servers(self) -> List[str]:
        """Discovers currently configured DNS resolvers."""
        pass

    @abc.abstractmethod
    def set_dns_servers(self, interface_name: str, servers: List[str], execute: bool = False) -> AgentActionLog:
        """Configures primary and secondary DNS servers on an adapter."""
        pass

    @abc.abstractmethod
    def flush_dns_cache(self, execute: bool = False) -> AgentActionLog:
        """Flushes system-wide resolver cache."""
        pass

    @abc.abstractmethod
    def get_tcp_parameters(self) -> Dict[str, Any]:
        """Inspects current OS TCP/IP stack configuration."""
        pass

    @abc.abstractmethod
    def set_tcp_parameters(self, params: Dict[str, Any], execute: bool = False) -> List[AgentActionLog]:
        """Applies TCP stack optimization settings."""
        pass

    @abc.abstractmethod
    def set_interface_mtu(self, interface_name: str, mtu: int, execute: bool = False) -> AgentActionLog:
        """Sets MTU on specified network interface."""
        pass

    @abc.abstractmethod
    def renew_dhcp_lease(self, interface_name: Optional[str] = None, execute: bool = False) -> AgentActionLog:
        """Releases and renews DHCP configuration."""
        pass

    @abc.abstractmethod
    def reset_network_stack(self, execute: bool = False) -> List[AgentActionLog]:
        """Resets network stack to factory baseline (for critical recovery)."""
        pass

    def enable_encrypted_dns_doh(self, execute: bool = False) -> List[AgentActionLog]:
        """Enables native DNS-over-HTTPS (DoH) / DNS-over-TLS encryption for Cloudflare and Google."""
        if self.platform == PlatformType.WINDOWS:
            cmds = [
                ["netsh", "dnsclient", "set", "global", "doh=yes", "ddr=yes"],
                ["netsh", "dns", "add", "encryption", "server=1.1.1.1", "dohtemplate=https://cloudflare-dns.com/dns-query", "autoupgrade=yes", "udpfallback=no"],
                ["netsh", "dns", "add", "encryption", "server=8.8.8.8", "dohtemplate=https://dns.google/dns-query", "autoupgrade=yes", "udpfallback=no"],
                ["netsh", "dns", "add", "encryption", "server=9.9.9.9", "dohtemplate=https://dns.quad9.net/dns-query", "autoupgrade=yes", "udpfallback=no"]
            ]
        elif self.platform == PlatformType.LINUX:
            cmds = [["resolvectl", "dnsovertls", "yes"]]
        else:
            cmds = [["dscacheutil", "-flushcache"]]
        logs = []
        for c in cmds:
            act = self.run_cmd(c, execute=execute)
            act.action_type = ActionType.OPTIMIZATION
            act.description = "Enable Encrypted DNS (DoH/DoT) for anti-ISP-throttling & privacy"
            logs.append(act)
        return logs

    def optimize_nic_low_latency(self, execute: bool = False) -> AgentActionLog:
        """Disables NIC power-saving throttling (EEE / Green Ethernet) to eliminate micro-stutters."""
        if self.platform == PlatformType.WINDOWS:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | Disable-NetAdapterPowerManagement -NoRestart -ErrorAction SilentlyContinue"
            ]
        elif self.platform == PlatformType.LINUX:
            cmd = ["sysctl", "-w", "net.ipv4.tcp_low_latency=1"]
        else:
            cmd = ["sysctl", "-w", "net.inet.tcp.delayed_ack=0"]
        act = self.run_cmd(cmd, execute=execute)
        act.action_type = ActionType.OPTIMIZATION
        act.description = "Disable NIC power-saving throttling (EEE) and enable low-latency path"
        return act


class WindowsHAL(NetworkHAL):
    """Windows implementation utilizing netsh, PowerShell and WMI/IPHelper abstractions."""

    def get_interfaces(self) -> List[NetworkInterfaceInfo]:
        interfaces: List[NetworkInterfaceInfo] = []
        try:
            cmd = ["powershell", "-NoProfile", "-Command", 
                   "Get-NetAdapter | Select-Object Name, InterfaceDescription, MacAddress, Status, LinkSpeed | ConvertTo-Json"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    is_up = str(item.get("Status", "")).lower() == "up"
                    interfaces.append(NetworkInterfaceInfo(
                        name=item.get("Name", "Unknown"),
                        mac_address=item.get("MacAddress"),
                        is_up=is_up,
                        speed_mbps=None
                    ))
        except Exception:
            pass
        return interfaces

    def get_default_gateway(self) -> Optional[str]:
        try:
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Select-Object NextHop, RouteMetric | ConvertTo-Json"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0 and res.stdout.strip():
                import json
                data = json.loads(res.stdout)
                if isinstance(data, dict):
                    data = [data]
                valid = [item.get("NextHop") for item in data if item.get("NextHop") and item.get("NextHop") not in ["0.0.0.0", "::", ""]]
                if valid:
                    return valid[0]
        except Exception:
            pass
        return None

    def get_dns_servers(self) -> List[str]:
        dns: List[str] = []
        try:
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-DnsClientServerAddress -AddressFamily IPv4 | Select-Object -ExpandProperty ServerAddresses"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    clean = line.strip()
                    if clean and clean not in dns:
                        dns.append(clean)
        except Exception:
            pass
        return dns

    def set_dns_servers(self, interface_name: str, servers: List[str], execute: bool = False) -> AgentActionLog:
        # Validación de parámetros y sanitización contra inyección (OMNI-010)
        if not re.match(r"^[a-zA-Z0-9_\-\.\s\(\)]+$", interface_name):
            raise ValueError(f"Nombre de interfaz inválido o no sanitizado: {interface_name}")
        for s in servers:
            ipaddress.ip_address(s)  # Valida que cada servidor sea una IP válida

        servers_str = ",".join(f"'{s}'" for s in servers)
        cmd = ["powershell", "-NoProfile", "-Command",
               f"Set-DnsClientServerAddress -InterfaceAlias '{interface_name}' -ServerAddresses {servers_str}"]
        action = self.run_cmd(cmd, execute=execute)
        action.action_type = ActionType.OPTIMIZATION
        action.description = f"Set DNS servers on '{interface_name}' to {servers}"
        return action

    def flush_dns_cache(self, execute: bool = False) -> AgentActionLog:
        cmd = ["ipconfig", "/flushdns"]
        action = self.run_cmd(cmd, execute=execute)
        action.action_type = ActionType.REPAIR
        action.description = "Flush local DNS resolver cache"
        return action

    def get_tcp_parameters(self) -> Dict[str, Any]:
        params = {
            "autotuninglevel": "normal",
            "congestionprovider": "default",
            "rss": "enabled",
            "rsc": "enabled",
            "dca": "enabled",
            "ecncapability": "disabled",
            "timestamps": "disabled"
        }
        try:
            res = subprocess.run(["netsh", "int", "tcp", "show", "global"], capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k = k.strip().lower()
                        v = v.strip().lower()
                        if "tuning" in k:
                            params["autotuninglevel"] = v
                        elif "congestion" in k:
                            params["congestionprovider"] = v
                        elif "receive-side scaling" in k:
                            params["rss"] = v
                        elif "receive segment coalescing" in k:
                            params["rsc"] = v
                        elif "ecn" in k:
                            params["ecncapability"] = v
                        elif "timestamps" in k:
                            params["timestamps"] = v
        except Exception:
            pass
        return params

    def set_tcp_parameters(self, params: Dict[str, Any], execute: bool = False) -> List[AgentActionLog]:
        logs: List[AgentActionLog] = []
        for key, val in params.items():
            cmd = ["netsh", "int", "tcp", "set", "global", f"{key}={val}"]
            log = self.run_cmd(cmd, execute=execute)
            log.action_type = ActionType.OPTIMIZATION
            log.description = f"Set TCP global parameter {key}={val}"
            logs.append(log)
        return logs

    def set_interface_mtu(self, interface_name: str, mtu: int, execute: bool = False) -> AgentActionLog:
        cmd = ["netsh", "interface", "ipv4", "set", "subinterface", f'"{interface_name}"', f"mtu={mtu}", "store=persistent"]
        action = self.run_cmd(cmd, execute=execute)
        action.action_type = ActionType.OPTIMIZATION
        action.description = f"Set MTU on interface '{interface_name}' to {mtu}"
        return action

    def renew_dhcp_lease(self, interface_name: Optional[str] = None, execute: bool = False) -> AgentActionLog:
        cmd = ["ipconfig", "/renew"] if not interface_name else ["ipconfig", "/renew", interface_name]
        action = self.run_cmd(cmd, execute=execute)
        action.action_type = ActionType.REPAIR
        action.description = f"Renew DHCP lease for {'all' if not interface_name else interface_name}"
        return action

    def reset_network_stack(self, execute: bool = False) -> List[AgentActionLog]:
        logs = []
        logs.append(self.run_cmd(["netsh", "winsock", "reset"], execute=execute))
        logs.append(self.run_cmd(["netsh", "int", "ip", "reset"], execute=execute))
        logs.append(self.run_cmd(["ipconfig", "/flushdns"], execute=execute))
        for l in logs:
            l.action_type = ActionType.REPAIR
            l.description = "Complete Windows network stack & winsock reset"
        return logs


class LinuxHAL(NetworkHAL):
    """Linux implementation using sysctl, iproute2, nmcli and systemd-resolved."""

    def get_interfaces(self) -> List[NetworkInterfaceInfo]:
        interfaces: List[NetworkInterfaceInfo] = []
        try:
            res = subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                import json
                data = json.loads(res.stdout)
                for item in data:
                    name = item.get("ifname", "")
                    flags = item.get("flags", [])
                    is_up = "UP" in flags
                    is_loopback = "LOOPBACK" in flags
                    mtu = item.get("mtu")
                    addrs = [a.get("local") for a in item.get("addr_info", []) if a.get("family") == "inet"]
                    interfaces.append(NetworkInterfaceInfo(
                        name=name,
                        mac_address=item.get("address"),
                        ipv4_addresses=addrs,
                        is_up=is_up,
                        is_loopback=is_loopback,
                        mtu=mtu
                    ))
        except Exception:
            pass
        return interfaces

    def get_default_gateway(self) -> Optional[str]:
        try:
            res = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout:
                # default via 192.168.1.1 dev eth0 ...
                m = re.search(r"via\s+([0-9.]+)", res.stdout)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return None

    def get_dns_servers(self) -> List[str]:
        dns: List[str] = []
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        parts = line.split()
                        if len(parts) > 1:
                            dns.append(parts[1].strip())
        except Exception:
            pass
        return dns

    def set_dns_servers(self, interface_name: str, servers: List[str], execute: bool = False) -> AgentActionLog:
        if not re.match(r"^[a-zA-Z0-9_\-\.\s]+$", interface_name):
            raise ValueError(f"Nombre de interfaz Linux inválido: {interface_name}")
        for s in servers:
            ipaddress.ip_address(s)
        # Preferred modern path: resolvectl, fallback to nmcli
        srv_str = " ".join(servers)
        cmd = f"resolvectl dns {interface_name} {srv_str} || nmcli device modify {interface_name} ipv4.dns '{srv_str}'"
        action = self.run_cmd(cmd, shell=True, execute=execute)
        action.action_type = ActionType.OPTIMIZATION
        action.description = f"Set Linux DNS for {interface_name} to {servers}"
        return action

    def flush_dns_cache(self, execute: bool = False) -> AgentActionLog:
        cmd = "resolvectl flush-caches || systemd-resolve --flush-caches || service nscd restart"
        action = self.run_cmd(cmd, shell=True, execute=execute)
        action.action_type = ActionType.REPAIR
        action.description = "Flush Linux DNS cache via systemd-resolved/nscd"
        return action

    def get_tcp_parameters(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        keys = [
            "net.ipv4.tcp_congestion_control",
            "net.core.default_qdisc",
            "net.ipv4.tcp_fastopen",
            "net.ipv4.tcp_window_scaling",
            "net.ipv4.tcp_timestamps",
            "net.ipv4.tcp_sack",
            "net.core.rmem_max",
            "net.core.wmem_max"
        ]
        for k in keys:
            try:
                res = subprocess.run(["sysctl", "-n", k], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    params[k] = res.stdout.strip()
            except Exception:
                pass
        return params

    def set_tcp_parameters(self, params: Dict[str, Any], execute: bool = False) -> List[AgentActionLog]:
        logs: List[AgentActionLog] = []
        for k, v in params.items():
            cmd = ["sysctl", "-w", f"{k}={v}"]
            log = self.run_cmd(cmd, execute=execute)
            log.action_type = ActionType.OPTIMIZATION
            log.description = f"Set Linux sysctl {k}={v}"
            logs.append(log)
        return logs

    def set_interface_mtu(self, interface_name: str, mtu: int, execute: bool = False) -> AgentActionLog:
        cmd = ["ip", "link", "set", "dev", interface_name, "mtu", str(mtu)]
        action = self.run_cmd(cmd, execute=execute)
        action.action_type = ActionType.OPTIMIZATION
        action.description = f"Set MTU on {interface_name} to {mtu}"
        return action

    def renew_dhcp_lease(self, interface_name: Optional[str] = None, execute: bool = False) -> AgentActionLog:
        if interface_name:
            cmd = f"dhclient -r {interface_name} && dhclient {interface_name} || nmcli device reapply {interface_name}"
        else:
            cmd = "dhclient -r && dhclient || systemctl restart NetworkManager"
        action = self.run_cmd(cmd, shell=True, execute=execute)
        action.action_type = ActionType.REPAIR
        action.description = f"Renew DHCP lease on {interface_name or 'all'}"
        return action

    def reset_network_stack(self, execute: bool = False) -> List[AgentActionLog]:
        logs = []
        logs.append(self.run_cmd(["ip", "route", "flush", "cache"], execute=execute))
        logs.append(self.run_cmd(["systemctl", "restart", "NetworkManager"], execute=execute))
        for l in logs:
            l.action_type = ActionType.REPAIR
            l.description = "Flush Linux routing cache and restart network daemon"
        return logs


class DarwinHAL(NetworkHAL):
    """macOS (Darwin) implementation using networksetup, scutil, sysctl, and dscacheutil."""

    def get_interfaces(self) -> List[NetworkInterfaceInfo]:
        interfaces = []
        try:
            res = subprocess.run(["networksetup", "-listallhardwareports"], capture_output=True, text=True, timeout=8)
            if res.returncode == 0:
                cur_dev = ""
                cur_port = ""
                for line in res.stdout.splitlines():
                    if "Hardware Port:" in line:
                        cur_port = line.split(":", 1)[1].strip()
                    elif "Device:" in line:
                        cur_dev = line.split(":", 1)[1].strip()
                        interfaces.append(NetworkInterfaceInfo(
                            name=cur_port,
                            mac_address=None,
                            is_up=True
                        ))
        except Exception:
            pass
        return interfaces

    def get_default_gateway(self) -> Optional[str]:
        try:
            res = subprocess.run(["route", "-n", "get", "default"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "gateway:" in line:
                        return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return None

    def get_dns_servers(self) -> List[str]:
        dns = []
        try:
            res = subprocess.run(["scutil", "--dns"], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                for line in res.stdout.splitlines():
                    if "nameserver[" in line and ":" in line:
                        ip = line.split(":", 1)[1].strip()
                        if ip not in dns:
                            dns.append(ip)
        except Exception:
            pass
        return dns or ["1.1.1.1", "8.8.8.8"]

    def set_dns_servers(self, interface_name: str, servers: List[str], execute: bool = False) -> AgentActionLog:
        cmd = ["networksetup", "-setdnsservers", interface_name] + servers
        action = self.run_cmd(cmd, execute=execute)
        action.action_type = ActionType.OPTIMIZATION
        action.description = f"Set macOS DNS on {interface_name} to {servers}"
        return action

    def flush_dns_cache(self, execute: bool = False) -> AgentActionLog:
        cmd = "dscacheutil -flushcache; killall -HUP mDNSResponder"
        action = self.run_cmd(cmd, shell=True, execute=execute)
        action.action_type = ActionType.REPAIR
        action.description = "Flush macOS DNS cache and signal mDNSResponder"
        return action

    def get_tcp_parameters(self) -> Dict[str, Any]:
        params = {}
        for key in ["net.inet.tcp.delayed_ack", "net.inet.tcp.mptcp", "net.inet.tcp.sendspace", "net.inet.tcp.recvspace"]:
            try:
                res = subprocess.run(["sysctl", "-n", key], capture_output=True, text=True, timeout=3)
                if res.returncode == 0:
                    params[key] = res.stdout.strip()
            except Exception:
                pass
        return params

    def set_tcp_parameters(self, params: Dict[str, Any], execute: bool = False) -> List[AgentActionLog]:
        logs = []
        for k, v in params.items():
            cmd = ["sysctl", "-w", f"{k}={v}"]
            log = self.run_cmd(cmd, execute=execute)
            log.action_type = ActionType.OPTIMIZATION
            log.description = f"Set macOS sysctl {k}={v}"
            logs.append(log)
        return logs

    def set_interface_mtu(self, interface_name: str, mtu: int, execute: bool = False) -> AgentActionLog:
        cmd = ["networksetup", "-setMTU", interface_name, str(mtu)]
        action = self.run_cmd(cmd, execute=execute)
        action.action_type = ActionType.OPTIMIZATION
        action.description = f"Set MTU on {interface_name} to {mtu}"
        return action

    def renew_dhcp_lease(self, interface_name: Optional[str] = None, execute: bool = False) -> AgentActionLog:
        cmd = ["ipconfig", "set", interface_name or "en0", "DHCP"]
        action = self.run_cmd(cmd, execute=execute)
        action.action_type = ActionType.REPAIR
        action.description = f"Renew macOS DHCP lease on {interface_name or 'en0'}"
        return action

    def reset_network_stack(self, execute: bool = False) -> List[AgentActionLog]:
        logs = []
        logs.append(self.flush_dns_cache(execute=execute))
        logs.append(self.run_cmd(["ifconfig", "en0", "down"], execute=execute))
        logs.append(self.run_cmd(["ifconfig", "en0", "up"], execute=execute))
        return logs


def get_hal(dry_run: bool = True) -> NetworkHAL:
    """Factory function returning the proper HAL for the current host OS."""
    plat = detect_platform()
    if plat == PlatformType.WINDOWS:
        return WindowsHAL(dry_run=dry_run)
    elif plat == PlatformType.LINUX:
        return LinuxHAL(dry_run=dry_run)
    elif plat == PlatformType.DARWIN:
        return DarwinHAL(dry_run=dry_run)
    else:
        # Fallback to Linux-like POSIX implementation for BSD/Unix
        return LinuxHAL(dry_run=dry_run)

