"""
Hermes AI Multi-Agent Session Spawner & Subagent Orchestrator.
Spawns isolated subagents with independent context windows and models to execute parallel workstreams.
"""

from __future__ import annotations
import re
import time
import uuid
import threading
import concurrent.futures
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .harness import HermesAgentHarness, HermesHarnessConfig, HarnessTurnResult
from netopt.ecosystem_subagents import get_ecosystem_orchestrator

MAX_RETAINED_SESSIONS = 200
MAX_PARALLEL_WORKERS = 16


def _sanitize_error(exc: Exception) -> str:
    """Sanitizes exception text so internal traces or tokens are not leaked."""
    msg = f"{type(exc).__name__}: {exc}"
    msg = re.sub(r"[\r\n\t]+", " ", msg).strip()
    msg = re.sub(r"(?i)(bearer\s+|sk-|token=|key=|secret=)[^\s,;]+", r"\1[REDACTED]", msg)
    return msg[:200]


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
        self._sessions_lock = threading.RLock()
        self.ecosystem = get_ecosystem_orchestrator()

    def _record_session(self, session: SubagentSession) -> None:
        with self._sessions_lock:
            self.active_sessions[session.session_id] = session
            if len(self.active_sessions) > MAX_RETAINED_SESSIONS:
                # H-03: Never evict running sessions; only evict oldest terminal sessions.
                terminal_ids = [
                    sid for sid, sess in self.active_sessions.items()
                    if sess.status != "running" and sid != session.session_id
                ]
                for sid in terminal_ids:
                    if len(self.active_sessions) <= MAX_RETAINED_SESSIONS:
                        break
                    self.active_sessions.pop(sid, None)

    def get_session(self, session_id: str) -> Optional[SubagentSession]:
        """Thread-safe lookup of a recorded subagent session."""
        with self._sessions_lock:
            return self.active_sessions.get(session_id)

    def list_sessions(self, status: Optional[str] = None) -> List[SubagentSession]:
        """Thread-safe snapshot of recorded sessions, optionally filtered by status."""
        with self._sessions_lock:
            items = list(self.active_sessions.values())
        if status is not None:
            return [s for s in items if s.status == status]
        return items

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
        if not isinstance(role, str) or not role.strip():
            raise ValueError("role must be a non-empty string")
        if not isinstance(task_prompt, str) or not task_prompt.strip():
            raise ValueError("task_prompt must be a non-empty string")

        session_id = f"subagent-{uuid.uuid4().hex[:8]}"
        session = SubagentSession(
            session_id=session_id,
            role=role,
            task_prompt=task_prompt,
            status="running"
        )
        self._record_session(session)

        cfg = HermesHarnessConfig(
            provider=self.default_config.provider,
            model=model or self.default_config.model
        )
        harness = HermesAgentHarness(config=cfg)

        t0 = time.perf_counter()
        try:
            turn_res = harness.run_turn(
                prompt=task_prompt,
                system_prompt=f"Eres un subagente especializado de Hermes en el rol: '{role}'. Tu misión es completar la tarea con precisión quirúrgica."
            )
            final_status = "completed" if turn_res.success else "failed"
        except Exception as e:
            turn_res = HarnessTurnResult(content="", success=False, error=_sanitize_error(e))
            final_status = "failed"

        with self._sessions_lock:
            session.status = final_status
            session.completed_at = time.time()
            session.duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            session.result = turn_res

        return session

    def delegate_parallel(self, tasks: List[Dict[str, str]], max_workers: int = 4) -> List[SubagentSession]:
        """
        Executes multiple subagent tasks in parallel across worker threads.
        tasks format: [{"role": "...", "prompt": "..."}]
        """
        if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers <= 0:
            raise ValueError("max_workers must be a positive integer")
        if not isinstance(tasks, (list, tuple)):
            raise ValueError("tasks must be a list or tuple of task dicts")
        if not tasks:
            return []

        validated_tasks: List[Dict[str, str]] = []
        for idx, item in enumerate(tasks):
            if not isinstance(item, dict):
                raise ValueError(f"tasks[{idx}] must be a dict")
            r = item.get("role")
            p = item.get("prompt")
            if not isinstance(r, str) or not r.strip() or not isinstance(p, str) or not p.strip():
                raise ValueError(f"tasks[{idx}] must contain non-empty string 'role' and 'prompt'")
            validated_tasks.append({"role": r, "prompt": p})

        bounded_workers = max(1, min(MAX_PARALLEL_WORKERS, max_workers, len(validated_tasks)))
        sessions: List[SubagentSession] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=bounded_workers) as executor:
            futures = [
                executor.submit(self.spawn_session, t["role"], t["prompt"])
                for t in validated_tasks
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
                        result=HarnessTurnResult(content="", success=False, error=_sanitize_error(e))
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

