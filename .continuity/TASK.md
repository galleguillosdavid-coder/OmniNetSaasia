# Tarea activa

## Objetivo observable
Ciclo 61: Ejecución y cumplimiento integral del mandato de adopción de bibliotecas maduras (`docs/MIGRACION_BIBLIOTECAS.md` y `docs/Auditorias/3.md` §245-285): migración completa de la REST API hacia FastAPI y Uvicorn (`netopt/fastapi_app.py` y `main.py`) con preservación 100% de contratos HTTP y esquemas Pydantic v2, creación de suite de pruebas en `tests/test_fastapi_app.py`, elevando la suite general a 135/135 tests unitarios aprobados al 100%, servidor FastAPI/Uvicorn activo en puerto 8877 (`task-2630`) y temporizador de 40 min en curso (`task-2483`).

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
- [x] Suite completa aprobada al 100% (135/135 OK).
- [x] Telemetría in situ del host confirmada (ping 39.05 ms, jitter 1.2 ms, pérdida 0.0%, bufferbloat A+).
- [x] Servidor Web UI activo en puerto 8877 bajo FastAPI/Uvicorn (`task-2630`).
- [x] Documentación y estado del proyecto armonizados (README.md, AGENTS.md, AUTONOMOUS_OPERATIONAL_MANIFESTO.md a 135 tests).
- [x] Temporizador autónomo de 40 min en ejecución (`task-2483`).
- [ ] Implementación de OMNI-039 (Ed25519) tras recibir autorización e instrucciones detalladas.
- - Comunicación concisa al usuario (máximo 3-5 líneas).
