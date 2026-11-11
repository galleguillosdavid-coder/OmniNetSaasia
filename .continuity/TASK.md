# Tarea activa

## Objetivo observable
Ciclo 59: Integración de la herramienta y estrategia `resource_audit` en el bucle cognitivo Hermes (`hermes/foresee.py` y `hermes/executor.py`) alimentada por `SystemResourceAdapter` (`psutil`) con nuevo test en `tests/test_hermes_cognitive.py`, elevando la suite completa a 126/126 tests unitarios aprobados al 100%, servidor Web UI activo en puerto 8877 (`task-2393`), telemetría in situ del host validada y temporizador de 40 min renovado (`task-2397`).

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
- [x] Adaptadores maduros `psutil` y `httpx` implementados e integrados (`netopt/adapters.py`, `netopt/llm_gateway.py`, `cloud_server/proxy_server.py`, `netopt/licensing.py`).
- [x] Esquemas Pydantic v2 implementados e integrados en `main.py` (`OmniNetAPIHandler`).
- [x] Estrategia y herramienta `resource_audit` integrada en Hermes Cognitive Loop (`hermes/foresee.py` y `hermes/executor.py`).
- [x] Suite completa aprobada al 100% (126/126 OK).
- [x] Telemetría in situ del host confirmada (ping 130.69 ms, jitter 0.3 ms, pérdida 0.0%, bufferbloat A).
- [x] Servidor Web UI activo en puerto 8877 (`task-2393`).
- [x] Documentación y estado del proyecto armonizados (README.md, AGENTS.md, AUTONOMOUS_OPERATIONAL_MANIFESTO.md a 126 tests).
- [x] Temporizador autónomo de 40 min renovado (`task-2397`).
- [ ] Ejecución continua del mandato de adopción de bibliotecas maduras (`docs/MIGRACION_BIBLIOTECAS.md`).
- [ ] Implementación de OMNI-039 (Ed25519) tras recibir autorización e instrucciones detalladas.
- - Comunicación concisa al usuario (máximo 3-5 líneas).
