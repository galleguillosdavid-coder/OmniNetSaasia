# Tarea activa

## Objetivo observable
Ciclo 57: Integración de adaptadores de bibliotecas maduras (`HttpClientAdapter` con `httpx`) en `netopt/llm_gateway.py` y `cloud_server/proxy_server.py`, y validación tipada estricta con Pydantic v2 en `main.py` (`OmniNetAPIHandler`), elevando la suite completa a 124/124 tests unitarios aprobados al 100% en 121.7s.

## Contexto que se debe consultar
- `docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`
- `AGENTS.md`
- `.continuity/STATE.md`
- `.continuity/DECISIONS.md`
- `PROJECT_STATE.md`
- `docs/Auditorias/2.md`
- `docs/Auditorias/3.md`

## Criterios de aceptación
- [x] OMNI-038 implementado y verificado (3 tests en `test_autosentinel_safety.py`).
- [x] Política Fail-Closed y unificación de versión v2.9.6 verificadas.
- [x] Adaptadores maduros `psutil` y `httpx` implementados e integrados (`netopt/adapters.py`, `netopt/llm_gateway.py`, `cloud_server/proxy_server.py`).
- [x] Esquemas Pydantic v2 implementados e integrados en `main.py` (`OmniNetAPIHandler`).
- [x] Suite completa aprobada al 100% (124/124 OK en 121.7s).
- [x] Telemetría in situ del host confirmada.
- [x] Documentación y estado del proyecto armonizados (README.md, AGENTS.md, AUTONOMOUS_OPERATIONAL_MANIFESTO.md a 124 tests).
- [x] Comunicación concisa al usuario (máximo 3-5 líneas).
