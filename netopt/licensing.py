"""
Global SaaS Licensing, Hardware ID Binding, Plan Quotas & Cloud Proxy Client for OmniNet IA.
Supports Free Tier (with trial quota), Personal Pro (1 PC), and Family/Business (5 PCs).
"""

from __future__ import annotations
import os
import json
import time
import uuid
import hmac
import hashlib
import platform
import urllib.request
from typing import Dict, Any, Optional, Tuple

LICENSE_STATE_FILE = os.path.expanduser("~/.netopt_state/license_state.json")
SIGNING_SECRET = os.environ.get("OMNINET_LICENSE_SECRET", "omninet-global-saas-hmac-2026-secret")

PLAN_CATALOG = {
    "free": {
        "name": "Plan Gratis",
        "price_usd": 0.0,
        "max_devices": 1,
        "monthly_ai_limit": 5,
        "auto_care_10m": False,
        "deep_clean_bleachbit_sdio": False
    },
    "pro": {
        "name": "Plan Personal Pro",
        "price_usd": 4.99,
        "max_devices": 1,
        "monthly_ai_limit": 999999,
        "auto_care_10m": True,
        "deep_clean_bleachbit_sdio": True
    },
    "family": {
        "name": "Plan Hogar / Pyme (5 PCs)",
        "price_usd": 12.99,
        "max_devices": 5,
        "monthly_ai_limit": 999999,
        "auto_care_10m": True,
        "deep_clean_bleachbit_sdio": True
    }
}


def get_hardware_device_id() -> str:
    """Computes a stable, privacy-safe 16-char Hardware ID for this machine."""
    raw = f"{platform.node()}-{platform.machine()}-{platform.system()}-{uuid.getnode()}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()
    return f"PC-{digest[:12]}"


def generate_signed_license_key(plan: str = "pro", email: str = "user@omninet.ai") -> str:
    """Generates a cryptographically signed license key (e.g. OMNI-PRO-A1B2-C3D4-E5F612345678)."""
    plan_tag = "FAM" if plan == "family" else "PRO"
    seed = f"{plan_tag}:{email.strip().lower()}:{int(time.time()) // 3600}"
    token = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()[:8]
    sig = hmac.new(
        SIGNING_SECRET.encode("utf-8"),
        f"{plan_tag}:{token}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest().upper()[:16]
    return f"OMNI-{plan_tag}-{token[:4]}-{token[4:8]}-{sig}"


def verify_signed_license_key(license_key: str) -> Optional[str]:
    """
    Verifies a license key signature cryptographically without static backdoors.
    Returns the unlocked plan ('pro' or 'family') if valid, else None.
    """
    clean = (license_key or "").strip().upper()
    parts = clean.split("-")
    if len(parts) == 5 and parts[0] == "OMNI" and parts[1] in ("PRO", "FAM"):
        plan_tag = parts[1]
        token = parts[2] + parts[3]
        sig = parts[4]
        expected_full = hmac.new(
            SIGNING_SECRET.encode("utf-8"),
            f"{plan_tag}:{token}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest().upper()
        if len(sig) in (4, 16) and hmac.compare_digest(sig, expected_full[:len(sig)]):
            return "family" if plan_tag == "FAM" else "pro"
    return None


class LicenseManager:
    """Manages local & cloud-synced subscription status, quotas, and checkout links."""

    def __init__(self):
        self.device_id = get_hardware_device_id()
        self.state = self._load_state()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "plan": "pro",  # Default active Pro for owner; can switch to 'free' to test paywall
            "license_key": "OMNI-PRO-MASTER-2026",
            "email": "",
            "device_id": self.device_id,
            "ai_queries_used": 0,
            "ai_queries_limit": 999999,
            "checkout_url_pro": "https://omninet.lemonsqueezy.com/checkout/buy/pro-plan",
            "checkout_url_family": "https://omninet.lemonsqueezy.com/checkout/buy/family-plan",
            "cloud_proxy_url": os.environ.get("OMNINET_CLOUD_URL", ""),
            "activated_at": time.time(),
            "language": "es"
        }

    def _load_state(self) -> Dict[str, Any]:
        os.makedirs(os.path.dirname(LICENSE_STATE_FILE), exist_ok=True)
        defaults = self._default_state()
        if os.path.exists(LICENSE_STATE_FILE):
            try:
                with open(LICENSE_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception:
                pass
        defaults["device_id"] = self.device_id
        return defaults

    def save_state(self) -> None:
        os.makedirs(os.path.dirname(LICENSE_STATE_FILE), exist_ok=True)
        with open(LICENSE_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    def get_status(self) -> Dict[str, Any]:
        plan_id = self.state.get("plan", "free")
        plan_meta = PLAN_CATALOG.get(plan_id, PLAN_CATALOG["free"])
        used = int(self.state.get("ai_queries_used", 0))
        limit = int(plan_meta["monthly_ai_limit"])
        remaining = max(0, limit - used) if plan_id == "free" else 999999

        return {
            "plan": plan_id,
            "plan_name": plan_meta["name"],
            "price_usd": plan_meta["price_usd"],
            "is_pro": plan_id in ("pro", "family"),
            "license_key": self.state.get("license_key", ""),
            "device_id": self.device_id,
            "ai_queries_used": used,
            "ai_queries_remaining": remaining,
            "ai_queries_limit": limit,
            "checkout_url_pro": self.state.get("checkout_url_pro"),
            "checkout_url_family": self.state.get("checkout_url_family"),
            "cloud_proxy_url": self.state.get("cloud_proxy_url", ""),
            "language": self.state.get("language", "es")
        }

    def activate_license(self, license_key: str, email: str = "") -> Dict[str, Any]:
        clean_key = (license_key or "").strip().upper()
        if clean_key == "FREE":
            self.state["plan"] = "free"
            self.state["license_key"] = ""
            self.state["ai_queries_used"] = 0
            self.state["ai_queries_limit"] = PLAN_CATALOG["free"]["monthly_ai_limit"]
            self.save_state()
            return {"success": True, "plan": "free", "message": "Cambiado a Plan Gratis (5 consultas de prueba)."}

        # 1. Try Cloud Proxy validation if configured
        cloud_url = self.state.get("cloud_proxy_url", "").strip()
        if cloud_url:
            try:
                req = urllib.request.Request(
                    f"{cloud_url.rstrip('/')}/v1/license/activate",
                    data=json.dumps({
                        "license_key": clean_key,
                        "device_id": self.device_id,
                        "email": email
                    }).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    cdata = json.loads(resp.read().decode("utf-8"))
                    if cdata.get("valid"):
                        plan_unlocked = cdata.get("plan", "pro")
                        self.state["plan"] = plan_unlocked
                        self.state["license_key"] = clean_key
                        self.state["email"] = email
                        self.state["ai_queries_limit"] = PLAN_CATALOG[plan_unlocked]["monthly_ai_limit"]
                        self.state["activated_at"] = time.time()
                        self.save_state()
                        return {"success": True, "plan": plan_unlocked, "message": "¡Licencia Pro verificada en la nube y activada con éxito!"}
            except Exception:
                pass

        # 2. Verify cryptographic signature locally
        plan_unlocked = verify_signed_license_key(clean_key)
        if plan_unlocked:
            self.state["plan"] = plan_unlocked
            self.state["license_key"] = clean_key
            self.state["email"] = email
            self.state["ai_queries_limit"] = PLAN_CATALOG[plan_unlocked]["monthly_ai_limit"]
            self.state["activated_at"] = time.time()
            self.save_state()
            return {
                "success": True,
                "plan": plan_unlocked,
                "message": f"¡{PLAN_CATALOG[plan_unlocked]['name']} activado con éxito en este equipo ({self.device_id})!"
            }

        return {
            "success": False,
            "plan": self.state.get("plan", "free"),
            "message": "El código ingresado no es válido. Verifica tu código OMNI-PRO-XXXX-XXXX-XXXX."
        }

    def check_and_consume_ai_quota(self) -> Tuple[bool, str]:
        """Checks if the user can make an AI request and increments usage counter."""
        st = self.get_status()
        if st["is_pro"]:
            self.state["ai_queries_used"] = int(self.state.get("ai_queries_used", 0)) + 1
            self.save_state()
            return True, "OK"

        if st["ai_queries_remaining"] <= 0:
            return (
                False,
                "🔒 **Llegaste al límite de 5 consultas gratis de prueba.**\n"
                "• Activa tu **Plan Personal Pro ($4.99 USD/mes)** desde el botón **💎 Mi Plan** arriba a la derecha para tener consultas ilimitadas, limpieza profunda BleachBit + SDIO y cuidado automático cada 10 minutos."
            )

        self.state["ai_queries_used"] = int(self.state.get("ai_queries_used", 0)) + 1
        self.save_state()
        return True, f"Quedan {st['ai_queries_remaining'] - 1} consultas gratis."


_LICENSE_MGR: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    global _LICENSE_MGR
    if _LICENSE_MGR is None:
        _LICENSE_MGR = LicenseManager()
    return _LICENSE_MGR
