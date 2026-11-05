# MANIFIESTO OPERACIONAL AUTÓNOMO — OMNINET AI AGENT PRO
## Protocolo Soberano de Optimización de Redes, Telemetría L1–L7 y Auto-Evolución Continua

> [!IMPORTANT]
> ### 👑 DIRECTIVA SUPREMA DE PRIORIDAD 0 (100% INDEPENDIENTE)
> **1. Independencia Total del Proyecto:** Este manifiesto gobierna de forma exclusiva e independiente el proyecto **OmniNet AI Agent Pro (`Optimizador de redes`)**, sin ninguna dependencia ni referencia a otros proyectos externos.  
> **2. Principios Rectores Inviolables:** *Autonomía Operativa Absoluta, Comunicación Breve y Concisa, Cero Dependencias Externas Innecesarias, Invariante Zero NetLoss (Snapshot Previo + Verification Gate + Auto-Rollback), 100% Pruebas Unitarias Aprobadas y Ciclo Autónomo de Redes Cada 10 Minutos (`600s`)*.  
> **3. Naturaleza Ampliable y Auto-Evolutiva (Metodología Harness²):** Optimización continua de los componentes del agente (prompts, guardrails, memoria, herramientas MCP, skills, scripts y planificador autónomo).

---

## 1. Arquitectura y Subsistemas Activos (`netopt/`)

1. **[`netopt/hal.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/hal.py):** Capa de Abstracción de Hardware/OS multiplataforma (`WindowsHAL`, `LinuxHAL`, `DarwinHAL`) con modo seguro `dry_run`.
2. **[`netopt/diagnostics.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/diagnostics.py):** Motor de telemetría profunda L1–L7: RTT TCP, Jitter RFC 3550, Bufferbloat (`A+` a `F`), Benchmark Anycast DNS, inspección de estados de sockets (`TIME_WAIT`/`CLOSE_WAIT`), descubrimiento binario de Path MTU (`DF-bit`) y auditoría ARP LAN.
3. **[`netopt/optimizer.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/optimizer.py):** Motor de afinamiento de pila TCP (`autotuninglevel`, `rss`, `rsc`, `bbr`, `fq`) y conmutación DNS Anycast con Snapshot y Verification Gate.
4. **[`netopt/repair.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/repair.py):** Árbol jerárquico de triage y autorreparación L1 a L7 (Enlace -> DHCP/ARP -> Ruta IP -> DNS -> Stack/Sockets).
5. **[`netopt/rollback.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/rollback.py):** Gestor de Snapshots en `~/.netopt_state/snapshots/` y reversión automática en `< 5s` ante degradación.
6. **[`netopt/auto_trigger.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/auto_trigger.py):** Centinela adaptativo con línea base dinámica EWMA y enfriamiento de histéresis (`600s`) libre de falsos positivos.
7. **[`netopt/autonomous_scheduler.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/autonomous_scheduler.py):** Planificador autónomo de ciclo de **10 minutos (`600s`)** que busca, agenda y ejecuta tareas preventivas y correctivas en la red.
8. **[`netopt/llm_gateway.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/llm_gateway.py):** Pasarela cognitiva agnóstica de modelo con contrato estricto de comunicación breve y concisa.
9. **[`mcp_server.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/mcp_server.py) & [`tools_manifest.json`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/tools_manifest.json):** Servidor JSON-RPC 2.0 MCP con 12 herramientas nativas.

---

## 2. Contrato de Comunicación y Ciclo Autónomo de 10 Minutos

- **Brevedad Estricta:** Toda respuesta al usuario debe tener máximo 3–5 viñetas concisas: métricas clave, acciones/snapshots ejecutados y estado del próximo ciclo de 10 minutos.
- **Ciclo Cada 10 Minutos (`schedule`):** El agente mantiene activo un cron cada 10 minutos (`*/10 * * * *`) que ejecuta el descubrimiento y programación autónoma de tareas de red y verifica el cumplimiento de Zero Regressions (`python -m unittest discover -s tests -v`).

