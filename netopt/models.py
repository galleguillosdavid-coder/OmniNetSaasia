"""
Data models and telemetry schemas for the Network Optimization & Healing Engine.
Model-agnostic, serializable and cross-platform.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Any
import time
import uuid


class PlatformType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    DARWIN = "darwin"
    BSD = "bsd"
    UNKNOWN = "unknown"


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    DOWN = "down"


class ActionType(str, Enum):
    DIAGNOSTIC = "diagnostic"
    OPTIMIZATION = "optimization"
    REPAIR = "repair"
    ROLLBACK = "rollback"


@dataclass
class NetworkInterfaceInfo:
    name: str
    mac_address: Optional[str] = None
    ipv4_addresses: List[str] = field(default_factory=list)
    ipv6_addresses: List[str] = field(default_factory=list)
    is_up: bool = False
    is_loopback: bool = False
    mtu: Optional[int] = None
    speed_mbps: Optional[int] = None
    dns_servers: List[str] = field(default_factory=list)
    gateway: Optional[str] = None


@dataclass
class LatencyMetrics:
    target: str
    packets_sent: int
    packets_received: int
    packet_loss_percent: float
    min_ms: float
    avg_ms: float
    max_ms: float
    jitter_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class DnsBenchmarkEntry:
    provider: str
    ip: str
    avg_latency_ms: float
    success_rate_percent: float
    supports_edns: bool = True
    is_anycast: bool = True


@dataclass
class DiagnosticsReport:
    timestamp: float
    platform: PlatformType
    overall_health: HealthState
    default_gateway: Optional[str]
    gateway_reachable: bool
    internet_reachable: bool
    dns_resolving: bool
    dns_benchmarks: List[DnsBenchmarkEntry]
    latency_metrics: Dict[str, LatencyMetrics]
    detected_pmtu: int
    bufferbloat_grade: str  # A+, A, B, C, D, F
    active_interface: Optional[str]
    anomalies: List[str] = field(default_factory=list)


@dataclass
class SnapshotState:
    snapshot_id: str
    timestamp: float
    platform: PlatformType
    dns_settings: Dict[str, List[str]]  # interface -> list of dns
    tcp_parameters: Dict[str, Any]
    mtu_settings: Dict[str, int]
    description: str


@dataclass
class AgentActionLog:
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    action_type: ActionType = ActionType.OPTIMIZATION
    description: str = ""
    command: str = ""
    is_dry_run: bool = True
    success: bool = False
    reverted: bool = False
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0


@dataclass
class OrchestrationPlan:
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    reasoning: str = ""
    target_os: PlatformType = PlatformType.UNKNOWN
    diagnostics_before: Optional[DiagnosticsReport] = None
    planned_actions: List[AgentActionLog] = field(default_factory=list)
    requires_elevation: bool = True
    rollback_snapshot_id: Optional[str] = None
    status: str = "pending"  # pending, executed, verified, reverted, failed

