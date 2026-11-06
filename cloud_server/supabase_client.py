"""
OmniNet Supabase Client (Zero-Dependency REST API Connector).
Interacts directly with Supabase PostgREST API using standard urllib.
"""

from __future__ import annotations
import os
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List


def _load_env_if_present() -> None:
    env_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    ]
    for p in env_paths:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k, v = k.strip(), v.strip().strip("'\"")
                            if k not in os.environ and v:
                                os.environ[k] = v
            except Exception:
                pass


_load_env_if_present()


def get_supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def get_supabase_backend_key() -> str:
    """Returns the privileged Service Role Key for backend server operations (OMNI-023)."""
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def get_supabase_client_key() -> str:
    """Returns the unprivileged Anon / Publishable key for public client reads (OMNI-023)."""
    return os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")


def get_supabase_key(require_service_role: bool = False) -> str:
    """
    OMNI-023: Explicitly separates backend server credentials from public client credentials.
    Backend write operations require service-role to avoid unexpected RLS write drops.
    """
    srv = get_supabase_backend_key()
    if srv:
        return srv
    if require_service_role:
        return ""
    return get_supabase_client_key()


def is_supabase_configured(require_backend: bool = False) -> bool:
    url = get_supabase_url()
    key = get_supabase_key(require_service_role=require_backend)
    return bool(url and key)


def _supabase_request(endpoint: str, method: str = "GET", body: Optional[Dict[str, Any]] = None, query_params: Optional[Dict[str, str]] = None) -> Any:
    if not is_supabase_configured():
        return None

    sb_url = get_supabase_url()
    sb_key = get_supabase_key()

    url = f"{sb_url}/rest/v1/{endpoint.lstrip('/')}"
    if query_params:
        url += "?" + urllib.parse.urlencode(query_params)

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        },
        method=method
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else []
    except Exception as e:
        print(f"[Supabase Client Error] {endpoint}: {e}", flush=True)
        return None


def get_license_from_supabase(license_key: str) -> Optional[Dict[str, Any]]:
    """Fetches a license by license_key from Supabase."""
    res = _supabase_request("licenses", method="GET", query_params={"license_key": f"eq.{license_key}", "limit": "1"})
    if isinstance(res, list) and len(res) > 0:
        return res[0]
    return None


def upsert_license_in_supabase(license_data: Dict[str, Any]) -> bool:
    """Inserts or updates a license record in Supabase."""
    res = _supabase_request(
        "licenses",
        method="POST",
        body=license_data,
        query_params={"on_conflict": "license_key"}
    )
    return res is not None


def update_license_devices(license_key: str, devices: List[str], queries_count: int) -> bool:
    """Updates device bindings and query counts."""
    res = _supabase_request(
        "licenses",
        method="PATCH",
        body={"devices": devices, "queries_count": queries_count, "updated_at": "now()"},
        query_params={"license_key": f"eq.{license_key}"}
    )
    return res is not None


def save_conversation_feedback_in_supabase(entry: Dict[str, Any]) -> bool:
    """Saves anonymous conversational feedback to Supabase."""
    res = _supabase_request("conversations_feedback", method="POST", body=entry)
    return res is not None


def save_payment_event_in_supabase(event_type: str, provider: str, payload: Dict[str, Any]) -> bool:
    """Logs payment webhooks in Supabase."""
    res = _supabase_request("payment_events", method="POST", body={
        "event_type": event_type,
        "provider": provider,
        "payload": payload
    })
    return res is not None

