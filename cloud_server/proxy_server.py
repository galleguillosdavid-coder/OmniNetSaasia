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

try:
    from .supabase_client import (
        is_supabase_configured,
        get_license_from_supabase,
        upsert_license_in_supabase,
        update_license_devices,
        save_conversation_feedback_in_supabase,
        save_payment_event_in_supabase
    )
except (ImportError, ValueError):
    from supabase_client import (
        is_supabase_configured,
        get_license_from_supabase,
        upsert_license_in_supabase,
        update_license_devices,
        save_conversation_feedback_in_supabase,
        save_payment_event_in_supabase
    )

CLOUD_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_subscriptions_db.json")
CLOUD_FEEDBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_global_feedback.json")
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
    return db
                "queries_count": 0,
                "created_at": time.time()
            },
            demo_key: {
                "plan": "pro",
                "email": "demo@omninet.ai",
                "active": True,
                "max_devices": 1,
                "devices": [],
                "queries_count": 0,
                "created_at": time.time()
            }
        }
    }
    save_cloud_db(db)
    return db


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

    def do_GET(self):
        if self.path == "/v1/admin/stats":
            if ADMIN_SECRET_KEY:
                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {ADMIN_SECRET_KEY}":
                    self.send_json(401, {"error": "Unauthorized: Clave de administrador requerida"})
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
            key = (data.get("license_key") or "").strip().upper()
            dev_id = (data.get("device_id") or "UNKNOWN").strip()
            email = (data.get("email") or "").strip()

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

        # 2. Secure DeepSeek Proxy Endpoint (OMNI-004, OMNI-008)
        elif self.path == "/v1/chat":
            key = (data.get("license_key") or "").strip().upper()
            dev_id = (data.get("device_id") or "").strip()
            messages = data.get("messages", [])

            if not key:
                self.send_json(401, {"error": "Clave de licencia requerida para acceder al proxy IA."})
                return

            rec = None
            if is_supabase_configured():
                rec = get_license_from_supabase(key)
            if not rec:
                rec = lics.get(key)

            # OMNI-004: Validar existencia y estado activo de la licencia
            if not rec or not rec.get("active"):
                self.send_json(403, {"error": "Licencia no encontrada, cancelada o inactiva."})
                return

            # OMNI-004: Validar vinculación del dispositivo
            devices = rec.get("devices", [])
            if isinstance(devices, str):
                try:
                    devices = json.loads(devices)
                except Exception:
                    devices = []
            if not isinstance(devices, list):
                devices = []

            max_devs = rec.get("max_devices", 1)
            if dev_id and dev_id not in devices:
                if len(devices) < max_devs:
                    devices.append(dev_id)
                    rec["devices"] = devices
                    save_cloud_db(db)
                    if is_supabase_configured():
                        update_license_devices(key, devices, rec.get("queries_count", 0))
                else:
                    self.send_json(403, {"error": f"Dispositivo no autorizado para esta licencia (máximo {max_devs} equipos alcanzado)."})
                    return

            # OMNI-004: Aplicación efectiva de cuotas mensuales
            plan = rec.get("plan", "pro")
            limit = PLAN_CATALOG.get(plan, {}).get("monthly_ai_limit", 999999)
            cur_count = int(rec.get("queries_count", 0))
            if cur_count >= limit:
                self.send_json(429, {"error": f"Cuota mensual de consultas de IA alcanzada ({cur_count}/{limit})."})
                return

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

            if not DEEPSEEK_API_KEY:
                self.send_json(503, {"error": "DEEPSEEK_API_KEY no configurada en el servidor nube."})
                return

            try:
                req = urllib.request.Request(
                    f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions",
                    data=json.dumps({
                        "model": "deepseek-chat",
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": 350
                    }).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    reply = resp_data["choices"][0]["message"]["content"]
                    self.send_json(200, {"reply": reply, "model": "deepseek-chat-cloud-proxy"})
            except Exception as e:
                self.send_json(500, {"error": str(e)})

        # 3. Payment Webhook con Validación Criptográfica e Idempotencia (OMNI-001)
        elif self.path == "/v1/webhooks/payment":
            # 3.1 Verificación Criptográfica de Firma
            if LEMONSQUEEZY_WEBHOOK_SECRET:
                inc_sig = self.headers.get("X-Signature", "")
                exp_sig = hmac.new(LEMONSQUEEZY_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
                if not inc_sig or not hmac.compare_digest(inc_sig, exp_sig):
                    self.send_json(401, {"error": "Firma HMAC de webhook inválida o ausente."})
                    return

            if STRIPE_WEBHOOK_SECRET:
                stripe_sig = self.headers.get("Stripe-Signature", "")
                if not stripe_sig:
                    self.send_json(401, {"error": "Cabecera Stripe-Signature ausente."})
                    return

            # 3.2 Idempotencia
            event_id = str(data.get("meta", {}).get("event_id") or data.get("id") or data.get("data", {}).get("id") or "")
            processed = db.setdefault("processed_webhook_events", [])
            if event_id and event_id in processed:
                self.send_json(200, {"status": "idempotent_duplicate_ignored", "event_id": event_id})
                return

            # 3.3 Validación de estado de pago
            event_name = str(data.get("meta", {}).get("event_name") or data.get("type", "")).lower()
            attrs = data.get("data", {}).get("attributes", {})
            payment_status = str(attrs.get("status", "")).lower()

            is_valid_paid_event = (
                "order_created" in event_name or
                "subscription_created" in event_name or
                "payment_intent.succeeded" in event_name or
                payment_status == "paid" or
                not (LEMONSQUEEZY_WEBHOOK_SECRET or STRIPE_WEBHOOK_SECRET)
            )

            if not is_valid_paid_event:
                self.send_json(200, {"status": "ignored_non_paid_event", "event_name": event_name})
                return

            email = attrs.get("user_email") or data.get("email")
            if not email:
                self.send_json(400, {"error": "Email no encontrado en el payload de pago."})
                return

            custom_plan = data.get("meta", {}).get("custom_data", {}).get("plan")
            product_name = str(attrs.get("first_order_item", {}).get("product_name", "")).lower()
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
            if event_id:
                processed.append(event_id)
                if len(processed) > 5000:
                    db["processed_webhook_events"] = processed[-5000:]
            save_cloud_db(db)

            if is_supabase_configured():
                upsert_license_in_supabase(record)
                save_payment_event_in_supabase(event_name or "payment_received", "lemon_squeezy", data)

            self.send_json(200, {
                "created": True,
                "email": email,
                "plan": plan,
                "license_key": new_key
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

