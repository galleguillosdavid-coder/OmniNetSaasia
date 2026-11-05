---
name: autonomous-net-scheduler
description: >-
  Use this skill to run, manage, or inspect the autonomous 10-minute network task
  discovery and self-scheduling engine. Discovers network bottlenecks across L1-L7,
  queues remediation/optimization tasks, executes them with Zero NetLoss safety,
  and maintains the recurring 10-minute schedule.
---

# Autonomous 10-Minute Network Task Scheduler

This skill empowers the agent to proactively search for and schedule its own network maintenance, optimization, and repair tasks every 10 minutes (`600s` / `*/10 * * * *`).

## Execution Procedure

1. **Run the Autonomous Discovery & Execution Cycle**:
   ```powershell
   python -c "from netopt.autonomous_scheduler import get_task_scheduler; import json; print(json.dumps(get_task_scheduler().discover_and_schedule_cycle(execute=True), indent=2, ensure_ascii=False))"
   ```

2. **Verify Scheduled Task History**:
   Inspect `~/.netopt_state/scheduled_tasks.json` or call `get_task_scheduler().get_status()`.

3. **Maintain Recurring 10-Minute Trigger**:
   Ensure the `schedule` tool is active with `CronExpression="*/10 * * * *"` and `IsDaemon=True` (or `DurationSeconds=600`).

4. **Concise Reporting**:
   Report to the user in at most 3–4 bullet lines: Health/RTT/Jitter, Tasks Executed + Snapshot ID, and Next 10-Min Schedule status.

