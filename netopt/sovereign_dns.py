"""
Sovereign Local DNS Forwarder & Real-Time AI Phishing Sinkhole (`netopt/sovereign_dns.py`).
Listens on 127.0.0.1 (default port 5353, or 53 when elevated), inspects queried domains
in real time against `ai_defense.inspect_url_or_domain()`, blocks DANGEROUS phishing/homoglyph
domains with NXDOMAIN, and forwards safe queries over encrypted DNS-over-HTTPS (RFC 8484).
"""

from __future__ import annotations
import socket
import struct
import threading
import time
import urllib.request
from typing import Any, Dict, Optional, Tuple

from .ai_defense import inspect_url_or_domain

DEFAULT_DOH_UPSTREAM = "https://1.1.1.1/dns-query"
FALLBACK_DOH_UPSTREAM = "https://dns.google/dns-query"


def extract_dns_qname(packet: bytes) -> str:
    """Extracts the first queried domain name from a raw RFC 1035 DNS packet."""
    if not isinstance(packet, (bytes, bytearray)) or len(packet) < 13:
        return ""
    idx = 12
    labels = []
    while idx < len(packet):
        length = packet[idx]
        if length == 0:
            break
        if (length & 0xC0) == 0xC0:
            break
        idx += 1
        if idx + length > len(packet):
            return ""
        labels.append(packet[idx:idx + length].decode("ascii", errors="ignore"))
        idx += length
    return ".".join(lbl for lbl in labels if lbl).lower()


def build_nxdomain_response(query_packet: bytes) -> bytes:
    """Builds a minimal RFC 1035 NXDOMAIN (RCODE=3) reply preserving transaction ID and question."""
    if len(query_packet) < 12:
        return b""
    txid = query_packet[:2]
    # QR=1, Opcode=0, AA=0, TC=0, RD=1 | RA=1, Z=0, RCODE=3 (NXDOMAIN)
    flags = struct.pack(">H", 0x8183)
    qdcount = query_packet[4:6]
    header = txid + flags + qdcount + b"\x00\x00\x00\x00\x00\x00"
    idx = 12
    while idx < len(query_packet) and query_packet[idx] != 0:
        if (query_packet[idx] & 0xC0) == 0xC0:
            idx += 1
            break
        idx += 1 + query_packet[idx]
    q_end = min(len(query_packet), idx + 5)  # zero byte + QTYPE(2) + QCLASS(2)
    return header + query_packet[12:q_end]


class SovereignDNSServer:
    """Local encrypted DoH forwarder with real-time AI phishing/homoglyph domain sinkholing."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5353,
        upstream_doh: str = DEFAULT_DOH_UPSTREAM,
        cache_ttl_sec: float = 60.0,
        fallback_doh: str = FALLBACK_DOH_UPSTREAM,
    ):
        self.host = host
        self.port = int(port)
        self.upstream_doh = upstream_doh
        self.fallback_doh = fallback_doh
        self.cache_ttl_sec = max(0.0, float(cache_ttl_sec))
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.RLock()
        self._cache: Dict[bytes, Tuple[float, bytes]] = {}
        self.queries_total = 0
        self.blocked_total = 0
        self.cache_hits = 0
        self.upstream_failovers = 0
        self.last_blocked_domain = ""

    def _forward_doh(self, query_packet: bytes) -> Optional[bytes]:
        upstreams = [self.upstream_doh]
        if self.fallback_doh and self.fallback_doh != self.upstream_doh:
            upstreams.append(self.fallback_doh)
        for idx, url in enumerate(upstreams):
            req = urllib.request.Request(
                url,
                data=query_packet,
                headers={
                    "Content-Type": "application/dns-message",
                    "Accept": "application/dns-message",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if idx > 0:
                        with self._lock:
                            self.upstream_failovers += 1
                    return resp.read()
            except Exception:
                continue
        return None

    def handle_packet(self, query_packet: bytes) -> Tuple[bytes, bool, str]:
        """Inspects a raw DNS query, sinkholes DANGEROUS domains, or forwards via DoH."""
        qname = extract_dns_qname(query_packet)
        with self._lock:
            self.queries_total += 1
        if qname:
            verdict = inspect_url_or_domain(f"https://{qname}")
            if verdict.get("verdict") == "DANGEROUS":
                with self._lock:
                    self.blocked_total += 1
                    self.last_blocked_domain = qname
                return build_nxdomain_response(query_packet), True, qname

        cache_key = bytes(query_packet[12:]) if len(query_packet) > 12 else b""
        now = time.time()
        if cache_key and self.cache_ttl_sec > 0:
            with self._lock:
                hit = self._cache.get(cache_key)
                if hit and hit[0] > now and len(hit[1]) >= 2:
                    self.cache_hits += 1
                    return bytes(query_packet[:2]) + hit[1][2:], False, qname

        reply = self._forward_doh(query_packet)
        if reply:
            if cache_key and self.cache_ttl_sec > 0 and len(reply) >= 12:
                with self._lock:
                    if len(self._cache) >= 512:
                        self._cache.clear()
                    self._cache[cache_key] = (now + self.cache_ttl_sec, reply)
            return reply, False, qname
        return build_nxdomain_response(query_packet), False, qname

    def _serve_loop(self) -> None:
        while self._running and self._sock is not None:
            try:
                data, addr = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            reply, _, _ = self.handle_packet(data)
            if reply and self._sock is not None:
                try:
                    self._sock.sendto(reply, addr)
                except OSError:
                    pass

    def start(self, execute: bool = False) -> Dict[str, Any]:
        if self._running:
            return {"success": True, "already_running": True, **self.status()}
        if execute is not True:
            return {"success": True, "simulated": True, "action": "start_sovereign_dns", **self.status()}
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.5)
        bound = False
        for candidate_port in (self.port, 53553, 0):
            try:
                sock.bind((self.host, candidate_port))
                bound = True
                break
            except OSError:
                continue
        if not bound:
            sock.close()
            return {"success": False, "simulated": False, "error": "No se pudo enlazar ningún puerto UDP para DNS Soberano."}
        self.port = sock.getsockname()[1]
        self._sock = sock
        self._running = True
        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()
        return {"success": True, "simulated": False, **self.status()}

    def stop(self, execute: bool = False) -> Dict[str, Any]:
        if execute is not True:
            return {"success": True, "simulated": True, "action": "stop_sovereign_dns", **self.status()}
        self._running = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        return {"success": True, "simulated": False, **self.status()}

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "listen": f"{self.host}:{self.port}",
                "upstream_doh": self.upstream_doh,
                "queries_total": self.queries_total,
                "blocked_total": self.blocked_total,
                "cache_hits": self.cache_hits,
                "last_blocked_domain": self.last_blocked_domain,
            }


_SOVEREIGN_DNS_SINGLETON: Optional[SovereignDNSServer] = None


def get_sovereign_dns() -> SovereignDNSServer:
    global _SOVEREIGN_DNS_SINGLETON
    if _SOVEREIGN_DNS_SINGLETON is None:
        _SOVEREIGN_DNS_SINGLETON = SovereignDNSServer()
    return _SOVEREIGN_DNS_SINGLETON
