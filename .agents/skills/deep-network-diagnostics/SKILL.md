---
name: deep-network-diagnostics
description: >-
  Use this skill when performing deep network telemetry across OSI layers L1-L7:
  gateway/internet reachability, RFC 3550 jitter, bufferbloat grading, DF-bit
  binary-search Path MTU discovery, active TCP/UDP socket state inspection,
  and local LAN ARP conflict/spoofing auditing.
---

# Deep Network Diagnostics (L1–L7)

Provides non-destructive deep telemetry across physical/link, IP/MTU, transport sockets, and DNS resolution.

## Commands

1. **Full L1-L7 Sweep + Bufferbloat + DNS Ranking**:
   ```powershell
   python -c "from netopt.diagnostics import run_full_diagnostics; import json; d=run_full_diagnostics(); print(json.dumps({'health': d.overall_health.value, 'gw': d.default_gateway, 'bloat': d.bufferbloat_grade, 'anomalies': d.anomalies}, indent=2))"
   ```

2. **Active Socket & Port Exhaustion Audit (`TIME_WAIT` / `CLOSE_WAIT`)**:
   ```powershell
   python -c "from netopt.diagnostics import inspect_active_sockets; import json; print(json.dumps(inspect_active_sockets(), indent=2))"
   ```

3. **Binary-Search Path MTU (PMTU) Discovery**:
   ```powershell
   python -c "from netopt.diagnostics import discover_path_mtu; import json; print(json.dumps(discover_path_mtu('1.1.1.1'), indent=2))"
   ```

4. **Local LAN ARP & Duplicate MAC Audit**:
   ```powershell
   python -c "from netopt.diagnostics import audit_arp_lan; import json; print(json.dumps(audit_arp_lan(), indent=2))"
   ```

