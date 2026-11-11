# Tarea activa

## Objetivo observable
Ciclo 58: Integración de adaptadores de bibliotecas maduras (`HttpClientAdapter` con `httpx`) en `netopt/licensing.py` para activación SaaS en la nube con nuevo test unitario en `tests/test_mature_adapters.py`, elevando la suite completa a 125/125 tests unitarios aprobados al 100%, telemetría empírica in situ del host validada y temporizador autónomo de 40 min renovado (`task-2286`).

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
- [x] Suite completa aprobada al 100% (125/125 OK).
- [x] Telemetría in situ del host confirmada (ping 33.6 ms, jitter 0.05 ms, pérdida 0.0%, bufferbloat A+).
- [x] Documentación y estado del proyecto armonizados (README.md, AGENTS.md, AUTONOMOUS_OPERATIONAL_MANIFESTO.md a 125 tests).
- [x] Temporizador autónomo de 40 min renovado (`task-2286`).
- [ ] Ejecución continua del mandato de adopción de bibliotecas maduras (`docs/MIGRACION_BIBLIOTECAS.md`).
- [ ] Implementación de OMNI-039 (Ed25519) tras recibir autorización e instrucciones detalladas.
- - Comunicación concisa al usuario (máximo 3-5 líneas).
