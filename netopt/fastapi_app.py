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
import hmac
import secrets
from typing import Dict, Any, List, Optional
from dataclasses import asdict

from fastapi import FastAPI, Request, HTTPException, Depends, Body, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from . import __version__ as OMNINET_VERSION
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
    DeviceIdentity,
    ExecuteFlagRequest,
    LLMConfigUpdateRequest,
    UrlCheckRequest,
    QuarantineIsolateRequest,
    QuarantineRestoreRequest,
    WallpaperToggleRequest,
    AutonomyToggleRequest,
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


def _sanitize_llm_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Returns a copy of LLM config with the API key stripped and safely masked."""
    safe_cfg = {k: v for k, v in cfg.items() if k != "api_key"}
    raw_key = str(cfg.get("api_key") or "")
    safe_cfg["api_key_configured"] = bool(raw_key)
    if raw_key:
        safe_cfg["api_key_masked"] = (
            raw_key[:4] + "..." + raw_key[-3:] if len(raw_key) > 8 else "****"
        )
    return safe_cfg


def create_app(dashboard_html_provider=None) -> FastAPI:
    """Creates and configures the FastAPI application."""
    app = FastAPI(
        title="OmniNet AI Agent Pro API",
        version=OMNINET_VERSION,
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
        if content_length is not None:
            try:
                parsed_length = int(content_length)
            except (ValueError, TypeError):
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Cabecera Content-Length inválida"}
                )
            if parsed_length < 0:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Cabecera Content-Length negativa"}
                )
            if parsed_length > MAX_PAYLOAD_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Payload Too Large (Máximo 1MB permitido)"}
                )
        elif request.method in ("POST", "PUT", "PATCH"):
            raw_body = await request.body()
            if len(raw_body) > MAX_PAYLOAD_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Payload Too Large (Máximo 1MB permitido)"}
                )

        # 2. Local loopback / CSRF access control (OMNI-003)
        client_ip = request.client.host if request.client else "127.0.0.1"
        is_loopback = client_ip in ("127.0.0.1", "::1", "localhost", "testclient")
        req_token = request.headers.get("X-OmniNet-Token") or ""

        if not is_loopback and not hmac.compare_digest(req_token, LOCAL_SESSION_TOKEN):
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
            version=OMNINET_VERSION,
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
            "version": OMNINET_VERSION,
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
        try:
            return discover_path_mtu(target)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

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
                if f.endswith(".json") and os.path.isfile(os.path.join(SNAPSHOT_DIR, f))
            ]
            snap_files.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0.0)
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
        return _sanitize_llm_config(load_llm_config())

    @app.get("/api/metrics/impact")
    def metrics_impact():
        from .telemetry import get_impact_summary
        return get_impact_summary()

    @app.get("/api/mesh/status")
    def mesh_status():
        from .virtual_mesh import VirtualMeshManager
        return VirtualMeshManager().get_status()

    @app.get("/api/quarantine")
    def quarantine_list():
        from .quarantine import QuarantineManager
        return {"items": QuarantineManager().list_items()}

    @app.post("/api/quarantine/isolate")
    def quarantine_isolate(req: QuarantineIsolateRequest):
        from .quarantine import QuarantineManager
        return QuarantineManager().quarantine_file(req.file_path, reason=req.reason, execute=req.execute)

    @app.post("/api/quarantine/restore")
    def quarantine_restore(req: QuarantineRestoreRequest):
        from .quarantine import QuarantineManager
        return QuarantineManager().restore_file(req.item_id, execute=req.execute)

    @app.get("/api/defense/audit")
    def defense_audit():
        from .ai_defense import audit_ai_threats
        return audit_ai_threats()

    @app.post("/api/defense/check-url")
    def defense_check_url(req: UrlCheckRequest):
        from .ai_defense import inspect_url_or_domain
        return inspect_url_or_domain(req.url)

    @app.get("/api/wallpaper/status")
    def wallpaper_status():
        from .matrix_wallpaper import MatrixWallpaperManager
        return MatrixWallpaperManager().status()

    @app.get("/matrix", response_class=HTMLResponse)
    def matrix_fullscreen_page():
        return HTMLResponse(content="""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>OmniNet Matrix Code World 3D</title>
<style>
  html,body{margin:0;padding:0;background:#000;overflow:hidden;height:100%}
  canvas{position:fixed;inset:0;display:block}
</style>
<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"
  }
}
</script>
</head>
<body>
<canvas id="gl3d"></canvas>
<script type="module">
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';

const ch = 'ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const hiddenMsgs = [
  'e^(i*pi)+1=0','E=mc^2','i*hbar*dpsi/dt=H*psi','S=k*ln(W)',
  'sum(1/n^2)=pi^2/6','nabla x E = -dB/dt','phi=1.6180339','lambda=h/p',
  'def zero_netloss(): return True','O(log n)','SHA256::0x7F','RFC9330::L4S',
  'AI::HANDSHAKE[OK]','HERMES->OMNINET::SYNC','AGENT::VERIFY_TRUTH','MESH::TRUST_OK'
];

// Procedural live Matrix digital-rain texture generator for 3D surfaces
function createMatrixRainTexture(w, h, fontSize, speedScale, brightMode = false) {
  const cv = document.createElement('canvas');
  cv.width = w; cv.height = h;
  const g = cv.getContext('2d');
  g.fillStyle = '#000';
  g.fillRect(0, 0, w, h);
  const cols = Math.floor(w / fontSize);
  const drops = Array.from({ length: cols }, () => Math.random() * (h / fontSize));
  const speeds = Array.from({ length: cols }, () => (0.45 + Math.random() * 1.4) * speedScale);
  const colMsg = {};
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;

  function step() {
    g.fillStyle = brightMode ? 'rgba(0, 12, 4, 0.14)' : 'rgba(0, 4, 1, 0.10)';
    g.fillRect(0, 0, w, h);
    g.font = `bold ${fontSize}px monospace`;
    for (let i = 0; i < cols; i++) {
      if (!colMsg[i] && Math.random() > 0.993) {
        colMsg[i] = { text: hiddenMsgs[Math.floor(Math.random() * hiddenMsgs.length)], idx: 0 };
      }
      let t, isMsg = false;
      if (colMsg[i]) {
        t = colMsg[i].text[colMsg[i].idx++]; isMsg = true;
        if (colMsg[i].idx >= colMsg[i].text.length) delete colMsg[i];
      } else {
        t = ch[Math.floor(Math.random() * ch.length)];
      }
      const x = i * fontSize, y = Math.floor(drops[i]) * fontSize;
      if (brightMode) {
        g.fillStyle = isMsg ? '#ecfdf5' : (speeds[i] > 1.2 ? '#bbf7d0' : '#4ade80');
      } else {
        g.fillStyle = isMsg ? '#86efac' : (speeds[i] > 1.25 ? '#4ade80' : '#00e639');
      }
      g.fillText(t, x, y);
      if (y > h && Math.random() > 0.97) {
        drops[i] = 0;
      } else {
        drops[i] += speeds[i];
      }
    }
    tex.needsUpdate = true;
  }
  for (let pre = 0; pre < 35; pre++) step();
  return { tex, step };
}

const glCanvas = document.getElementById('gl3d');
const renderer = new THREE.WebGLRenderer({ canvas: glCanvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x000b03, 0.032);

const camera = new THREE.PerspectiveCamera(54, window.innerWidth / window.innerHeight, 0.1, 120);
camera.position.set(0, 1.55, 6.5);
camera.lookAt(0, 1.45, -18);

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloomPass = new UnrealBloomPass(
  new THREE.Vector2(window.innerWidth, window.innerHeight),
  1.25, 0.55, 0.14
);
composer.addPass(bloomPass);

// Ambient & green corridor lighting
scene.add(new THREE.AmbientLight(0x052e16, 1.2));
const coreLight = new THREE.PointLight(0x22ff66, 6.0, 26);
coreLight.position.set(0, 2.2, -10.5);
scene.add(coreLight);

// Code textures for corridor walls, floor/ceiling, and glowing human figures
const wallCode = createMatrixRainTexture(1024, 512, 13, 0.85, false);
wallCode.tex.repeat.set(3, 1);
const floorCode = createMatrixRainTexture(512, 1024, 12, 1.0, false);
floorCode.tex.repeat.set(1.5, 4);
const figureCode = createMatrixRainTexture(512, 512, 11, 0.9, true);

const wallMat = new THREE.MeshStandardMaterial({
  map: wallCode.tex, emissiveMap: wallCode.tex, emissive: new THREE.Color(0x00ff41),
  emissiveIntensity: 0.95, roughness: 0.45, metalness: 0.25, side: THREE.DoubleSide
});
const floorMat = new THREE.MeshStandardMaterial({
  map: floorCode.tex, emissiveMap: floorCode.tex, emissive: new THREE.Color(0x00ff41),
  emissiveIntensity: 0.85, roughness: 0.18, metalness: 0.65, side: THREE.DoubleSide
});
const figMat = new THREE.MeshStandardMaterial({
  map: figureCode.tex, emissiveMap: figureCode.tex, emissive: new THREE.Color(0x99ffd6),
  emissiveIntensity: 2.45, roughness: 0.15, metalness: 0.2
});

// 1. 3D Matrix Code Corridor (walls, ceiling, floor, and back doorway)
const corridorLen = 28, corridorW = 6.2, corridorH = 4.6, midZ = -4;
const leftWall = new THREE.Mesh(new THREE.PlaneGeometry(corridorLen, corridorH), wallMat);
leftWall.rotation.y = Math.PI / 2; leftWall.position.set(-corridorW / 2, corridorH / 2, midZ);
scene.add(leftWall);

const rightWall = new THREE.Mesh(new THREE.PlaneGeometry(corridorLen, corridorH), wallMat);
rightWall.rotation.y = -Math.PI / 2; rightWall.position.set(corridorW / 2, corridorH / 2, midZ);
scene.add(rightWall);

const floor = new THREE.Mesh(new THREE.PlaneGeometry(corridorW, corridorLen), floorMat);
floor.rotation.x = -Math.PI / 2; floor.position.set(0, 0, midZ);
scene.add(floor);

const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(corridorW, corridorLen), floorMat);
ceiling.rotation.x = Math.PI / 2; ceiling.position.set(0, corridorH, midZ);
scene.add(ceiling);

const backWall = new THREE.Mesh(new THREE.PlaneGeometry(corridorW, corridorH), wallMat);
backWall.position.set(0, corridorH / 2, midZ - corridorLen / 2);
scene.add(backWall);

// 2. Sculpted 3D Human Silhouette(s) made of dense glowing Matrix code
function createCodeHuman(x, z, scale = 1.0) {
  const grp = new THREE.Group();
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.145 * scale, 20, 16), figMat);
  head.position.y = 1.63 * scale; grp.add(head);
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.055 * scale, 0.065 * scale, 0.14 * scale, 12), figMat);
  neck.position.y = 1.46 * scale; grp.add(neck);
  const torso = new THREE.Mesh(new THREE.CylinderGeometry(0.18 * scale, 0.135 * scale, 0.54 * scale, 16), figMat);
  torso.position.y = 1.16 * scale; torso.scale.z = 0.62; grp.add(torso);
  const pelvis = new THREE.Mesh(new THREE.CylinderGeometry(0.145 * scale, 0.165 * scale, 0.22 * scale, 16), figMat);
  pelvis.position.y = 0.80 * scale; pelvis.scale.z = 0.68; grp.add(pelvis);
  [-1, 1].forEach(side => {
    const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.052 * scale, 0.040 * scale, 0.66 * scale, 12), figMat);
    arm.position.set(side * 0.23 * scale, 1.08 * scale, 0);
    arm.rotation.z = side * 0.08; grp.add(arm);
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.072 * scale, 0.050 * scale, 0.78 * scale, 12), figMat);
    leg.position.set(side * 0.085 * scale, 0.39 * scale, 0);
    grp.add(leg);
  });
  grp.position.set(x, 0, z);
  scene.add(grp);
  return grp;
}
createCodeHuman(0.0, -8.8, 1.12);
createCodeHuman(-1.05, -9.6, 1.04);
createCodeHuman(1.05, -9.6, 1.04);
const figureRimLight = new THREE.PointLight(0x88ffcc, 6.0, 14);
figureRimLight.position.set(0, 1.6, -10.8);
scene.add(figureRimLight);

// 3. Foreground/Midground 3D Matrix Code Curtains (floating rain planes)
const rainCurtains = [];
[-5.5, -2.0, 2.5].forEach((cz, idx) => {
  const rc = createMatrixRainTexture(1024, 512, 16, 0.95 + idx * 0.2, false);
  const rMat = new THREE.MeshBasicMaterial({
    map: rc.tex, transparent: true, opacity: 0.22, blending: THREE.AdditiveBlending, depthWrite: false
  });
  const plane = new THREE.Mesh(new THREE.PlaneGeometry(8.5, 5.2), rMat);
  plane.position.set(0, 2.3, cz);
  scene.add(plane);
  rainCurtains.push(rc);
});

function onResize() {
  const w = window.innerWidth, h = window.innerHeight;
  renderer.setSize(w, h);
  composer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
onResize();
window.addEventListener('resize', onResize);

let tick = 0;
function animate() {
  requestAnimationFrame(animate);
  tick++;
  if (tick % 2 === 0) {
    wallCode.step();
    floorCode.step();
    figureCode.step();
    rainCurtains.forEach(rc => rc.step());
  }
  camera.position.x = Math.sin(tick * 0.007) * 0.32;
  camera.position.y = 1.55 + Math.cos(tick * 0.006) * 0.06;
  camera.lookAt(0, 1.35, -14);
  coreLight.intensity = 5.4 + Math.sin(tick * 0.05) * 1.1;
  composer.render();
}
animate();
</script></body></html>""")

    @app.post("/api/wallpaper/matrix")
    def wallpaper_matrix_toggle(req: WallpaperToggleRequest):
        from .matrix_wallpaper import MatrixWallpaperManager
        mgr = MatrixWallpaperManager()
        return mgr.start(execute=req.execute) if req.enabled else mgr.stop(execute=req.execute)

    @app.get("/api/autonomy/status")
    def autonomy_status():
        from .sovereign_dns import get_sovereign_dns
        from .virtual_mesh import evaluate_multipath_failover
        return {
            "sovereign_dns": get_sovereign_dns().status(),
            "multipath": evaluate_multipath_failover(execute=False),
            "sentinel": get_sentinel().get_status(),
        }

    @app.post("/api/autonomy/sovereign-dns")
    def autonomy_sovereign_dns(req: AutonomyToggleRequest):
        from .sovereign_dns import get_sovereign_dns
        dns_srv = get_sovereign_dns()
        return dns_srv.start(execute=req.execute) if req.enabled else dns_srv.stop(execute=req.execute)

    @app.post("/api/autonomy/qos")
    def autonomy_apply_qos(req: ExecuteFlagRequest):
        from .qos_controller import apply_app_dscp_qos_policies
        return apply_app_dscp_qos_policies(execute=req.execute)

    @app.post("/api/autonomy/service")
    def autonomy_service_toggle(req: AutonomyToggleRequest):
        from .qos_controller import manage_autostart_service
        return manage_autostart_service(enabled=req.enabled, execute=req.execute)

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
    def update_llm_settings(req: LLMConfigUpdateRequest):
        gateway = LLMGateway()
        payload = req.model_dump(exclude_none=True)
        gateway.update_config(payload)
        return {"status": "saved", "config": _sanitize_llm_config(gateway.config)}

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
    def trigger_tasks(req: Optional[ExecuteFlagRequest] = Body(default=None)):
        execute = bool(req.execute) if req else False
        sched = get_task_scheduler()
        return sched.discover_and_schedule_cycle(execute=execute)

    @app.post("/api/device/maintain")
    def run_device_maintenance(req: Optional[ExecuteFlagRequest] = Body(default=None)):
        execute = bool(req.execute) if req else False
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
