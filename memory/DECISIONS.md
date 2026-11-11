# Registro de Decisiones Técnicas y Arquitectónicas (`DECISIONS.md`)
*Registro inmutable de decisiones técnicas, alternativas descartadas y consecuencias.*

---

## [2026-11-05] DEC-001: Arquitectura de Doble Cadencia Operativa
- **Decisión:** Desacoplar el motor autónomo de OmniNet (reactivo y continuo por eventos) del ciclo de auto-mejora del Agente IA (recurrente cada 40 minutos).
- **Alternativas consideradas:**
  1. Un único bucle rígido de 10 minutos para todo. Descartado: provocaba sobrecarga en el agente e impedía a OmniNet reaccionar en milisegundos a caídas de red.
  2. Ejecución bajo demanda manual únicamente. Descartado: violaba el principio de autonomía absoluta.
- **Consecuencias:** OmniNet protege el sistema 24/7 en tiempo real mientras el agente investiga, refina heurísticas y verifica tests cada 40 minutos.
- **Condiciones de revisión:** Solo si el usuario solicita cambiar el intervalo del temporizador.

---

## [2026-11-06] DEC-002: Sincronización Dual Git (`origin` y `upstream-operador`)
- **Decisión:** Mantener ambos repositorios remotos estrictamente sincronizados en la rama `main` en cada ciclo de trabajo.
- **Alternativas consideradas:** Desacoplar los repositorios en ramas separadas. Descartado para mantener uniformidad total entre `OmniNetSaasia` y `Operador-de-red-Ia`.
- **Consecuencias:** Todo avance se respalda y distribuye en ambas cuentas de GitHub simultáneamente.

---

## [2026-11-07] DEC-003: Arnés de Ejecución y Orquestador Hermes
- **Decisión:** Desarrollar en `hermes/` un arnés desacoplado de herramientas (`harness.py`), orquestación de sub-agentes (`orchestrator.py`) y motor de auto-mejora con memoria persistente (`self_improvement.py`).
- **Alternativas consideradas:** Confiar únicamente en llamadas MCP externas. Descartado para permitir tests unitarios herméticos sin depender de procesos externos.
- **Consecuencias:** Capacidad de aprendizaje, evaluación y ejecución en sandbox integrada en el núcleo del proyecto.


---

## [2026-11-09] DEC-004: Bucle Cognitivo Hermes Foresee → Executor → Reflect
- **Decisión:** Añadir en `hermes/` un planificador anticipatorio determinista (`foresee.py`), un ejecutor que despacha pasos vía `HermesAgentHarness.dispatch_tool` con snapshot/rollback Zero NetLoss (`executor.py`), un evaluador que califica contra criterios de éxito y persiste estadísticas por estrategia en `HermesMemory` (`reflect.py`), y un bucle con re-planificación acotada (`cognitive_loop.py`).
- **Alternativas consideradas:** Planificación vía LLM. Descartado como base: sin API key debe funcionar offline y los tests deben ser herméticos; el LLM puede añadirse luego como capa sobre `ForeseePlanner`.
- **Consecuencias:** Pasos simulados nunca cuentan como éxito ni alimentan el aprendizaje; estrategias con ≥2 fallos reales consecutivos se excluyen automáticamente de planes futuros.
