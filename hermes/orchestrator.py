"""
Hermes AI Multi-Agent Session Spawner & Subagent Orchestrator.
Spawns isolated subagents with independent context windows and models to execute parallel workstreams.
"""

from __future__ import annotations
import time
import uuid
import concurrent.futures
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .harness import HermesAgentHarness, HermesHarnessConfig, HarnessTurnResult
from netopt.ecosystem_subagents import get_ecosystem_orchestrator


@dataclass
class SubagentSession:
    session_id: str
    role: str
    task_prompt: str
    status: str = "initialized"  # 'initialized', 'running', 'completed', 'failed'
    result: Optional[HarnessTurnResult] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    duration_ms: float = 0.0


class HermesOrchestrator:
    """
    Coordinator agent that delegates tasks by spinning up isolated subagents
    with dedicated toolsets and independent execution contexts.
    """

    def __init__(self, default_config: Optional[HermesHarnessConfig] = None):
        self.default_config = default_config or HermesHarnessConfig()
        self.active_sessions: Dict[str, SubagentSession] = {}
        self.ecosystem = get_ecosystem_orchestrator()

    def spawn_session(
        self,
        role: str,
        task_prompt: str,
        tools: Optional[List[str]] = None,
        model: Optional[str] = None
    ) -> SubagentSession:
        """
        Spawns an isolated subagent session with its own harness and context window.
        """
        session_id = f"subagent-{uuid.uuid4().hex[:8]}"
        session = SubagentSession(
            session_id=session_id,
            role=role,
            task_prompt=task_prompt,
            status="running"
        )
        self.active_sessions[session_id] = session

        cfg = HermesHarnessConfig(
            provider=self.default_config.provider,
            model=model or self.default_config.model
        )
        harness = HermesAgentHarness(config=cfg)

        t0 = time.perf_counter()
        # Execute turn within subagent context
        turn_res = harness.run_turn(
            prompt=task_prompt,
            system_prompt=f"Eres un subagente especializado de Hermes en el rol: '{role}'. Tu misión es completar la tarea con precisión quirúrgica."
        )

        session.completed_at = time.time()
        session.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
        session.result = turn_res
        session.status = "completed" if turn_res.success else "failed"

        return session

    def delegate_parallel(self, tasks: List[Dict[str, str]], max_workers: int = 4) -> List[SubagentSession]:
        """
        Executes multiple subagent tasks in parallel across worker threads.
        tasks format: [{"role": "...", "prompt": "..."}]
        """
        sessions: List[SubagentSession] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.spawn_session, t["role"], t["prompt"])
                for t in tasks
            ]
            for f in concurrent.futures.as_completed(futures):
                try:
                    s = f.result()
                    sessions.append(s)
                except Exception as e:
                    failed_session = SubagentSession(
                        session_id=f"failed-{uuid.uuid4().hex[:6]}",
                        role="ErrorSession",
                        task_prompt="Execution failed",
                        status="failed",
                        result=HarnessTurnResult(content="", success=False, error=str(e))
                    )
                    sessions.append(failed_session)

        return sessions

    def synthesize_results(self, sessions: List[SubagentSession]) -> Dict[str, Any]:
        """Synthesizes parallel subagent results into a coherent multi-agent executive brief."""
        total = len(sessions)
        succeeded = sum(1 for s in sessions if s.status == "completed")
        summaries = [f"[{s.role}]: {s.result.content if s.result else 'Sin salida'}" for s in sessions]

        return {
            "total_subagents_spawned": total,
            "successful_subagents": succeeded,
            "all_succeeded": total > 0 and succeeded == total,
            "synthesized_summary": " | ".join(summaries),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "role": s.role,
                    "status": s.status,
                    "duration_ms": s.duration_ms
                }
                for s in sessions
            ]
        }

