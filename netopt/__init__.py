"""
OmniNet - Autonomous Cross-Platform Network Optimization, Self-Evolution & Healing Engine.
"""

__version__ = "2.1.0"

from .models import (
    PlatformType,
    HealthState,
    DiagnosticsReport,
    OrchestrationPlan,
    SnapshotState
)
from .hal import get_hal, detect_platform
from .elevation import is_elevated, ensure_elevated, elevation_status_str
from .diagnostics import run_full_diagnostics, benchmark_all_resolvers
from .optimizer import NetworkOptimizer
from .repair import NetworkRepairEngine
from .rollback import RollbackManager
from .persistence import NetworkDaemon
from .auto_trigger import get_sentinel, AutoSentinel
from .autonomous_scheduler import get_task_scheduler, AutonomousTaskScheduler

__all__ = [
    "PlatformType",
    "HealthState",
    "DiagnosticsReport",
    "OrchestrationPlan",
    "SnapshotState",
    "get_hal",
    "detect_platform",
    "is_elevated",
    "ensure_elevated",
    "elevation_status_str",
    "run_full_diagnostics",
    "benchmark_all_resolvers",
    "NetworkOptimizer",
    "NetworkRepairEngine",
    "RollbackManager",
    "NetworkDaemon",
    "get_sentinel",
    "AutoSentinel",
    "get_task_scheduler",
    "AutonomousTaskScheduler"
]
