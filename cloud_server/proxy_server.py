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
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from netopt.licensing import generate_signed_license_key, verify_signed_license_key, PLAN_CATALOG

CLOUD_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_subscriptions_db.json")
CLOUD_FEEDBACK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cloud_global_feedback.json")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


def load_cloud_db() -> Dict[str, Any]:
    if os.path.exists(CLOUD_DB_FILE):
        try:
            with open(CLOUD_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Seed with a master demo license
    demo_key = generate_signed_license_key("pro", "founder@omninet.ai")
    db = {
        "licenses": {
            "OMNI-PRO-MASTER-2026": {
                "plan": "pro",
                "email": "founder@omninet.ai",
                "active": True,
                "max_devices": 5,
                "devices": [],
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
            db = load_cloud_db()
            lics = db.get("licenses", {})
            self.send_json(200, {
                "service": "OmniNet Global Cloud Proxy",
                "total_licenses": len(lics),
                "active_licenses": sum(1 for v in lics.values() if v.get("active")),
                "total_queries_proxied": sum(v.get("queries_count", 0) for v in lics.values()),
                "sample_keys": list(lics.keys())[:5]
            })
        else:
            self.send_json(200, {"status": "online", "service": "OmniNet Global SaaS Cloud Proxy"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        db = load_cloud_db()
        lics = db.setdefault("licenses", {})

        # 1. License Activation & Hardware ID Binding
        if self.path == "/v1/license/activate":
            key = (data.get("license_key") or "").strip().upper()
            dev_id = (data.get("device_id") or "UNKNOWN").strip()
            email = (data.get("email") or "").strip()

            rec = lics.get(key)
            if not rec:
                plan_sig = verify_signed_license_key(key)
                if plan_sig:
                    rec = {
                        "plan": plan_sig,
                        "email": email,
                        "active": True,
                        "max_devices": PLAN_CATALOG[plan_sig]["max_devices"],
                        "devices": [],
                        "queries_count": 0,
                        "created_at": time.time()
                    }
                    lics[key] = rec

            if not rec or not rec.get("active"):
                self.send_json(403, {"valid": False, "error": "Licencia inválida o inactiva"})
                return

            devices = rec.setdefault("devices", [])
            if dev_id not in devices:
                if len(devices) >= rec.get("max_devices", 1):
                    self.send_json(403, {
                        "valid": False,
                        "error": f"Esta licencia ya alcanzó el límite de {rec.get('max_devices', 1)} computador(es)."
                    })
                    return
                devices.append(dev_id)
                save_cloud_db(db)

            self.send_json(200, {
                "valid": True,
                "plan": rec["plan"],
                "devices_bound": len(devices),
                "max_devices": rec.get("max_devices", 1)
            })

        # 2. Secure DeepSeek Proxy Endpoint (hides API key from client EXE)
        elif self.path == "/v1/chat":
            key = (data.get("license_key") or "").strip().upper()
            dev_id = (data.get("device_id") or "").strip()
            messages = data.get("messages", [])

            rec = lics.get(key)
            plan_sig = verify_signed_license_key(key)
            if not rec and not plan_sig:
                self.send_json(402, {"error": "Suscripción Pro requerida para usar el proxy IA en la nube."})
                return

            if rec:
                rec["queries_count"] = rec.get("queries_count", 0) + 1
                save_cloud_db(db)

            append_global_feedback({
                "timestamp": time.time(),
                "device_id": dev_id,
                "user_message": messages[-1].get("content", "")[:250] if messages else ""
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

        # 3. Payment Webhook (Lemon Squeezy / Stripe) -> Generates License Automatically
        elif self.path == "/v1/webhooks/payment":
            email = data.get("email") or data.get("data", {}).get("attributes", {}).get("user_email") or "buyer@omninet.ai"
            plan = data.get("plan", "pro")
            if plan not in ("pro", "family"):
                plan = "pro"
            new_key = generate_signed_license_key(plan, email)
            lics[new_key] = {
                "plan": plan,
                "email": email,
                "active": True,
                "max_devices": PLAN_CATALOG[plan]["max_devices"],
                "devices": [],
                "queries_count": 0,
                "created_at": time.time()
            }
            save_cloud_db(db)
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

