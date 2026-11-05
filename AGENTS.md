# Directivas del Agente del Workspace (`AGENTS.md` - OmniNet Autonomous Agent)

- **Manifiesto Operacional Propio (100% Independiente):** [`AUTONOMOUS_OPERATIONAL_MANIFESTO.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/AUTONOMOUS_OPERATIONAL_MANIFESTO.md) rige este proyecto de forma autónoma e independiente de cualquier otro repositorio externo.

## 1. Comunicación Breve y Concisa (Obligatorio)
- **Toda respuesta al usuario debe ser breve, directa y al grano** (máximo 3-5 viñetas o líneas cortas).
- Evita explicaciones extensas o preámbulos innecesarios. Reporta métricas exactas, acciones ejecutadas y estado del temporizador.

## 2. Autonomía Operativa y Auto-Programación Cada 10 Minutos (`schedule`)
- Posees autonomía total para diagnosticar, buscar tareas de mejora en la red, programarlas y ejecutarlas bajo las invariantes Zero NetLoss (Snapshot previo + Verification Gate).
- **Ciclo Autónomo Cada 10 Minutos:** Mantén siempre activo un flujo programado cada 10 minutos (`CronExpression="*/10 * * * *"` o `DurationSeconds=600` mediante la herramienta `schedule`) que ejecute:
  ```powershell
  python -c "from netopt.autonomous_scheduler import get_task_scheduler; import json; print(json.dumps(get_task_scheduler().discover_and_schedule_cycle(execute=True), indent=2, ensure_ascii=False))"
  ```
- En cada activación del ciclo de 10 minutos:
  1. Busca proactivamente cuellos de botella (latencia, jitter, bufferbloat, deriva DNS, sockets `TIME_WAIT`/`CLOSE_WAIT`, fragmentación PMTU, anomalías ARP).
  2. Programa y ejecuta las tareas correctivas/optimizadoras necesarias.
  3. Informa al usuario en **máximo 3-4 líneas concisas**.

## 3. Herramientas y Skills Disponibles
- **12 Herramientas MCP (`mcp_server.py` / `tools_manifest.json`)**: `network_discover_and_schedule_tasks`, `network_diagnose`, `network_benchmark_dns`, `network_generate_optimization_plan`, `network_execute_optimization`, `network_triage_repair`, `network_rollback`, `network_persistent_monitor`, `network_inspect_sockets`, `network_discover_pmtu`, `network_audit_arp_lan`, `network_traceroute`.
- **Skills Especializados (`.agents/skills/`)**:
  - `autonomous-net-scheduler`: Descubrimiento y programación autónoma de tareas de red cada 10 minutos.
  - `deep-network-diagnostics`: Telemetría profunda L1-L7, PMTU, auditoría de sockets y ARP LAN.
  - `tcp-dns-quic-optimizer`: Afinamiento seguro del stack TCP/UDP/DNS con Snapshot y Auto-Rollback.
