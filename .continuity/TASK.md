# Tarea activa

## Objetivo observable
Ciclo 60: Integración de modelos Pydantic v2 (`CloudChatRequest`, `TelemetryReport`, `LicenseActivationRequest`) en los endpoints del servidor proxy SaaS (`cloud_server/proxy_server.py`) con nuevo test en `tests/test_pydantic_schemas.py`, elevando la suite completa a 127/127 tests unitarios aprobados al 100%, telemetría in situ del host validada y temporizador de 40 min renovado (`task-2483`).

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
- [x] Esquemas Pydantic v2 integrados en `main.py` y `cloud_server/proxy_server.py`.
- [x] Estrategia y herramienta `resource_audit` integrada en Hermes Cognitive Loop (`hermes/foresee.py` y `hermes/executor.py`).
- [x] Suite completa aprobada al 100% (127/127 OK en 120.5s).
- [x] Telemetría in situ del host confirmada (ping 39.05 ms, jitter 1.2 ms, pérdida 0.0%, bufferbloat A+).
- [x] Servidor Web UI activo en puerto 8877 (`task-2393`).
- [x] Documentación y estado del proyecto armonizados (README.md, AGENTS.md, AUTONOMOUS_OPERATIONAL_MANIFESTO.md a 127 tests).
- [x] Temporizador autónomo de 40 min renovado (`task-2483`).
- [ ] Ejecución continua del mandato de adopción de bibliotecas maduras (`docs/MIGRACION_BIBLIOTECAS.md`).
- [ ] Implementación de OMNI-039 (Ed25519) tras recibir autorización e instrucciones detalladas.
- - Comunicación concisa al usuario (máximo 3-5 líneas).
