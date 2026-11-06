"""
Hermes AI Agent Harness & Autonomous Orchestrator for OmniNet.
Provides persistent cognitive loops, dynamic tool execution, multi-agent session spawning,
and closed-loop self-improvement adapted from Hermes Agent architecture.
"""

from __future__ import annotations
from .harness import HermesAgentHarness, HermesHarnessConfig, ToolDefinition
from .orchestrator import HermesOrchestrator, SubagentSession
from .self_improvement import HermesSelfImprovementEngine, HermesMemory, EvolutionReport

__all__ = [
    "HermesAgentHarness",
    "HermesHarnessConfig",
    "ToolDefinition",
    "HermesOrchestrator",
    "SubagentSession",
    "HermesSelfImprovementEngine",
    "HermesMemory",
    "EvolutionReport",
    "get_hermes_engine"
]

_engine_instance = None


def get_hermes_engine() -> HermesSelfImprovementEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = HermesSelfImprovementEngine()
    return _engine_instance

