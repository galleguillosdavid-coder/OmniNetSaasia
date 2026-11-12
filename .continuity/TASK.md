# Tarea activa

## Objetivo observable
Ciclo 73: Formalizar e incorporar como directiva autónoma inviolable: redefinir las tareas autónomas frecuentemente y buscar soluciones activas más allá de lo evidente, utilizando internet y cualquier otro tipo de solución disruptiva (arquitecturas avanzadas, nuevos estándares RFC, optimizaciones de bajo nivel del kernel, adopción de bibliotecas de vanguardia, heurísticas cognitivas y refactorizaciones no convencionales), documentado en `AGENTS.md`, `docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`, `README.md`, manteniendo el 100% de tests aprobados (166/166 OK), el daemon FastAPI (:8877) y el ciclo de 40 minutos activos.

## Contexto que se debe consultar
- `docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`
- `AGENTS.md`
- `.continuity/STATE.md`
- `.continuity/DECISIONS.md`
- `PROJECT_STATE.md`
- `docs/Auditorias/2.md`
- `docs/Auditorias/3.md`
- `docs/MIGRACION_BIBLIOTECAS.md`

## Criterios de aceptación
- [x] OMNI-038 implementado y verificado (3 tests en `test_autosentinel_safety.py`).
- [x] Política Fail-Closed y unificación de versión v2.9.6 verificadas.
- [x] Adaptadores maduros `psutil` y `httpx` implementados e integrados (`netopt/adapters.py`, `netopt/llm_gateway.py`, `cloud_server/proxy_server.py`, `netopt/licensing.py`).
- [x] Esquemas Pydantic v2 integrados en `main.py`, `cloud_server/proxy_server.py` y `netopt/fastapi_app.py`.
- [x] Estrategia y herramienta `resource_audit` integrada en Hermes Cognitive Loop (`hermes/foresee.py` y `hermes/executor.py`).
- [x] Migración REST API hacia FastAPI/Uvicorn (`netopt/fastapi_app.py` y `main.py`) con 8 tests en `tests/test_fastapi_app.py`.
- [x] Ejecución del mandato de adopción de bibliotecas maduras (`docs/MIGRACION_BIBLIOTECAS.md` y `docs/Auditorias/3.md`).
- [x] Suite completa aprobada al 100% (166/166 OK).
- [x] Telemetría in situ del host confirmada (ping 39.05 ms, jitter 1.2 ms, pérdida 0.0%, bufferbloat A+).
- [x] Servidor Web UI activo en puerto 8877 bajo FastAPI/Uvicorn (`task-2630`).
- [x] Documentación y estado del proyecto armonizados (README.md, AGENTS.md, AUTONOMOUS_OPERATIONAL_MANIFESTO.md a 166 tests).
- [x] Temporizador autónomo de 40 min en ejecución (`task-2483`).
- [ ] Implementación de OMNI-039 (Ed25519) tras recibir autorización e instrucciones detalladas.
- - Comunicación concisa al usuario (máximo 3-5 líneas).
