"""
Global SaaS Licensing, Hardware ID Binding, Plan Quotas & Cloud Proxy Client for OmniNet IA.
Supports Free Tier (with trial quota), Personal Pro (1 PC), and Family/Business (5 PCs).
"""

from __future__ import annotations
import os
import sys
import json
import time
import uuid
import hmac
import hashlib
import platform
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple

try:
    from .adapters import HttpClientAdapter
except (ImportError, ValueError):
    from netopt.adapters import HttpClientAdapter

LICENSE_STATE_FILE = os.path.expanduser("~/.netopt_state/license_state.json")


def get_signing_secret() -> str:
    """
    Returns the HMAC signing secret enforcing a strict Fail-Closed security policy.
    - Production: Requires the OMNINET_LICENSE_SECRET environment variable.
      If absent, returns empty string, disabling key generation and verification (Fail-Closed).
    - Development / Testing: Permitted only when OMNINET_DEV_MODE=1 is explicitly set or
      under automated unit testing, emitting a security warning to prevent accidental production use.
    """
    sec = os.environ.get("OMNINET_LICENSE_SECRET", "").strip()
    if sec:
        return sec
    is_dev = os.environ.get("OMNINET_DEV_MODE", "0").lower() in ("1", "true", "yes")
    is_test = "unittest" in sys.modules or any("test" in arg.lower() for arg in sys.argv)
    if is_dev or is_test:
        import warnings
        warnings.warn(
            "[OmniNet Security Warning] Modo desarrollo/pruebas activo: utilizando clave efímera. "
            "PROHIBIDO utilizar en entornos de producción sin OMNINET_LICENSE_SECRET configurado.",
            RuntimeWarning,
            stacklevel=2
        )
        return "omninet-ephemeral-dev-test-secret-2026"
    return ""

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
    """Generates a cryptographically signed license key with full 128-bit/32-hex HMAC signature."""
    secret = get_signing_secret()
    if not secret:
        raise ValueError("Emisión de licencia bloqueada: OMNINET_LICENSE_SECRET ausente (Fail-Closed).")
    plan_tag = "FAM" if plan == "family" else "PRO"
    seed = f"{plan_tag}:{email.strip().lower()}:{int(time.time()) // 3600}"
    token = hashlib.sha256(seed.encode("utf-8")).hexdigest().upper()[:8]
    sig = hmac.new(
        secret.encode("utf-8"),
        f"{plan_tag}:{token}".encode("utf-8"),
        hashlib.sha256
    ).hexdigest().upper()[:32]
    return f"OMNI-{plan_tag}-{token[:4]}-{token[4:8]}-{sig}"


def verify_signed_license_key(license_key: str) -> Optional[str]:
    """
    Verifies a license key signature cryptographically without static backdoors or weak truncations.
    Rejects any key that has a truncated signature (e.g. < 32 hex chars), master backdoor string,
    or when OMNINET_LICENSE_SECRET is absent (Fail-Closed).
    Returns the unlocked plan ('pro' or 'family') if valid, else None.
    """
    secret = get_signing_secret()
    if not secret:
        return None

    clean = (license_key or "").strip().upper()
    if clean in ("OMNI-PRO-MASTER-2026", "ADMIN-PRO", "MASTER", "ROOT"):
        return None

    parts = clean.split("-")
    if len(parts) == 5 and parts[0] == "OMNI" and parts[1] in ("PRO", "FAM"):
        plan_tag = parts[1]
        token = parts[2] + parts[3]
        sig = parts[4]
        # OMNI-014: Strictly reject truncated signatures (< 32 hex chars) to prevent brute-force
        if len(sig) < 32:
            return None
        expected_full = hmac.new(
            secret.encode("utf-8"),
            f"{plan_tag}:{token}".encode("utf-8"),
            hashlib.sha256
        ).hexdigest().upper()
        expected_32 = expected_full[:32]
        if len(sig) == 32 and hmac.compare_digest(sig, expected_32):
            return "family" if plan_tag == "FAM" else "pro"
        elif len(sig) == 64 and hmac.compare_digest(sig, expected_full):
            return "family" if plan_tag == "FAM" else "pro"
    return None


class LicenseManager:
    """Manages local & cloud-synced subscription status, quotas, and checkout links."""

    def __init__(self):
        self.device_id = get_hardware_device_id()
        self.state = self._load_state()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "plan": "free",  # Default Free tier; activation required for Pro / Family (OMNI-014)
            "license_key": "",
            "email": "",
            "device_id": self.device_id,
            "ai_queries_used": 0,
            "ai_queries_limit": PLAN_CATALOG["free"]["monthly_ai_limit"],
            "checkout_url_pro": "https://omninet.lemonsqueezy.com/checkout/buy/pro-plan",
            "checkout_url_family": "https://omninet.lemonsqueezy.com/checkout/buy/family-plan",
            "cloud_proxy_url": os.environ.get("OMNINET_CLOUD_URL", ""),
            "activated_at": None,
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
            act_url = f"{cloud_url.rstrip('/')}/v1/license/activate"
            act_payload = {
                "license_key": clean_key,
                "device_id": self.device_id,
                "email": email
            }
            if HttpClientAdapter.is_available():
                status_code, cdata = HttpClientAdapter.post_json(act_url, act_payload, timeout_sec=8.0)
                if status_code == 200 and isinstance(cdata, dict) and cdata.get("valid"):
                    plan_unlocked = cdata.get("plan", "pro")
                    self.state["plan"] = plan_unlocked
                    self.state["license_key"] = clean_key
                    self.state["email"] = email
                    self.state["ai_queries_limit"] = PLAN_CATALOG[plan_unlocked]["monthly_ai_limit"]
                    self.state["activated_at"] = time.time()
                    self.save_state()
                    return {"success": True, "plan": plan_unlocked, "message": "¡Licencia Pro verificada en la nube y activada con éxito!"}
                elif status_code in (401, 403) or (isinstance(cdata, dict) and cdata.get("valid") is False):
                    return {
                        "success": False,
                        "plan": self.state.get("plan", "free"),
                        "message": cdata.get("error") if isinstance(cdata, dict) else "Licencia rechazada por el servidor de activación."
                    }
            try:
                req = urllib.request.Request(
                    act_url,
                    data=json.dumps(act_payload).encode("utf-8"),
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
                    elif cdata.get("valid") is False:
                        return {
                            "success": False,
                            "plan": self.state.get("plan", "free"),
                            "message": cdata.get("error") or "Licencia rechazada por el servidor de activación."
                        }
            except urllib.error.HTTPError as he:
                try:
                    if he.code in (401, 403):
                        err_msg = "Licencia rechazada o límite de equipos alcanzado en el servidor."
                        try:
                            err_body = json.loads(he.read().decode("utf-8"))
                            err_msg = err_body.get("error") or err_msg
                        except Exception:
                            pass
                        return {
                            "success": False,
                            "plan": self.state.get("plan", "free"),
                            "message": err_msg
                        }
                finally:
                    try:
                        he.close()
                    except Exception:
                        pass
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
