"""
FastAPI application for OmniNet AI Agent Pro.
Adopted according to the mature library mandate (docs/Auditorias/3.md §245-285).
Provides fully typed, high-performance REST API with automatic OpenAPI documentation
and strict Pydantic v2 schema validation.
"""

from __future__ import annotations
import os
import json
import time
import secrets
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    HealthResponse,
    ChatRequest,
    OptimizeRequest,
    SubagentRequest,
    RollbackRequest,
    RepairRequest,
    SentinelToggleRequest,
    LicenseActivationRequest,
    TelemetryReport,
    DeviceIdentity
)
from .hal import get_hal, detect_platform
from .diagnostics import (
    run_full_diagnostics,
    benchmark_all_resolvers,
    measure_bandwidth_speed,
    inspect_active_sockets,
    discover_path_mtu,
    audit_arp_lan,
    inspect_wifi_and_nic
)
from .optimizer import NetworkOptimizer
from .repair import NetworkRepairEngine
from .rollback import RollbackManager, SNAPSHOT_DIR
from .auto_trigger import get_sentinel
from .autonomous_scheduler import get_task_scheduler
from .device_maintenance import DeviceMaintenanceEngine
from .licensing import get_license_manager
from .llm_gateway import LLMGateway, load_llm_config, save_llm_config
from .ecosystem_subagents import get_ecosystem_orchestrator
from .elevation import is_elevated, elevation_status_str

LOCAL_SESSION_TOKEN = secrets.token_hex(16)
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1 MB


def create_app(dashboard_html_provider=None) -> FastAPI:
    """Creates and configures the FastAPI application."""
    app = FastAPI(
        title="OmniNet AI Agent Pro API",
        version="2.9.6",
        description="Autonomous Cross-Platform Network Optimization & Maintenance Engine"
    )

    # CORS allowlist
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8877", "http://127.0.0.1:8877", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_and_limit_middleware(request: Request, call_next):
        # 1. Payload size protection (OMNI-020)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_PAYLOAD_SIZE:
            return JSONResponse(
                status_code=413,
                content={"error": "Payload Too Large (Máximo 1MB permitido)"}
            )

        # 2. Local loopback / CSRF access control (OMNI-003)
        client_ip = request.client.host if request.client else "127.0.0.1"
        is_loopback = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")
        req_token = request.headers.get("X-OmniNet-Token")

        if not is_loopback and req_token != LOCAL_SESSION_TOKEN:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"error": "Acceso denegado: API local protegida (solo loopback o token válido)"}
            )

        response = await call_next(request)
        return response

    # ------------------------------------------------------------------
    # Web UI Dashboard
    # ------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    @app.get("/index.html", response_class=HTMLResponse)
    def get_dashboard():
        if dashboard_html_provider:
            return HTMLResponse(content=dashboard_html_provider(), status_code=200)
        return HTMLResponse(content="<h1>OmniNet AI Agent Pro</h1>", status_code=200)

    # ------------------------------------------------------------------
    # System & Health
    # ------------------------------------------------------------------
    @app.get("/health", response_model=HealthResponse)
    def health_check():
        return HealthResponse(
            status="online",
            version="2.9.6",
            service="OmniNet AI Agent Pro"
        )

    @app.get("/api/status")
    def get_system_status():
        try:
            elevated = is_elevated()
            elev_str = elevation_status_str()
        except Exception:
            elevated = False
            elev_str = "unknown"
        sentinel = get_sentinel()
        return {
            "version": "2.9.6",
            "platform": detect_platform().value,
            "admin_elevated": elevated,
            "elevation_status": elev_str,
            "sentinel_active": sentinel.running,
            "port": 8877,
        }

    # ------------------------------------------------------------------
    # Diagnostics & Telemetry
    # ------------------------------------------------------------------
    @app.get("/api/diagnose")
    def get_diagnostics():
        diag = run_full_diagnostics()
        return {
            "timestamp": diag.timestamp,
            "platform": diag.platform.value,
            "overall_health": diag.overall_health.value,
            "gateway_reachable": diag.gateway_reachable,
            "internet_reachable": diag.internet_reachable,
            "dns_resolving": diag.dns_resolving,
            "bufferbloat_grade": diag.bufferbloat_grade,
            "anomalies": diag.anomalies,
            "latency_metrics": {k: vars(v) for k, v in diag.latency_metrics.items()},
            "dns_benchmarks": [vars(b) for b in diag.dns_benchmarks]
        }

    @app.get("/api/bench-dns")
    def bench_dns():
        bench = benchmark_all_resolvers()
        return {"benchmarks": [vars(b) for b in bench]}

    @app.get("/api/speedtest")
    def speedtest():
        return measure_bandwidth_speed()

    @app.get("/api/sockets")
    def get_active_sockets():
        return inspect_active_sockets()

    @app.get("/api/wifi")
    def get_wifi_inspection():
        return inspect_wifi_and_nic()

    @app.get("/api/pmtu")
    def get_pmtu(target: str = "1.1.1.1"):
        return discover_path_mtu(target)

    @app.get("/api/arp")
    def get_arp_audit():
        return audit_arp_lan()

    # ------------------------------------------------------------------
    # Maintenance, Snapshots & Rollback
    # ------------------------------------------------------------------
    @app.get("/api/snapshots")
    def list_snapshots():
        if os.path.exists(SNAPSHOT_DIR):
            snap_files = [
                os.path.join(SNAPSHOT_DIR, f)
                for f in os.listdir(SNAPSHOT_DIR)
                if f.endswith(".json")
            ]
            snap_files.sort(key=lambda p: os.path.getmtime(p))
            snaps = [os.path.basename(p).replace(".json", "") for p in snap_files]
        else:
            snaps = []
        return {"snapshots": snaps}

    @app.get("/api/incidents")
    def list_incidents():
        sentinel = get_sentinel()
        return {"incidents": [asdict(i) for i in sentinel.incidents[::-1]]}

    @app.get("/api/sentinel/status")
    def sentinel_status():
        return get_sentinel().get_status()

    @app.get("/api/tasks")
    def scheduler_tasks():
        return get_task_scheduler().get_status()

    @app.get("/api/device/diagnose")
    def device_diagnose():
        return DeviceMaintenanceEngine().diagnose_all_device_faults()

    @app.get("/api/device/catalog")
    def device_catalog(category: str = "all"):
        return DeviceMaintenanceEngine().get_os_command_catalog(category)

    @app.get("/api/subagents")
    def subagents_status():
        return get_ecosystem_orchestrator().get_all_subagents_status()

    @app.get("/api/license")
    def license_status():
        return get_license_manager().get_status()

    @app.get("/api/hermes/insights")
    def hermes_insights():
        from hermes.cognitive_loop import HermesCognitiveLoop
        return HermesCognitiveLoop().meta_cognitive_insights()

    @app.get("/api/llm/config")
    def llm_config():
        cfg = load_llm_config()
        safe_cfg = {k: v for k, v in cfg.items() if k != "api_key"}
        safe_cfg["api_key_configured"] = bool(cfg.get("api_key"))
        if cfg.get("api_key"):
            safe_cfg["api_key_masked"] = cfg["api_key"][:4] + "..." + cfg["api_key"][-3:]
        return safe_cfg

    # ------------------------------------------------------------------
    # POST Mutating & Action Endpoints (Validated by Pydantic)
    # ------------------------------------------------------------------
    @app.post("/api/optimize")
    def execute_optimize(req: OptimizeRequest):
        hal = get_hal(dry_run=not req.execute)
        optimizer = NetworkOptimizer(hal)
        plan = optimizer.generate_plan()
        success, logs = optimizer.execute_plan(plan, execute=req.execute)
        return {
            "plan_id": plan.plan_id,
            "status": plan.status,
            "applied": req.execute,
            "success": success,
            "logs": logs
        }

    @app.post("/api/repair")
    def execute_repair(req: RepairRequest):
        hal = get_hal(dry_run=not req.execute)
        repair = NetworkRepairEngine(hal)
        failure_type, triage_logs = repair.diagnose_and_triage()
        actions = repair.execute_triage_repair(failure_type, execute=req.execute)
        return {
            "failure_type": failure_type,
            "triage_logs": triage_logs,
            "applied": req.execute,
            "actions": [vars(a) for a in actions]
        }

    @app.post("/api/rollback")
    def execute_rollback(req: RollbackRequest):
        hal = get_hal(dry_run=not req.execute)
        mgr = RollbackManager(hal)
        logs = mgr.rollback(req.snapshot_id, execute=req.execute)
        ok = bool(logs) and not any(str(l).startswith("ERROR:") for l in logs)
        return {"snapshot_id": req.snapshot_id, "applied": req.execute and ok, "success": ok, "logs": logs}

    @app.post("/api/chat")
    def chat_assistant(req: ChatRequest):
        gateway = LLMGateway()
        res = gateway.chat(
            req.message,
            history=req.history or [],
            language_mode=req.language_mode or "technical"
        )
        return res

    @app.post("/api/llm/config")
    def update_llm_settings(payload: Dict[str, Any]):
        gateway = LLMGateway()
        gateway.update_config(payload)
        safe_cfg = {k: v for k, v in gateway.config.items() if k != "api_key"}
        safe_cfg["api_key_configured"] = bool(gateway.config.get("api_key"))
        if gateway.config.get("api_key"):
            safe_cfg["api_key_masked"] = gateway.config["api_key"][:4] + "..." + gateway.config["api_key"][-3:]
        return {"status": "saved", "config": safe_cfg}

    @app.post("/api/sentinel/toggle")
    def toggle_sentinel(req: SentinelToggleRequest):
        sentinel = get_sentinel()
        requested_enabled = req.enabled if req.enabled is not None else not sentinel.enabled
        sentinel.enabled = bool(requested_enabled)
        if sentinel.enabled:
            sentinel.start()
        else:
            sentinel.stop()
        return sentinel.get_status()

    @app.post("/api/sentinel/trigger")
    def trigger_sentinel():
        sentinel = get_sentinel()
        report = sentinel.check_health_and_auto_heal()
        return {
            "triggered": True,
            "had_incident": report is not None,
            "report": asdict(report) if report else None,
            "status": sentinel.get_status()
        }

    @app.post("/api/tasks/trigger")
    def trigger_tasks(payload: Dict[str, Any] = None):
        execute = bool((payload or {}).get("execute", False))
        sched = get_task_scheduler()
        return sched.discover_and_schedule_cycle(execute=execute)

    @app.post("/api/device/maintain")
    def run_device_maintenance(payload: Dict[str, Any] = None):
        execute = bool((payload or {}).get("execute", False))
        hal = get_hal(dry_run=not execute)
        maint = DeviceMaintenanceEngine(hal)
        return maint.run_full_device_maintenance(execute=execute)

    @app.post("/api/subagents/run")
    def run_subagent(req: SubagentRequest):
        orch = get_ecosystem_orchestrator()
        return orch.execute_subagent_by_id(req.id, execute=req.execute)

    @app.post("/api/license/activate")
    def activate_license(req: LicenseActivationRequest):
        return get_license_manager().activate_license(req.license_key, email=req.email or "")

    return app
