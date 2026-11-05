---
name: tcp-dns-quic-optimizer
description: >-
  Use this skill to generate, apply, verify, or roll back OS-level TCP stack
  optimizations (Autotuning, RSS, RSC, BBR, FQ), Anycast DNS switching, and
  hierarchical L1-L7 triage repairs under strict Zero NetLoss safety invariants.
---

# TCP, DNS & Triage Optimizer (Zero NetLoss)

Applies cross-platform network stack tuning and hierarchical self-healing with mandatory pre-action snapshots and post-action verification gates.

## Workflow

1. **Generate & Execute Optimization Plan with Safety Snapshot**:
   ```powershell
   python -c "from netopt.hal import get_hal; from netopt.optimizer import NetworkOptimizer; import json; opt=NetworkOptimizer(get_hal(dry_run=False)); plan=opt.generate_plan(); ok, logs=opt.execute_plan(plan, execute=True); print(json.dumps({'plan_id': plan.plan_id, 'status': plan.status, 'snapshot': plan.rollback_snapshot_id, 'ok': ok, 'logs': logs}, indent=2))"
   ```

2. **Hierarchical L1–L7 Triage & Auto-Repair**:
   ```powershell
   python -c "from netopt.hal import get_hal; from netopt.repair import NetworkRepairEngine; import json; rep=NetworkRepairEngine(get_hal(dry_run=False)); ft, logs=rep.diagnose_and_triage(); acts=rep.execute_triage_repair(ft, execute=True); print(json.dumps({'failure_type': ft, 'logs': logs, 'actions': [vars(a) for a in acts]}, indent=2))"
   ```

3. **Instant Rollback (if needed)**:
   ```powershell
   python -c "from netopt.hal import get_hal; from netopt.rollback import RollbackManager; mgr=RollbackManager(get_hal(dry_run=False)); print(mgr.rollback('<SNAPSHOT_ID>', execute=True))"
   ```

