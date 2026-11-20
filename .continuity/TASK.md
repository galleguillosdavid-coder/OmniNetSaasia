# Tareas Reorganizadas por Ciclos y Sub-Ciclos (`DEC-006`)

## 1. Ciclos Periódicos (Programados vía `schedule`)
- [ ] **Ciclo Macro (Cada 40 min, `DurationSeconds=2400`):** Rotación multimódulo (`netopt/`, `hermes/`, `cloud_server/`, `config/`+`main.py`+`mcp_server.py`, `tests/`, `docs/`+`.continuity/`), pruebas reales in situ (`run_real_device_empirical_probes()`), actualización de `.continuity/STATE.md` y reporte breve (3-5 viñetas).
- [ ] **Sub-Ciclo Periódico de Vigilancia Antigravity (Cada 3er ciclo macro o diario):** Buscar actualizaciones, herramientas, skills, workflows y plugins de **Antigravity** (`antigravity-guide`, `agy-customizations`, `search_marketplace`, `search_web`) y aplicarlos de forma persistente (`run_workflow` para auditorías fan-out, `swarm` para refactors paralelos, `schedule` cron/timer, `invoke_subagent`).
- [x] **Ciclo Micro-Software OmniNet (10 min / continuo):** `AutonomousTaskScheduler` + `AutoSentinel` activos bajo Zero NetLoss (`OMNI-038`).

## 2. Sub-Ciclos por Necesidad (Reactivos / Event-Driven)
- [ ] **Contención & Regresión:** Activar de inmediato ante cualquier test fallido, degradación empírica (`bufferbloat_grade >= C`, pérdida > 0%, anomalía ARP) o error de arranque (`main.py serve` / `cloud_server`).
- [ ] **Auditoría de Seguridad & Persistencia:** Activar al modificar endpoints HTTP, esquemas Pydantic v2, firmas HMAC/Ed25519, locks transaccionales o rutas de mutación (`execute is True`).

## 3. Sub-Ciclos Ocasionales (Hitos / Mantenimiento Profundo)
- [ ] **Suite Completa & Higiene Git:** Ejecutar `python -m unittest discover -s tests -v` (`233` tests), `git diff --check` y armonizar conteos/versiones en `README.md`, `AGENTS.md`, `docs/` y `.continuity/`.
- [ ] **Migración Progresiva a Bibliotecas Maduras:** Sustituir código artesanal restante según `docs/Auditorias/3.md` apoyándose en `run_workflow` o subagentes `research`.

## 4. Sub-Ciclos por Voluntad (Iniciativa Autónoma Disruptiva)
- [ ] **Innovación RFC & Kernel (Más Allá de lo Evidente):** Investigar en Internet (L4S/TCP Prague, DoQ/DoH3, ECH, PQC `X25519MLKEM768`, Wi-Fi 7 MLO / Wi-Fi 8 UHR, NetAdapterCx/XDP, MASQUE/OHTTP) e incorporar nuevas capacidades en `netopt/` y `hermes/`.

## Hitos Base Completados
- [x] Documento de pendientes, alternativas seleccionables y guía operativa para el usuario (`docs/PENDIENTES_Y_ACCIONES_USUARIO.md`) creado y propagado a `AGENTS.md`, `README.md` y `.continuity/`.
- [x] Remediación Auditoría H-01..H-10, Ed25519 y endurecimiento `execute is True` (Ciclos 120–131, `c63a1b7`, `207/207` tests OK).
- [x] Migración FastAPI/Uvicorn (`netopt/fastapi_app.py`), Pydantic v2 (`netopt/schemas.py`), adaptadores `psutil`/`httpx` (`netopt/adapters.py`) y telemetría in situ (`netopt/telemetry.py`).
- [x] Propagación de Arquitectura de Ciclos y Sub-Ciclos (`DEC-006` / `DEC-013`) en `AGENTS.md`, `docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`, `.continuity/` y `memory/`.
