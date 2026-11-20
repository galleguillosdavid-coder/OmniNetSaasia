"""
AI-Era Cyber Defense & Threat Triage Engine (`netopt/ai_defense.py`).
Defends endpoints and LANs against AI-driven threats:
  1. Suspicious outbound connections / C2 beaconing from temp-dir processes (via psutil).
  2. Exposed wildcard listeners (`0.0.0.0` / `::`) and ARP spoofing cross-check.
  3. AI-crafted phishing URL / Punycode (`xn--`) / lookalike domain inspection.
"""

from __future__ import annotations
import ipaddress
import os
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from .diagnostics import audit_arp_lan


_TEMP_PATH_MARKERS = ("\\temp\\", "\\tmp\\", "/tmp/", "\\appdata\\local\\temp\\")
_COMMON_BRANDS = (
    "google", "microsoft", "apple", "paypal", "amazon", "netflix",
    "mercadopago", "binance", "github", "cloudflare", "whatsapp", "instagram",
)
_RISKY_TLDS = (".zip", ".mov", ".top", ".xyz", ".click", ".gq", ".tk", ".ml", ".cf")


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def inspect_url_or_domain(raw_input: str) -> Dict[str, Any]:
    """Analyzes a URL or domain for AI-phishing traits (Punycode, lookalikes, IP-host, risky TLDs)."""
    text = (raw_input or "").strip()
    if not text:
        return {"verdict": "INVALID", "risk_score": 0, "reasons": ["Ingresa una URL o dominio válido."]}

    candidate = text if "://" in text else f"https://{text}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        return {"verdict": "INVALID", "risk_score": 0, "reasons": ["No se pudo extraer un dominio válido."]}

    reasons: List[str] = []
    score = 0

    if "xn--" in host:
        score += 45
        reasons.append("Usa codificación Punycode (xn--), técnica común en ataques de dominios homógrafos.")

    try:
        ipaddress.ip_address(host)
        score += 40
        reasons.append("Apunta directamente a una dirección IP en lugar de un dominio verificado.")
    except ValueError:
        pass

    if any(host.endswith(tld) for tld in _RISKY_TLDS):
        score += 20
        reasons.append("Utiliza una extensión de dominio frecuentemente usada en campañas de phishing.")

    labels = [lbl for lbl in host.split(".") if lbl]
    if len(labels) >= 5:
        score += 20
        reasons.append("Exceso de subdominios diseñado para ocultar el dominio real.")

    sld = labels[-2] if len(labels) >= 2 else labels[0]
    sld_norm = sld.translate(str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a"}))
    for brand in _COMMON_BRANDS:
        if sld != brand and (
            _levenshtein(sld, brand) == 1
            or _levenshtein(sld_norm, brand) <= 1
            or (brand in sld and len(sld) > len(brand))
            or (brand in sld_norm and len(sld_norm) > len(brand))
        ):
            score += 45
            reasons.append(f"Posible suplantación visual (typosquatting/homoglifo) de '{brand}'.")
            break

    if parsed.scheme == "http":
        score += 15
        reasons.append("Conexión sin cifrado HTTPS.")

    score = min(100, score)
    if score >= 50:
        verdict = "DANGEROUS"
    elif score >= 20:
        verdict = "SUSPICIOUS"
    else:
        verdict = "SAFE"
        if not reasons:
            reasons.append("No se detectaron señales típicas de phishing o suplantación.")

    return {
        "input": text,
        "host": host,
        "verdict": verdict,
        "risk_score": score,
        "reasons": reasons,
    }


def audit_ai_threats() -> Dict[str, Any]:
    """
    Performs a non-destructive endpoint + LAN audit for AI-driven attack indicators:
    - Processes executing from temp folders with active outbound connections.
    - Unnecessary wildcard listening sockets (`0.0.0.0` / `::`).
    - LAN ARP spoofing / gateway impersonation.
    """
    findings: List[Dict[str, Any]] = []
    risk_score = 0
    temp_net_procs: List[Dict[str, Any]] = []
    wildcard_listeners: List[Dict[str, Any]] = []

    try:
        import psutil
        seen_pids = set()
        for conn in psutil.net_connections(kind="inet"):
            status = getattr(conn, "status", "")
            laddr = getattr(conn, "laddr", None)
            raddr = getattr(conn, "raddr", None)
            pid = getattr(conn, "pid", None)

            if status == "LISTEN" and laddr and getattr(laddr, "ip", "") in ("0.0.0.0", "::"):
                if len(wildcard_listeners) < 15:
                    wildcard_listeners.append({"port": getattr(laddr, "port", 0), "pid": pid})

            if status == "ESTABLISHED" and raddr and pid and pid not in seen_pids:
                seen_pids.add(pid)
                try:
                    proc = psutil.Process(pid)
                    exe = (proc.exe() or "").lower()
                    if any(marker in exe for marker in _TEMP_PATH_MARKERS):
                        temp_net_procs.append({
                            "pid": pid,
                            "name": proc.name(),
                            "exe": proc.exe(),
                            "remote_ip": getattr(raddr, "ip", ""),
                            "remote_port": getattr(raddr, "port", 0),
                        })
                except Exception:
                    continue
    except Exception as exc:
        findings.append({"severity": "LOW", "type": "telemetry_limited", "detail": str(exc)})

    if temp_net_procs:
        risk_score += min(60, 30 * len(temp_net_procs))
        findings.append({
            "severity": "HIGH",
            "type": "temp_process_beaconing",
            "detail": f"{len(temp_net_procs)} proceso(s) ejecutándose desde carpetas temporales con conexión externa activa.",
            "processes": temp_net_procs[:5],
        })

    if len(wildcard_listeners) >= 10:
        risk_score += 15
        findings.append({
            "severity": "MEDIUM",
            "type": "exposed_wildcard_ports",
            "detail": f"{len(wildcard_listeners)} puertos escuchando en todas las interfaces (0.0.0.0/::).",
            "ports": [w["port"] for w in wildcard_listeners[:10]],
        })

    arp_res = audit_arp_lan()
    arp_anomalies = arp_res.get("anomalies", [])
    if arp_anomalies:
        risk_score += 45
        findings.append({
            "severity": "HIGH",
            "type": "arp_lan_anomaly",
            "detail": f"Anomalía ARP detectada en la red local: {arp_anomalies[0]}",
        })

    risk_score = min(100, risk_score)
    if risk_score >= 50:
        threat_level = "HIGH"
    elif risk_score >= 20:
        threat_level = "ELEVATED"
    else:
        threat_level = "LOW"

    return {
        "threat_level": threat_level,
        "risk_score": risk_score,
        "temp_network_processes": temp_net_procs,
        "wildcard_listeners_count": len(wildcard_listeners),
        "arp_anomalies_count": len(arp_anomalies),
        "findings": findings,
        "summary": (
            "Tu equipo y red local no muestran señales de intrusión o beaconing automatizado."
            if not findings else
            f"Se detectaron {len(findings)} alerta(s) de seguridad que conviene revisar."
        ),
    }
