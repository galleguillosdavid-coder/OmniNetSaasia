# Tarea activa

## Objetivo observable
Ciclo 54: Consolidación de la auditoría técnica y mandato de adopción de bibliotecas maduras (`docs/Auditorias/2.md` y `docs/Auditorias/3.md`), con unificación de versión v2.9.6, suite en 110/110 tests aprobados al 100%, telemetría in situ del host validada y temporizador de 40 min renovado para Ciclo 55 (`task-2401`).

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
- [x] Suite completa aprobada al 100% (110/110 OK en 117.4s).
- [x] Telemetría in situ del host confirmada (ping 39.14 ms, jitter 1.47 ms, pérdida 0%).
- [x] Temporizador autónomo de 40 min renovado (`task-2401`).
- [ ] Ejecución por fases del mandato de adopción de bibliotecas maduras (`docs/MIGRACION_BIBLIOTECAS.md`).
- [ ] Implementación de OMNI-039 (Ed25519) tras recibir autorización e instrucciones detalladas.
- [ ] Push dual a `origin` y `upstream-operador` una vez autorizado.
- Comunicación concisa al usuario (máximo 3-5 líneas).

## Dependencias y efectos posibles
- Protege los sockets del sistema contra el reseteo abrupto por ataques ciegos de RST y la reutilización corrupta de tuplas en puertos locales durante transferencias intensivas.

## Criterios de aceptación
- [x] Función `check_rfc9293_tcp_state_machine_and_rst_challenge_ack_status()` implementada y exportada en `netopt/diagnostics.py`.
- [x] Test unitario `test_rfc9293_tcp_state_machine_and_rst_challenge_ack_status` añadido a `tests/test_netopt_mock.py`.
- [x] 107/107 tests ejecutados y aprobados al 100% en `python -m unittest discover -s tests -v`.
- [x] `.continuity/` y documentación sincronizados a 107 tests.

## Pruebas que deben ejecutarse
- `python -m unittest discover -s tests -v` (107 tests OK).

## Riesgos y plan de reversión
- Riesgo: Discrepancia en la lista canónica de los 11 estados de conexión TCP.
- Reversión: Revertir archivo con git si la suite detecta inconsistencias.
