# ORCHESTRATION_SPEC.md: Especificación Técnica de Orquestación
## Sistema de Optimización, Autorreparación y Centinela de Redes

---

## 1. Máquina de Estados Finita del Orquestador (FSM)

El agente opera como una máquina de estados determinista gobernada por compuertas de seguridad:

```
                  ┌───────────────┐
                  │     IDLE      │
                  └───────┬───────┘
                          │ Invocación (Diagnose / Optimize / Repair / Watch)
                          ▼
                  ┌───────────────┐
                  │  DIAGNOSING   │ ◄─── (Sondeo L1 a L7, Ping, Jitter, DNS)
                  └───────┬───────┘
                          │
          ┌───────────────┴───────────────┐
          │                               │
    [Optimization]                  [Repair Triage]
          │                               │
          ▼                               ▼
  ┌───────────────┐               ┌───────────────┐
  │   PLANNING    │               │ TRIAGE_SELECT │
  └───────┬───────┘               └───────┬───────┘
          │                               │
          └───────────────┬───────────────┘
                          │ execute = True
                          ▼
                  ┌───────────────┐
                  │ SNAPSHOTTING  │ (Captura estado previo en disco)
                  └───────┬───────┘
                          │ Snapshot ID verificado
                          ▼
                  ┌───────────────┐
                  │   EXECUTING   │ (Aplica cambios en OS vía HAL)
                  └───────┬───────┘
                          │ Espera 1.0s
                          ▼
                  ┌───────────────┐
                  │  VERIFYING    │
                  └───────┬───────┘
                          │
          ┌───────────────┴───────────────┐
     [Healthy]                       [Degraded / Loss > 10%]
          │                               │
          ▼                               ▼
  ┌───────────────┐               ┌───────────────┐
  │   COMMITTED   │               │ ROLLING_BACK  │ (Restaura Snapshot previo)
  └───────────────┘               └───────┬───────┘
                                          │
                                          ▼
                                  ┌───────────────┐
                                  │   RESTORED    │
                                  └───────────────┘
```

---

## 2. Invariantes del Sistema & SLAs

| Invariante | Descripción | Límite Estricto |
| :--- | :--- | :--- |
| **INV-01 (Zero NetLoss)** | Ninguna mutación puede ejecutarse sin un `snapshot_id` persistido previamente. | Falla inmediata si `capture_snapshot()` falla. |
| **INV-02 (Verification SLA)** | Todo cambio debe someterse a una verificación de conectividad post-acción. | Intervalo de prueba: 1.0s post-cambio. |
| **INV-03 (Rollback SLA)** | En caso de degradación (pérdida > 10% o latencia > +50%), el estado debe revertirse. | Tiempo máximo de recuperación: < 5 segundos. |
| **INV-04 (Safe Dry-Run)** | El modo predeterminado de todas las herramientas y comandos es simulación. | Mutación prohibida a menos que `execute=True`. |
| **INV-05 (Daemon Rotation)** | Los registros de telemetría no deben saturar el almacenamiento del disco. | Rotación circular en 10 MB. |

---

## 3. Protocolos de Transporte y Capas

1. **Model Context Protocol (MCP):**
   - Transmisión: `stdio` (JSON-RPC 2.0).
   - Version: `2024-11-05`.
   - Métodos soportados: `initialize`, `ping`, `tools/list`, `tools/call`.

2. **REST API Embebida:**
   - Host: `127.0.0.1` (configurable a `0.0.0.0`).
   - Puerto: `8877`.
   - Endpoints:
     - `GET /health`
     - `GET /api/diagnose`
     - `GET /api/bench-dns`
     - `GET /api/snapshots`
     - `POST /api/optimize`
     - `POST /api/repair`
     - `POST /api/rollback`

3. **Capa de Abstracción de Red (HAL):**
   - Windows: PowerShell 5.1/7+, `netsh`, WMI.
   - Linux: `sysctl`, `iproute2` (`ip`), `systemd-resolved`, `nmcli`.
   - macOS: `networksetup`, `scutil`, `sysctl`, `dscacheutil`.

