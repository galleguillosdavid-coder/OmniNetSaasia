"""
OmniNet Cloud SaaS Backend & Secure DeepSeek Proxy Server (`cloud_server/proxy_server.py`).
Deploy this file on any cloud host (Render, Fly.io, Railway, DigitalOcean, AWS, or VPS).

Responsibilities:
  1. Keeps your DEEPSEEK_API_KEY 100% secret on the server (never inside OmniNet.exe).
  2. Validates user license keys & Hardware IDs (1 PC for Pro, 5 PCs for Family).
  3. Receives payment webhooks from Lemon Squeezy / Stripe to auto-generate license keys.
  4. Aggregates anonymous conversation feedback from global users to improve the AI.
"""

from __future__ import annotations
import os
import sys
import json
import time
import hmac
import hashlib
import tempfile
import threading
import urllib.request
from contextlib import contextmanager
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Callable, Iterator, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netopt import __version__ as OMNINET_VERSION
from netopt.licensing import generate_signed_license_key, verify_signed_license_key, PLAN_CATALOG
from netopt.adapters import HttpClientAdapter
from netopt.schemas import LicenseActivationRequest, TelemetryReport, CloudChatRequest

try:
    from .supabase_client import (
        is_supabase_configured,
        get_license_from_supabase,
        upsert_license_in_supabase,
        update_license_devices,
        save_conversation_feedback_in_supabase,
        save_device_telemetry_in_supabase,
        save_payment_event_in_supabase
    )
except (ImportError, ValueError):
    from supabase_client import (
        is_supabase_configured,
        get_license_from_supabase,
        upsert_license_in_supabase,
        update_license_devices,
        save_conversation_feedback_in_supabase,
        save_device_telemetry_in_supabase,
        save_payment_event_in_supabase
    )

CLOUD_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_subscriptions_db.json")
CLOUD_FEEDBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_global_feedback.json")
CLOUD_TELEMETRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_global_telemetry.json")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
LEMONSQUEEZY_WEBHOOK_SECRET = os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
ADMIN_SECRET_KEY = os.environ.get("OMNINET_ADMIN_KEY", "")
MAX_PAYLOAD_SIZE = 1024 * 1024  # 1 MB
_CLOUD_IO_LOCK = threading.RLock()


class CloudDataCorruptionError(RuntimeError):
    """El archivo persistente existe, pero no contiene datos JSON válidos."""


class CloudLockTimeoutError(TimeoutError):
    """No se pudo adquirir el bloqueo interproceso dentro del tiempo límite."""


@contextmanager
def _interprocess_file_lock(lock_path: str, timeout_sec: float = 5.0) -> Iterator[None]:
    """Portable cross-process advisory file lock (msvcrt on Windows, fcntl on POSIX)."""
    parent = os.path.dirname(os.path.abspath(lock_path)) or "."
    os.makedirs(parent, exist_ok=True)
    deadline = time.monotonic() + max(0.1, float(timeout_sec))
    with open(lock_path, "a+b") as lock_file:
        acquired = False
        try:
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise CloudLockTimeoutError(
                            f"Timeout esperando bloqueo de archivo: {os.path.basename(lock_path)}"
                        )
                    time.sleep(0.01)
            yield
        finally:
            if acquired:
                try:
                    if os.name == "nt":
                        import msvcrt
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass


def _atomic_write_json(path: str, data: Any) -> None:
    """Atomically writes JSON data to disk with flush, fsync, and restrictive permissions."""
    abs_path = os.path.abspath(path)
    parent = os.path.dirname(abs_path) or "."
    os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent, prefix=".cloud_", suffix=".tmp")
    closed = False
    try:
        try:
            os.chmod(tmp_path, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            closed = True
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, abs_path)
        if os.name != "nt":
            try:
                dir_fd = os.open(parent, os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except OSError:
                pass
    except Exception:
        if not closed:
            try:
                os.close(fd)
            except OSError:
                pass
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


def _read_json_list(path: str) -> List[Dict[str, Any]]:
    with _CLOUD_IO_LOCK:
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CloudDataCorruptionError(
                f"No se pudo leer el almacén persistente: {os.path.basename(path)}"
            ) from exc
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise CloudDataCorruptionError(
                f"Formato inválido en almacén: se esperaba una lista de objetos ({os.path.basename(path)})"
            )
        return data


def _append_json_list(path: str, entry: Dict[str, Any], limit: int) -> None:
    with _CLOUD_IO_LOCK:
        with _interprocess_file_lock(f"{os.path.abspath(path)}.lock"):
            items = _read_json_list(path)
            items.append(entry)
            _atomic_write_json(path, items[-limit:])


def load_cloud_db() -> Dict[str, Any]:
    with _CLOUD_IO_LOCK:
        if not os.path.exists(CLOUD_DB_FILE):
            db = {
                "licenses": {},
                "processed_webhook_events": []
            }
            _atomic_write_json(CLOUD_DB_FILE, db)
            return db
        try:
            with open(CLOUD_DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CloudDataCorruptionError(
                f"No se pudo leer la base de licencias: {os.path.basename(CLOUD_DB_FILE)}"
            ) from exc
        if (
            not isinstance(db, dict)
            or not isinstance(db.get("licenses", {}), dict)
            or not isinstance(db.get("processed_webhook_events", []), list)
        ):
            raise CloudDataCorruptionError(
                f"Estructura inválida en base de licencias ({os.path.basename(CLOUD_DB_FILE)})"
            )
        db.setdefault("licenses", {})
        db.setdefault("processed_webhook_events", [])
        return db


def _update_cloud_db(mutator: Callable[[Dict[str, Any]], Any]) -> Any:
    """Executes a read-modify-write transaction on CLOUD_DB_FILE under thread + process locks."""
    with _CLOUD_IO_LOCK:
        with _interprocess_file_lock(f"{os.path.abspath(CLOUD_DB_FILE)}.lock"):
            db = load_cloud_db()
            result, should_save = mutator(db)
            if should_save:
                _atomic_write_json(CLOUD_DB_FILE, db)
            return result


def verify_lemon_squeezy_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verifies Lemon Squeezy HMAC-SHA256 signature from X-Signature header."""
    if not secret or not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature_header.strip(), expected)


def verify_stripe_signature(raw_body: bytes, signature_header: str, secret: str, tolerance: int = 300) -> bool:
    """
    Verifies Stripe-Signature header according to Stripe's official standard:
    Header format: t=timestamp,v1=signature[,v0=...]
    Signed payload: f"{t}.".encode('utf-8') + raw_body
    """
    if not secret or not signature_header:
        return False
    parts: Dict[str, List[str]] = {}
    for item in signature_header.split(","):
        kv = item.split("=", 1)
        if len(kv) == 2:
            parts.setdefault(kv[0].strip(), []).append(kv[1].strip())

    timestamp_list = parts.get("t")
    v1_signatures = parts.get("v1")
    if not timestamp_list or not v1_signatures:
        return False

    try:
        ts = int(timestamp_list[0])
    except (ValueError, TypeError):
        return False

    if tolerance > 0 and abs(time.time() - ts) > tolerance:
        return False

    signed_payload = f"{ts}.".encode("utf-8") + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

    return any(hmac.compare_digest(sig, expected) for sig in v1_signatures)


def save_cloud_db(db: Dict[str, Any]) -> None:
    with _CLOUD_IO_LOCK:
        with _interprocess_file_lock(f"{os.path.abspath(CLOUD_DB_FILE)}.lock"):
            _atomic_write_json(CLOUD_DB_FILE, db)


def append_global_feedback(entry: Dict[str, Any]) -> None:
    _append_json_list(CLOUD_FEEDBACK_FILE, entry, limit=500)


def compute_global_feedback_stats() -> Dict[str, Any]:
    """
    Computes aggregated statistical metrics across all anonymized AI assistant feedback entries.
    Provides insights into conversational volume, AI model distribution, and average session depth
    without storing or exposing user prompts or private identifiers.
    """
    items = _read_json_list(CLOUD_FEEDBACK_FILE)

    total_entries = len(items)
    if not total_entries:
        return {
            "service": "OmniNet Global Feedback Aggregator",
            "total_feedback_entries": 0,
            "unique_devices": 0,
            "unique_licenses": 0,
            "avg_messages_per_session": 0.0,
            "models_used": {},
            "recent_activity_count": 0
        }

    devices = set()
    licenses = set()
    msg_counts = []
    models: Dict[str, int] = {}
    now = time.time()
    recent_24h = 0

    for it in items:
        dev = it.get("device_hash")
        if dev:
            devices.add(dev)
        lic = it.get("license_hash")
        if lic:
            licenses.add(lic)
        cnt = it.get("msg_count")
        if cnt is not None and isinstance(cnt, (int, float)) and cnt >= 0:
            msg_counts.append(int(cnt))
        mod = str(it.get("model") or "unknown").strip()
        models[mod] = models.get(mod, 0) + 1
        ts = it.get("timestamp", 0)
        if isinstance(ts, (int, float)) and (now - ts) <= 86400:
            recent_24h += 1

    return {
        "service": "OmniNet Global Feedback Aggregator",
        "total_feedback_entries": total_entries,
        "unique_devices": len(devices),
        "unique_licenses": len(licenses),
        "avg_messages_per_session": round(sum(msg_counts) / len(msg_counts), 2) if msg_counts else 0.0,
        "models_used": models,
        "recent_activity_count": recent_24h
    }



def append_global_telemetry(entry: Dict[str, Any]) -> None:
    _append_json_list(CLOUD_TELEMETRY_FILE, entry, limit=1000)


def compute_global_telemetry_stats() -> Dict[str, Any]:
    """
    Computes aggregated statistical metrics across all anonymized device telemetry reports.
    Provides global insights into fleet health, bufferbloat distribution, latency averages,
    and Wi-Fi 7 adoption without exposing sensitive device identities.
    """
    items = _read_json_list(CLOUD_TELEMETRY_FILE)

    total_reports = len(items)
    if not total_reports:
        return {
            "service": "OmniNet Global Telemetry Aggregator",
            "total_reports": 0,
            "unique_devices": 0,
            "avg_latency_ms": 0.0,
            "avg_jitter_ms": 0.0,
            "avg_packet_loss_pct": 0.0,
            "bufferbloat_distribution": {},
            "platforms_breakdown": {},
            "wifi7_devices_count": 0,
            "app_versions": {}
        }

    devices = set()
    latencies = []
    jitters = []
    packet_losses = []
    bufferbloat: Dict[str, int] = {}
    platforms: Dict[str, int] = {}
    wifi7_count = 0
    versions: Dict[str, int] = {}

    for it in items:
        dev = it.get("device_hash")
        if dev:
            devices.add(dev)
        lat = it.get("avg_latency_ms")
        if lat is not None and isinstance(lat, (int, float)) and lat >= 0:
            latencies.append(float(lat))
        jit = it.get("jitter_ms")
        if jit is not None and isinstance(jit, (int, float)) and jit >= 0:
            jitters.append(float(jit))
        loss = it.get("packet_loss_pct")
        if loss is not None and isinstance(loss, (int, float)) and loss >= 0:
            packet_losses.append(float(loss))
        grade = str(it.get("bufferbloat_grade") or "N/A").strip().upper()
        bufferbloat[grade] = bufferbloat.get(grade, 0) + 1
        plat = str(it.get("platform") or "unknown").strip().lower()
        platforms[plat] = platforms.get(plat, 0) + 1
        if it.get("is_wifi7"):
            wifi7_count += 1
        ver = str(it.get("app_version") or "unknown").strip()
        versions[ver] = versions.get(ver, 0) + 1

    return {
        "service": "OmniNet Global Telemetry Aggregator",
        "total_reports": total_reports,
        "unique_devices": len(devices),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "avg_jitter_ms": round(sum(jitters) / len(jitters), 2) if jitters else 0.0,
        "avg_packet_loss_pct": round(sum(packet_losses) / len(packet_losses), 2) if packet_losses else 0.0,
        "bufferbloat_distribution": bufferbloat,
        "platforms_breakdown": platforms,
        "wifi7_devices_count": wifi7_count,
        "app_versions": versions
    }


def format_rfc9457_problem_details(
    status: int,
    title: str,
    detail: str,
    instance: str = "",
    type_uri: str = "about:blank",
    **kwargs
) -> Dict[str, Any]:
    """
    Constructs an RFC 9457 compliant Problem Details object (obsoleting RFC 7807):
    - type: URI reference identifying the problem type. Defaults to 'about:blank'.
    - status: HTTP status code.
    - title: Short, human-readable summary that does not change across occurrences.
    - detail: Human-readable explanation specific to this occurrence.
    - instance: URI reference identifying this specific occurrence of the problem.
    - error: Legacy compatibility field ensuring seamless interoperability with older clients.
    - kwargs: Extension members providing structured domain-specific diagnostic data.
    """
    payload: Dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance or "",
        "error": detail or title
    }
    for k, v in kwargs.items():
        if v is not None:
            payload[k] = v
    return payload


class OmniNetCloudProxyHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        if hasattr(self, "request") and self.request is not None:
            try:
                self.request.settimeout(15.0)
            except OSError:
                pass

    def log_message(self, format, *args):
        pass

    def _read_exact_body(self) -> Tuple[Optional[bytes], Optional[Dict[str, Any]]]:
        """Reads and validates the HTTP request body according to strict length/timeout rules."""
        transfer_enc = (self.headers.get("Transfer-Encoding") or "").strip().lower()
        if transfer_enc and transfer_enc != "identity":
            self.send_json(501, {"error": "Transfer-Encoding no soportado"})
            return None, None

        raw_len = self.headers.get("Content-Length")
        if raw_len is None:
            self.send_json(411, {"error": "Cabecera Content-Length requerida"})
            return None, None
        try:
            length = int(raw_len)
        except (ValueError, TypeError):
            self.send_json(400, {"error": "Cabecera Content-Length inválida"})
            return None, None
        if length < 0:
            self.send_json(400, {"error": "Cabecera Content-Length negativa"})
            return None, None
        if length > MAX_PAYLOAD_SIZE:
            self.send_json(413, {"error": "Payload Too Large (Máximo 1MB permitido)"})
            return None, None

        if length == 0:
            return b"", {}

        chunks = []
        remaining = length
        try:
            while remaining > 0:
                chunk = self.rfile.read(remaining)
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
        except TimeoutError:
            self.send_json(408, {"error": "Timeout leyendo el cuerpo HTTP"})
            return None, None
        except OSError:
            self.send_json(400, {"error": "Error leyendo el cuerpo HTTP"})
            return None, None

        raw_body = b"".join(chunks)
        if len(raw_body) != length:
            self.send_json(400, {"error": "Cuerpo HTTP truncado o incompleto"})
            return None, None

        try:
            parsed = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "JSON inválido en el cuerpo de la petición"})
            return None, None
        if not isinstance(parsed, dict):
            self.send_json(400, {"error": "El cuerpo JSON debe ser un objeto"})
            return None, None
        return raw_body, parsed

    def _send_common_security_headers(self, is_api: bool = True):
        """Emit standard hardening headers on all Cloud SaaS responses."""
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        if is_api:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Signature, Stripe-Signature")
            self.send_header("Cache-Control", "no-store")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_common_security_headers(is_api=True)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_json(self, status: int, payload: Dict[str, Any]):
        body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_common_security_headers(is_api=True)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_problem(
        self,
        status: int,
        title: str,
        detail: str,
        instance: str = "",
        type_uri: str = "about:blank",
        **kwargs
    ):
        """Dispatches an RFC 9457 problem details response with application/problem+json."""
        payload = format_rfc9457_problem_details(status, title, detail, instance, type_uri, **kwargs)
        body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/problem+json; charset=utf-8")
        self._send_common_security_headers(is_api=True)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, status: int, html: str):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._send_common_security_headers(is_api=False)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            landing = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>OmniNet AI SaaS — Free Full & Cloud Pro</title>
<style>
body{{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#020617;color:#e2e8f0;line-height:1.5}}
.wrap{{max-width:980px;margin:0 auto;padding:40px 20px}}
.badge{{display:inline-block;padding:4px 12px;border-radius:999px;background:#0f172a;border:1px solid #334155;font-size:12px;color:#38bdf8}}
h1{{font-size:2.2rem;margin:14px 0 8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:26px}}
.card{{background:#0f172a;border:1px solid #1e293b;border-radius:16px;padding:22px}}
.pro{{border-color:#0ea5e9}}
ul{{padding-left:18px;font-size:14px;color:#cbd5e1}}
.price{{font-size:1.7rem;font-weight:800;margin:8px 0}}
a.btn{{display:inline-block;margin-top:10px;padding:10px 16px;border-radius:10px;text-decoration:none;font-weight:700;font-size:14px}}
.b-free{{background:#10b981;color:#022c22}}
.b-pro{{background:#0284c7;color:#fff}}
.pulse{{display:inline-flex;align-items:center;gap:8px;margin-top:14px;padding:8px 14px;border-radius:10px;background:#0f172a;border:1px solid #1e293b;font-size:13px;color:#86efac}}
.meta{{margin-top:28px;font-size:12px;color:#94a3b8}}
</style></head><body><div class="wrap">
<span class="badge">OmniNet Global SaaS · v{OMNINET_VERSION}</span>
<h1>Optimización Autónoma de Red y Defensa IA para Todo el Mundo</h1>
<p>Dos ediciones completas: descarga y usa la <strong>Edición Gratuita Full</strong> sin límites locales, o activa la <strong>Edición Cloud SaaS Pagada Full</strong> para IA administrada y flotas multi-dispositivo.</p>
<div id="livePulse" class="pulse">⚡ Red Global OmniNet: conectando telemetría en vivo...</div>
<div class="grid">
  <div class="card">
    <h2>🆓 Edición Gratuita Full (Local-First)</h2>
    <div class="price">$0 USD <small>/ para siempre</small></div>
    <ul>
      <li>Optimización TCP/UDP/DNS/QUIC + Zero NetLoss + Auto-Rollback</li>
      <li>Escudo Anti-Hackeos con IA + Cuarentena Reversible SHA-256</li>
      <li>Red Mesh Virtual (<code>wintun.dll</code>) + 10 Sub-Agentes + Auto-Cuidado 10m</li>
      <li>Asistente Cognitivo Hermes local + BYOK / Ollama ilimitado + 5 consultas Cloud de prueba</li>
    </ul>
    <a class="btn b-free" href="/v1/plans">Ver Especificación Free Full (JSON)</a>
  </div>
  <div class="card pro">
    <h2>💎 Edición Pagada Full (Cloud SaaS Pro / Pyme)</h2>
    <div class="price">$4.99 - $12.99 USD <small>/ mes</small></div>
    <ul>
      <li>Todo lo de la Edición Gratuita Full sin restricciones</li>
      <li>IA Cloud Administrada ilimitada (sin necesitar tu propia API Key)</li>
      <li>Licencia multi-dispositivo (1 PC Pro · 5 PCs Hogar / Pyme)</li>
      <li>Telemetría global agregada y prioridad de soporte SaaS</li>
    </ul>
    <a class="btn b-pro" href="/v1/telemetry/stats">Ver Telemetría Global en Vivo</a>
  </div>
</div>
<div class="meta">Endpoints públicos: <code>GET /health</code> · <code>GET /v1/plans</code> · <code>POST /v1/license/activate</code> · <code>POST /v1/chat</code> · <code>POST /v1/telemetry/report</code></div>
<script>fetch('/v1/telemetry/stats').then(r=>r.json()).then(d=>{{const el=document.getElementById('livePulse');if(el)el.textContent=`🌐 Red Global Activa · Dispositivos: ${{d.total_devices||0}} · Latencia promedio: ${{d.avg_latency_ms||'--'}} ms`;}}).catch(()=>{{}});</script>
</div></body></html>"""
            self.send_html(200, landing)
        elif self.path == "/health":
            self.send_json(200, {
                "status": "ok",
                "service": "OmniNet Global SaaS Cloud Proxy",
                "version": OMNINET_VERSION,
                "supabase_connected": is_supabase_configured()
            })
        elif self.path == "/v1/plans":
            from netopt.licensing import PLAN_CATALOG
            self.send_json(200, {
                "service": "OmniNet Global SaaS",
                "editions": {
                    "free_full": PLAN_CATALOG["free"],
                    "paid_pro": PLAN_CATALOG["pro"],
                    "paid_family": PLAN_CATALOG["family"],
                },
                "plans": PLAN_CATALOG
            })
        elif self.path == "/v1/admin/stats":
            # OMNI-022: Fail-Closed. Endpoint administrativo deshabilitado si OMNINET_ADMIN_KEY no está configurado
            if not ADMIN_SECRET_KEY:
                self.send_json(503, {"error": "Endpoint administrativo deshabilitado: OMNINET_ADMIN_KEY no configurado en servidor (Fail-Closed)."})
                return
            auth = self.headers.get("Authorization", "")
            if not hmac.compare_digest(auth, f"Bearer {ADMIN_SECRET_KEY}"):
                self.send_json(401, {"error": "Unauthorized: Clave de administrador requerida."})
                return
            try:
                db = load_cloud_db()
            except (CloudDataCorruptionError, CloudLockTimeoutError):
                self.send_json(503, {"error": "Almacén de licencias temporalmente no disponible."})
                return
            lics = db.get("licenses", {})
            self.send_json(200, {
                "service": "OmniNet Global Cloud Proxy",
                "supabase_connected": is_supabase_configured(),
                "total_licenses": len(lics),
                "active_licenses": sum(1 for v in lics.values() if v.get("active")),
                "total_queries_proxied": sum(v.get("queries_count", 0) for v in lics.values()),
                "sample_keys": [f"{k[:8]}...{k[-4:]}" for k in list(lics.keys())[:5]]
            })
        elif self.path == "/v1/telemetry/stats":
            try:
                self.send_json(200, compute_global_telemetry_stats())
            except (CloudDataCorruptionError, CloudLockTimeoutError):
                self.send_json(503, {"error": "Almacén de telemetría temporalmente no disponible."})
        elif self.path == "/v1/feedback/stats":
            try:
                self.send_json(200, compute_global_feedback_stats())
            except (CloudDataCorruptionError, CloudLockTimeoutError):
                self.send_json(503, {"error": "Almacén de feedback temporalmente no disponible."})
        else:
            self.send_json(200, {
                "status": "online",
                "service": "OmniNet Global SaaS Cloud Proxy",
                "supabase_connected": is_supabase_configured()
            })

    def do_POST(self):
        raw_body, data = self._read_exact_body()
        if raw_body is None or data is None:
            return

        # 1. License Activation & Hardware ID Binding
        if self.path == "/v1/license/activate":
            try:
                act_req = LicenseActivationRequest.model_validate(data)
                key = act_req.license_key.strip().upper()
                dev_id = (act_req.device_id or "UNKNOWN").strip()
                email = (act_req.email or "").strip()
            except Exception as e:
                self.send_json(400, {"valid": False, "error": f"Datos de activación inválidos: {e}"})
                return

            supa_rec = get_license_from_supabase(key) if is_supabase_configured() else None

            def _activate_tx(db_obj: Dict[str, Any]):
                lics_map = db_obj.setdefault("licenses", {})
                rec = supa_rec or lics_map.get(key)
                created_new = False
                if not rec:
                    plan_sig = verify_signed_license_key(key)
                    if plan_sig:
                        rec = {
                            "license_key": key,
                            "plan": plan_sig,
                            "email": email or "customer@omninet.ai",
                            "active": True,
                            "max_devices": PLAN_CATALOG[plan_sig]["max_devices"],
                            "devices": [],
                            "queries_count": 0,
                            "created_at": time.time()
                        }
                        lics_map[key] = rec
                        created_new = True

                if not rec or not rec.get("active"):
                    return (403, {"valid": False, "error": "Licencia inválida o inactiva"}, None, False), created_new

                expires_at = rec.get("expires_at")
                if expires_at and float(expires_at) < time.time():
                    return (403, {"valid": False, "error": "Licencia expirada. Renueve su suscripción para continuar."}, None, False), created_new

                devices = rec.get("devices", [])
                if isinstance(devices, str):
                    try:
                        devices = json.loads(devices)
                    except Exception:
                        devices = []
                if not isinstance(devices, list):
                    devices = []

                max_devs = rec.get("max_devices", 1)
                devices_updated = False
                if dev_id not in devices:
                    if len(devices) >= max_devs:
                        return (403, {
                            "valid": False,
                            "error": f"Esta licencia ya alcanzó el límite de {max_devs} computador(es)."
                        }, None, False), created_new
                    devices.append(dev_id)
                    rec["devices"] = devices
                    lics_map[key] = rec
                    devices_updated = True

                return (200, {
                    "valid": True,
                    "plan": rec["plan"],
                    "devices_bound": len(devices),
                    "max_devices": max_devs
                }, rec, devices_updated), (created_new or devices_updated)

            try:
                status_code, resp_body, rec_saved, devs_updated = _update_cloud_db(_activate_tx)
            except (CloudDataCorruptionError, CloudLockTimeoutError):
                self.send_json(503, {"valid": False, "error": "Almacén de licencias temporalmente no disponible."})
                return

            if is_supabase_configured() and rec_saved is not None:
                if devs_updated:
                    upsert_license_in_supabase(rec_saved)
                    update_license_devices(key, rec_saved.get("devices", []), rec_saved.get("queries_count", 0))
            self.send_json(status_code, resp_body)

        # 2. Secure DeepSeek Proxy Endpoint (OMNI-004, OMNI-018, OMNI-022)
        elif self.path == "/v1/chat":
            try:
                chat_req = CloudChatRequest.model_validate(data)
                key = chat_req.license_key.strip().upper()
                dev_id = chat_req.device_id.strip()
                messages = chat_req.messages
            except Exception as e:
                if not data.get("license_key"):
                    self.send_json(401, {"error": "Clave de licencia requerida para acceder al proxy IA."})
                elif not data.get("device_id") or len(str(data.get("device_id", "")).strip()) < 4:
                    self.send_json(400, {"error": "Identificador de dispositivo (device_id) válido requerido."})
                elif not isinstance(data.get("messages"), list) or len(data.get("messages", [])) == 0:
                    self.send_json(400, {"error": "Lista de mensajes ('messages') requerida y no vacía."})
                elif len(data.get("messages", [])) > 50:
                    self.send_json(400, {"error": "Límite de historial excedido (máximo 50 mensajes por consulta)."})
                else:
                    self.send_json(400, {"error": f"Solicitud malformada: {e}"})
                return

            rec = None
            if is_supabase_configured():
                rec = get_license_from_supabase(key)
            if not rec:
                try:
                    rec = load_cloud_db().get("licenses", {}).get(key)
                except CloudDataCorruptionError:
                    self.send_json(503, {"error": "Almacén de licencias temporalmente no disponible."})
                    return

            # OMNI-004 / OMNI-018: Validar existencia, estado activo y expiración
            if not rec or not rec.get("active"):
                self.send_json(403, {"error": "Licencia no encontrada, cancelada o inactiva."})
                return

            expires_at = rec.get("expires_at")
            if expires_at and float(expires_at) < time.time():
                self.send_json(403, {"error": "Licencia expirada. Renueve su suscripción para continuar."})
                return

            # OMNI-018: Validación estricta de vinculación previa (prohibido auto-registro en /v1/chat)
            devices = rec.get("devices", [])
            if isinstance(devices, str):
                try:
                    devices = json.loads(devices)
                except Exception:
                    devices = []
            if not isinstance(devices, list):
                devices = []

            if dev_id not in devices:
                self.send_json(403, {
                    "error": "Dispositivo no autorizado para esta licencia. Debe activar su equipo previamente en /v1/license/activate."
                })
                return

            # OMNI-018: Ciclo de cuota mensual real con ventana de 30 días
            now_ts = time.time()
            period_start = float(rec.get("period_start", rec.get("created_at", now_ts)))
            if now_ts - period_start >= 30 * 86400:
                # Nuevo ciclo mensual iniciado
                rec["period_start"] = now_ts
                rec["queries_count"] = 0
                cur_count = 0
            else:
                cur_count = int(rec.get("queries_count", 0))

            plan = rec.get("plan", "pro")
            limit = PLAN_CATALOG.get(plan, {}).get("monthly_ai_limit", 999999)
            if cur_count >= limit:
                self.send_json(429, {"error": f"Cuota mensual de consultas de IA alcanzada ({cur_count}/{limit})."})
                return

            if not DEEPSEEK_API_KEY:
                self.send_json(503, {"error": "DEEPSEEK_API_KEY no configurada en el servidor nube."})
                return

            try:
                endpoint = f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"
                payload = {
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 350
                }
                headers = {
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
                }

                if HttpClientAdapter.is_available():
                    status_code, resp_data = HttpClientAdapter.post_json(endpoint, payload, headers=headers, timeout_sec=25.0)
                    if status_code == 200 and isinstance(resp_data, dict) and "choices" in resp_data:
                        reply = resp_data["choices"][0]["message"]["content"]
                    else:
                        raise RuntimeError(f"HTTP upstream error {status_code}: {resp_data.get('error', resp_data)}")
                else:
                    req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=headers,
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=25) as resp:
                        resp_data = json.loads(resp.read().decode("utf-8"))
                        reply = resp_data["choices"][0]["message"]["content"]

                # Deduct quota atomically and record anonymized telemetry only after verified upstream response
                def _deduct_quota_tx(db_obj: Dict[str, Any]):
                    lics_map = db_obj.setdefault("licenses", {})
                    target_rec = lics_map.get(key) or rec
                    target_rec["queries_count"] = cur_count + 1
                    target_rec["period_start"] = period_start
                    lics_map[key] = target_rec
                    return target_rec["queries_count"], True

                new_q_count = _update_cloud_db(_deduct_quota_tx)
                if is_supabase_configured():
                    update_license_devices(key, devices, new_q_count)

                # OMNI-008: Anonimización criptográfica estricta de telemetría (cero filtración de mensajes o IDs)
                anon_dev = hashlib.sha256(f"dev:{dev_id}".encode()).hexdigest()[:12] if dev_id else "ANON"
                anon_lic = hashlib.sha256(f"lic:{key}".encode()).hexdigest()[:12] if key else "ANON"
                feedback_entry = {
                    "timestamp": time.time(),
                    "device_hash": anon_dev,
                    "license_hash": anon_lic,
                    "msg_count": len(messages),
                    "model": "deepseek-chat"
                }
                append_global_feedback(feedback_entry)
                if is_supabase_configured():
                    save_conversation_feedback_in_supabase({
                        "device_id": anon_dev,
                        "license_key": anon_lic,
                        "user_message": f"[Telemetry Anonymized] {len(messages)} prompts processed"
                    })

                self.send_json(200, {"reply": reply, "model": "deepseek-chat-cloud-proxy"})
            except Exception as e:
                # OMNI-022: Error genérico seguro con request_id (sin exponer trazas internas)
                req_id = hashlib.sha256(f"{time.time()}:{key}".encode()).hexdigest()[:8]
                self.send_json(500, {
                    "error": "Error de comunicación con el proveedor de IA. Intente nuevamente en unos instantes.",
                    "request_id": req_id
                })

        # 2.5 Colector Global de Métricas de Rendimiento de Dispositivos (Mundo)
        elif self.path == "/v1/telemetry/report":
            try:
                telem_req = TelemetryReport.model_validate(data)
            except Exception as e:
                self.send_json(400, {"error": f"Payload de telemetría inválido: {e}"})
                return
            anon_dev = hashlib.sha256(f"dev:{telem_req.device_id}".encode()).hexdigest()[:12] if telem_req.device_id else "ANON"
            telemetry_entry = {
                "timestamp": telem_req.timestamp,
                "device_hash": anon_dev,
                "platform": str(telem_req.platform or data.get("platform", "unknown")),
                "avg_latency_ms": float(telem_req.avg_latency_ms if telem_req.avg_latency_ms is not None else (telem_req.latency_ms or 0.0)),
                "jitter_ms": float(telem_req.jitter_ms or 0.0),
                "packet_loss_pct": float(telem_req.packet_loss_pct or 0.0),
                "bufferbloat_grade": str(telem_req.bufferbloat_grade or "N/A"),
                "active_interface": str(telem_req.active_interface or data.get("active_interface", "unknown")),
                "subagents_status": data.get("subagents_status", {}),
                "is_wifi7": bool(telem_req.is_wifi7 or False),
                "app_version": str(telem_req.app_version or OMNINET_VERSION)
            }
            try:
                append_global_telemetry(telemetry_entry)
            except (CloudDataCorruptionError, CloudLockTimeoutError):
                self.send_json(503, {"error": "Almacén de telemetría temporalmente no disponible."})
                return
            if is_supabase_configured():
                save_device_telemetry_in_supabase(telemetry_entry)
            self.send_json(200, {"status": "telemetry_received", "device_hash": anon_dev})

        # 3. Payment Webhook con Validación Criptográfica Estricta e Idempotencia (OMNI-013)
        elif self.path == "/v1/webhooks/payment":
            # 3.1 Fail-Closed: Si los secretos no están configurados, rechazar y nunca emitir licencias
            if not LEMONSQUEEZY_WEBHOOK_SECRET and not STRIPE_WEBHOOK_SECRET:
                self.send_json(503, {"error": "Webhooks no configurados: secretos de pago ausentes en servidor (Fail-Closed)."})
                return

            lemon_sig = self.headers.get("X-Signature", "").strip()
            stripe_sig = self.headers.get("Stripe-Signature", "").strip()

            if not lemon_sig and not stripe_sig:
                self.send_json(401, {"error": "Firma de webhook ausente (X-Signature o Stripe-Signature requerida)."})
                return

            provider = ""
            if lemon_sig:
                if not LEMONSQUEEZY_WEBHOOK_SECRET:
                    self.send_json(503, {"error": "Proveedor Lemon Squeezy no configurado en servidor."})
                    return
                if not verify_lemon_squeezy_signature(raw_body, lemon_sig, LEMONSQUEEZY_WEBHOOK_SECRET):
                    self.send_json(401, {"error": "Firma Lemon Squeezy HMAC inválida."})
                    return
                provider = "lemon_squeezy"
            elif stripe_sig:
                if not STRIPE_WEBHOOK_SECRET:
                    self.send_json(503, {"error": "Proveedor Stripe no configurado en servidor."})
                    return
                if not verify_stripe_signature(raw_body, stripe_sig, STRIPE_WEBHOOK_SECRET):
                    self.send_json(401, {"error": "Firma Stripe HMAC inválida o timestamp expirado."})
                    return
                provider = "stripe"

            # 3.2 Idempotencia Persistente y Transaccional (H-02 / Sec 4)
            event_id = str(data.get("meta", {}).get("event_id") or data.get("id") or data.get("data", {}).get("id") or "").strip()
            if not event_id:
                self.send_json(400, {"error": "Identificador de evento (event_id) ausente en payload."})
                return

            # 3.3 Verificación estricta de evento de pago aprobado
            if provider == "lemon_squeezy":
                event_name = str(data.get("meta", {}).get("event_name", "")).lower()
                attrs = data.get("data", {}).get("attributes", {})
                payment_status = str(attrs.get("status", "")).lower()
                is_paid = (
                    event_name in ("order_created", "subscription_created") and
                    payment_status in ("paid", "active")
                )
                email = (attrs.get("user_email") or "").strip().lower()
                custom_plan = str(data.get("meta", {}).get("custom_data", {}).get("plan") or "").lower()
                product_name = str(attrs.get("first_order_item", {}).get("product_name", "")).lower()
            else:  # stripe
                event_name = str(data.get("type", "")).lower()
                obj = data.get("data", {}).get("object", {})
                payment_status = str(obj.get("payment_status") or obj.get("status") or "").lower()
                is_paid = (
                    (event_name == "checkout.session.completed" and payment_status in ("paid", "complete")) or
                    (event_name == "payment_intent.succeeded" and payment_status in ("succeeded", "paid"))
                )
                email = (
                    obj.get("customer_details", {}).get("email") or
                    obj.get("receipt_email") or
                    obj.get("customer_email") or
                    ""
                ).strip().lower()
                custom_plan = str(obj.get("metadata", {}).get("plan") or "").lower()
                product_name = str(obj.get("description", "")).lower()

            if not is_paid:
                self.send_json(200, {
                    "status": "ignored_non_paid_event",
                    "event_name": event_name,
                    "payment_status": payment_status
                })
                return

            if not email:
                self.send_json(400, {"error": "Email no encontrado en el payload de pago."})
                return

            # 3.4 Mapeo de producto autorizado (sin texto libre arbitrario)
            if custom_plan in ("pro", "family"):
                plan = custom_plan
            elif "family" in product_name or "hogar" in product_name or "5 pc" in product_name:
                plan = "family"
            else:
                plan = "pro"

            def _webhook_tx(db_obj: Dict[str, Any]):
                processed_list = db_obj.setdefault("processed_webhook_events", [])
                if event_id in processed_list:
                    return ("duplicate", None, None), False
                lics_map = db_obj.setdefault("licenses", {})
                new_key = generate_signed_license_key(plan, email)
                record = {
                    "license_key": new_key,
                    "plan": plan,
                    "email": email,
                    "active": True,
                    "max_devices": PLAN_CATALOG[plan]["max_devices"],
                    "devices": [],
                    "queries_count": 0,
                    "created_at": time.time()
                }
                lics_map[new_key] = record
                processed_list.append(event_id)
                if len(processed_list) > 5000:
                    db_obj["processed_webhook_events"] = processed_list[-5000:]
                return ("created", new_key, record), True

            try:
                outcome, new_key, record = _update_cloud_db(_webhook_tx)
            except (CloudDataCorruptionError, CloudLockTimeoutError):
                self.send_json(503, {"error": "Almacén de pagos temporalmente no disponible."})
                return

            if outcome == "duplicate":
                self.send_json(200, {"status": "idempotent_duplicate_ignored", "event_id": event_id})
                return

            if is_supabase_configured() and record is not None:
                upsert_license_in_supabase(record)
                save_payment_event_in_supabase(event_name or "payment_received", provider, {"event_id": event_id, "email": email, "plan": plan})

            self.send_json(200, {
                "created": True,
                "email": email,
                "plan": plan,
                "license_key": new_key,
                "event_id": event_id
            })
        else:
            self.send_json(404, {"error": "Endpoint no encontrado"})


def run_cloud_server(port: int = 9988, host: Optional[str] = None):
    bind_host = host or os.environ.get("OMNINET_CLOUD_HOST", "127.0.0.1")
    srv = ThreadingHTTPServer((bind_host, port), OmniNetCloudProxyHandler)
    print(f"[OmniNet Cloud SaaS] Servidor de Licencias y Proxy DeepSeek escuchando en http://{bind_host}:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OmniNet Global SaaS Cloud Proxy")
    parser.add_argument("--host", default=os.environ.get("OMNINET_CLOUD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "9988")))
    args = parser.parse_args()
    run_cloud_server(port=args.port, host=args.host)

