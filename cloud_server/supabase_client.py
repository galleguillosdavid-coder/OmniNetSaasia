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


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY", "")


def is_supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def _supabase_request(endpoint: str, method: str = "GET", body: Optional[Dict[str, Any]] = None, query_params: Optional[Dict[str, str]] = None) -> Any:
    if not is_supabase_configured():
        return None

    url = f"{SUPABASE_URL}/rest/v1/{endpoint.lstrip('/')}"
    if query_params:
        url += "?" + urllib.parse.urlencode(query_params)

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
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

