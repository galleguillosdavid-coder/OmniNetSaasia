# Tarea activa

## Objetivo observable
Ciclo 53: Cierre de OMNI-038 (aislamiento y fail-safe de AutoSentinel en `netopt/auto_trigger.py`, `main.py` y `tests/test_autosentinel_safety.py`), preservando 109/109 tests aprobados al 100%, con temporizador de 40 min renovado y a la espera de instrucciones para OMNI-039 (Ed25519 licensing).

## Contexto que se debe consultar
- `docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`
- `AGENTS.md`
- `.continuity/STATE.md`
- `.continuity/DECISIONS.md`
- `PROJECT_STATE.md`
- `mt.md`

## Criterios de aceptación
- [x] OMNI-038 implementado estrictamente según directiva quirúrgica.
- [x] Pruebas de seguridad `tests/test_autosentinel_safety.py` (2/2 OK).
- [x] Suite completa aprobada al 100% (109/109 OK).
- [x] Memoria `.continuity/` actualizada.
- [x] Temporizador de ciclo autónomo renovado a 40 minutos (`task-2331`).
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
