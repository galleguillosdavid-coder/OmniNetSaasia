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
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


def load_cloud_db() -> Dict[str, Any]:
    if os.path.exists(CLOUD_DB_FILE):
        try:
            with open(CLOUD_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    db = {
        "licenses": {},
        "processed_webhook_events": []
    }
    save_cloud_db(db)
    return db


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
    with open(CLOUD_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def append_global_feedback(entry: Dict[str, Any]) -> None:
    items: List[Dict[str, Any]] = []
    if os.path.exists(CLOUD_FEEDBACK_FILE):
        try:
            with open(CLOUD_FEEDBACK_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []
    items.append(entry)
    with open(CLOUD_FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(items[-500:], f, indent=2, ensure_ascii=False)


def append_global_telemetry(entry: Dict[str, Any]) -> None:
    items: List[Dict[str, Any]] = []
    if os.path.exists(CLOUD_TELEMETRY_FILE):
        try:
            with open(CLOUD_TELEMETRY_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []
    items.append(entry)
    with open(CLOUD_TELEMETRY_FILE, "w", encoding="utf-8") as f:
        json.dump(items[-1000:], f, indent=2, ensure_ascii=False)


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
    def log_message(self, format, *args):
        pass

    def send_json(self, status: int, payload: Dict[str, Any]):
        body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/admin/stats":
            # OMNI-022: Fail-Closed. Endpoint administrativo deshabilitado si OMNINET_ADMIN_KEY no está configurado
            if not ADMIN_SECRET_KEY:
                self.send_json(503, {"error": "Endpoint administrativo deshabilitado: OMNINET_ADMIN_KEY no configurado en servidor (Fail-Closed)."})
                return
            auth = self.headers.get("Authorization", "")
            if auth != f"Bearer {ADMIN_SECRET_KEY}":
                self.send_json(401, {"error": "Unauthorized: Clave de administrador requerida."})
                return
            db = load_cloud_db()
            lics = db.get("licenses", {})
            self.send_json(200, {
                "service": "OmniNet Global Cloud Proxy",
                "supabase_connected": is_supabase_configured(),
                "total_licenses": len(lics),
                "active_licenses": sum(1 for v in lics.values() if v.get("active")),
                "total_queries_proxied": sum(v.get("queries_count", 0) for v in lics.values()),
                "sample_keys": [f"{k[:8]}...{k[-4:]}" for k in list(lics.keys())[:5]]
            })
        else:
            self.send_json(200, {
                "status": "online",
                "service": "OmniNet Global SaaS Cloud Proxy",
                "supabase_connected": is_supabase_configured()
            })

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > MAX_PAYLOAD_SIZE:
            self.send_json(413, {"error": "Payload Too Large (Máximo 1MB permitido)"})
            return

        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        data = {}
        if raw_body:
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except Exception:
                data = {}

        db = load_cloud_db()
        lics = db.setdefault("licenses", {})

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

            rec = None
            if is_supabase_configured():
                rec = get_license_from_supabase(key)
            if not rec:
                rec = lics.get(key)

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
                    lics[key] = rec
                    if is_supabase_configured():
                        upsert_license_in_supabase(rec)

            if not rec or not rec.get("active"):
                self.send_json(403, {"valid": False, "error": "Licencia inválida o inactiva"})
                return

            expires_at = rec.get("expires_at")
            if expires_at and float(expires_at) < time.time():
                self.send_json(403, {"valid": False, "error": "Licencia expirada. Renueve su suscripción para continuar."})
                return

            devices = rec.get("devices", [])
            if isinstance(devices, str):
                try:
                    devices = json.loads(devices)
                except Exception:
                    devices = []
            if not isinstance(devices, list):
                devices = []

            max_devs = rec.get("max_devices", 1)
            if dev_id not in devices:
                if len(devices) >= max_devs:
                    self.send_json(403, {
                        "valid": False,
                        "error": f"Esta licencia ya alcanzó el límite de {max_devs} computador(es)."
                    })
                    return
                devices.append(dev_id)
                rec["devices"] = devices
                save_cloud_db(db)
                if is_supabase_configured():
                    update_license_devices(key, devices, rec.get("queries_count", 0))

            self.send_json(200, {
                "valid": True,
                "plan": rec["plan"],
                "devices_bound": len(devices),
                "max_devices": max_devs
            })

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
                rec = lics.get(key)

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

                # Deduct quota and record anonymized telemetry only after verified upstream response
                rec["queries_count"] = cur_count + 1
                save_cloud_db(db)
                if is_supabase_configured():
                    update_license_devices(key, devices, rec["queries_count"])

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
                "app_version": str(telem_req.app_version or "2.9.6")
            }
            append_global_telemetry(telemetry_entry)
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

            # 3.2 Idempotencia Persistente
            event_id = str(data.get("meta", {}).get("event_id") or data.get("id") or data.get("data", {}).get("id") or "").strip()
            if not event_id:
                self.send_json(400, {"error": "Identificador de evento (event_id) ausente en payload."})
                return

            processed = db.setdefault("processed_webhook_events", [])
            if event_id in processed:
                self.send_json(200, {"status": "idempotent_duplicate_ignored", "event_id": event_id})
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
            lics[new_key] = record
            processed.append(event_id)
            if len(processed) > 5000:
                db["processed_webhook_events"] = processed[-5000:]
            save_cloud_db(db)

            if is_supabase_configured():
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


def run_cloud_server(port: int = 9988):
    srv = ThreadingHTTPServer(("0.0.0.0", port), OmniNetCloudProxyHandler)
    print(f"[OmniNet Cloud SaaS] Servidor de Licencias y Proxy DeepSeek escuchando en http://0.0.0.0:{port}")
    srv.serve_forever()


if __name__ == "__main__":
    p = int(os.environ.get("PORT", "9988"))
    run_cloud_server(p)

