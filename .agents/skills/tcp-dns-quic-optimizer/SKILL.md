---
name: tcp-dns-quic-optimizer
description: >-
  Use this skill to generate, apply, verify, or roll back OS-level TCP stack
  optimizations (Autotuning, RSS, RSC, BBR, FQ), L4S/AccECN congestion tuning,
  Windows QoS bandwidth release (NonBestEffortLimit=0), Hardware Task Offload (DisableTaskOffload=0),
  MTU Black Hole mitigation (RFC 4821 PLPMTUD), Anycast DoH encryption (Cloudflare/Google/Quad9 ECH),
  and hierarchical L1-L7 triage repairs under strict Zero NetLoss safety invariants.
---

# TCP, DNS & Triage Optimizer (Zero NetLoss)

Applies cross-platform network stack tuning, congestion signaling, and hierarchical self-healing with mandatory pre-action snapshots and post-action verification gates.

## Optimization Workflows

### 1. Ultra-Low Latency Gaming & L4S/QoS Tuning
```powershell
python -c "from netopt.hal import get_hal; from netopt.optimizer import NetworkOptimizer; import json; opt=NetworkOptimizer(get_hal(dry_run=False)); res=opt.optimize_gaming_and_l4s_qos(execute=True); print(json.dumps(res, indent=2, ensure_ascii=False))"
```
*Aplica:*
- **L4S / AccECN**: `netsh int tcp set global ecncapability=enabled` para supresión de colas de bufferbloat.
- **Windows QoS**: `NonBestEffortLimit = 0` (libera el 20% de ancho de banda reservado por el programador de paquetes).
- **Throttling Off**: `NetworkThrottlingIndex = 0xffffffff` y `SystemResponsiveness = 0`.
- **Hardware Task Offload**: `DisableTaskOffload = 0` para aceleración de adaptadores Wi-Fi 7 y Ethernet multi-gigabit.
- **RFC 4821 PLPMTUD**: `EnablePMTUBHDetect = 1` en Windows y `net.ipv4.tcp_mtu_probing = 1` en Linux para evitar congelamientos por agujeros negros de MTU.

### 2. Full Network Stack Tuning Plan (with Zero NetLoss Snapshot)
```powershell
python -c "from netopt.hal import get_hal; from netopt.optimizer import NetworkOptimizer; import json; opt=NetworkOptimizer(get_hal(dry_run=False)); plan=opt.generate_plan(); ok, logs=opt.execute_plan(plan, execute=True); print(json.dumps({'plan_id': plan.plan_id, 'status': plan.status, 'snapshot': plan.rollback_snapshot_id, 'ok': ok, 'logs': logs}, indent=2, ensure_ascii=False))"
```
*Configura Autotuning Normal, RSS, RSC, Fair Queueing (Linux), DoH nativo (Cloudflare, Google, Quad9) y verificación de salud en < 5s con auto-reversión.*

### 3. Hierarchical L1–L7 Triage & Auto-Repair
```powershell
python -c "from netopt.hal import get_hal; from netopt.repair import NetworkRepairEngine; import json; rep=NetworkRepairEngine(get_hal(dry_run=False)); ft, logs=rep.diagnose_and_triage(); acts=rep.execute_triage_repair(ft, execute=True); print(json.dumps({'failure_type': ft, 'logs': logs, 'actions': [vars(a) for a in acts]}, indent=2, ensure_ascii=False))"
```

### 4. Instant Safe Rollback
```powershell
python -c "from netopt.hal import get_hal; from netopt.rollback import RollbackManager; mgr=RollbackManager(get_hal(dry_run=False)); print(mgr.rollback('<SNAPSHOT_ID>', execute=True))"
```
