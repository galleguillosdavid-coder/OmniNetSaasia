---
name: autonomous-net-scheduler
description: >-
  Use this skill to run, manage, or inspect the autonomous network and device
  maintenance engine of OmniNet. Discovers bottlenecks across L1-L7 and the 10
  ecosystem subsystems, executes remediations with Zero NetLoss safety, and
  governs the dual cadence (OmniNet event-driven autonomous tasks vs Agent 40-minute
  self-improvement cycle).
---

# Autonomous Engine & Scheduler (Dual Cadence)

Governs autonomous discovery, remediation, and self-evolution across both the OmniNet software and the AI Agent.

## Dual Operational Cadence

1. **Ciclos Autónomos del Software OmniNet (Por Demanda / Evento)**:
   - OmniNet monitorea en segundo plano y ejecuta optimizaciones, limpiezas y autorreparaciones **cada vez que sea necesario** sobre cualquiera de sus 10 subsistemas (Redes, Antivirus, BleachBit, SDIO, Temperatura, Arranque, Desinstalador, Anti-Telemetría, DISM/SFC, Respaldo).
   - El centinela adaptativo reacciona instantáneamente ante degradación de latencia, pérdida de paquetes o cuellos de botella de disco/memoria.

2. **Ciclo de Auto-Mejora del Agente IA (Cada 40 Minutos)**:
   - El agente mantiene activo un flujo programado cada 40 minutos (`DurationSeconds=2400` vía `schedule`).
   - Misión: Vigilancia tecnológica web (L4S, ECN, BBRv3, DoH, Wi-Fi 7, radar LAN), ampliación de capacidades de los 10 sub-agentes, y verificación de Cero Regresiones (`python -m unittest discover -s tests -v`).

---

## Execution Procedures

### 1. Run Autonomous Discovery & Remediation Cycle (OmniNet Core)
```powershell
python -c "from netopt.autonomous_scheduler import get_task_scheduler; import json; print(json.dumps(get_task_scheduler().discover_and_schedule_cycle(execute=True), indent=2, ensure_ascii=False))"
```

### 2. Inspect Sentinel Status & Recent Incidents
```powershell
# Estado del centinela adaptativo
python -c "from netopt.auto_trigger import get_sentinel; import json; print(json.dumps(get_sentinel().get_status(), indent=2, ensure_ascii=False))"

# Disparar chequeo y autorreparación reactiva inmediata
python -c "from netopt.auto_trigger import get_sentinel; import json; rep=get_sentinel().check_health_and_auto_heal(); print(rep.failure_type if rep else 'Estado Saludable - Sin Incidentes')"
```

### 3. Programar Ciclo de Auto-Mejora del Agente (40 Minutos)
El agente invoca la herramienta `schedule`:
```json
{
  "DurationSeconds": 2400,
  "Prompt": "Ejecutar ciclo de auto-mejora de 40 minutos del Agente IA en OmniNet"
}
```
