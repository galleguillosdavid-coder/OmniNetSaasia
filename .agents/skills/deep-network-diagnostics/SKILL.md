---
name: deep-network-diagnostics
description: >-
  Use this skill when performing deep network telemetry across OSI layers L1-L7:
  gateway/internet reachability, RFC 3550 jitter, bufferbloat grading, DF-bit
  binary-search Path MTU discovery, active TCP/UDP socket state inspection,
  Zero-Trust Gateway MAC locking (ARP spoofing detection), Wi-Fi 7 MLO radio quality,
  and DNS-over-QUIC (DoQ RFC 9250) telemetry.
---

# Deep Network Diagnostics (L1–L7)

Provides non-destructive deep telemetry across physical/link, IP/MTU, transport sockets, and next-gen DNS resolution.

## Available Diagnostic Routines

### 1. Full L1-L7 Sweep + Bufferbloat + DNS Anycast Ranking
```powershell
python -c "from netopt.diagnostics import run_full_diagnostics; import json; d=run_full_diagnostics(); print(json.dumps({'health': d.overall_health.value, 'gw': d.default_gateway, 'bloat': d.bufferbloat_grade, 'anomalies': d.anomalies}, indent=2))"
```

### 2. Wi-Fi 7 (802.11be) MLO Radio & Physical Adapter Audit
```powershell
python -c "from netopt.diagnostics import inspect_wifi_and_nic; import json; print(json.dumps(inspect_wifi_and_nic(), indent=2, ensure_ascii=False))"
```
*Detecta bandas 2.4/5/6 GHz, intensidad RSSI %, tasas PHY (Tx/Rx) y compatibilidad Multi-Link Operation (MLO).*

### 3. Zero-Trust Gateway MAC Locking & ARP Radar
```powershell
python -c "from netopt.diagnostics import audit_lan_radar_devices; import json; print(json.dumps(audit_lan_radar_devices(), indent=2, ensure_ascii=False))"
```
*Bloquea la MAC confiable del router en `~/.netopt_state/trusted_gateway.json` y alerta de inmediato si un atacante intenta suplantar la puerta de enlace (ARP Spoofing / MitM).*

### 4. DNS over QUIC (DoQ - RFC 9250) & DoH Inspection
```powershell
# Verificar soporte de DoQ (UDP puerto 853 / 0-RTT)
python -c "from netopt.diagnostics import check_doq_status; import json; print(json.dumps(check_doq_status('9.9.9.9'), indent=2, ensure_ascii=False))"

# Inspeccionar cifrado DoH nativo (Cloudflare, Google, Quad9)
python -c "from netopt.diagnostics import check_doh_status; import json; print(json.dumps(check_doh_status(), indent=2, ensure_ascii=False))"
```

### 5. Binary-Search Path MTU (PMTU) & ICMP Filtering Check
```powershell
python -c "from netopt.diagnostics import discover_path_mtu; import json; print(json.dumps(discover_path_mtu('1.1.1.1'), indent=2))"
```

### 6. Active Socket & Port Exhaustion Audit (`TIME_WAIT` / `CLOSE_WAIT`)
```powershell
python -c "from netopt.diagnostics import inspect_active_sockets; import json; print(json.dumps(inspect_active_sockets(), indent=2))"
```

### 7. Micro Internet & Decentralized Identity (DID) Mesh Telemetry
```powershell
python -c "from netopt.micro_internet import get_micro_internet_orchestrator; import json; print(json.dumps(get_micro_internet_orchestrator().get_mesh_status(), indent=2, ensure_ascii=False))"
```
*Inspecciona la identidad criptográfica DID del dispositivo, nodos descubiertos en el hogar/oficina, interfaces multipath activas y estado de la red cooperativa P2P para intercambio multimedia sin nube.*
