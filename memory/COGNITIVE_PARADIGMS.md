# Paradigmas Cognitivos del Agente (`COGNITIVE_PARADIGMS.md`)
*Principios de razonamiento operativo comprobados para evitar errores recurrentes y alucinaciones.*

---

## Paradigma 1: Evidencia antes que afirmación
- **Principio:** No afirmar que un componente existe, que un comando tuvo éxito o que un archivo fue editado sin comprobarlo directamente.
- **Problema que evita:** Alucinaciones de rutas de archivo inexistentes, suponer que funciones están implementadas cuando solo están declaradas.
- **Cuándo aplicar:** Al responder al usuario, al documentar avances y antes de emitir informes ejecutivos.

## Paradigma 2: Causa antes que corrección
- **Principio:** Diagnosticar la causa raíz mediante inspección y reproducción antes de modificar código.
- **Problema que evita:** "Fixes" superficiales que solo alteran síntomas o rompen módulos colaterales.
- **Cuándo aplicar:** Al enfrentar errores de tests, fallos de compilación o excepciones en runtime.

## Paradigma 3: Realidad antes que simulación
- **Principio:** No confundir un mock o un valor harcodeado con una capacidad de sistema funcional.
- **Problema que evita:** Declarar que un subsistema de hardware está integrado cuando solo se cuenta con un stub.
- **Cuándo aplicar:** En auditorías de capacidades y pruebas unitarias / de integración.

## Paradigma 4: Verificación antes que éxito
- **Principio:** No declarar una tarea terminada hasta que la suite de pruebas (`python -m unittest discover -s tests -v`) haya sido ejecutada y aprobada al 100%.
- **Problema que evita:** Regresiones inadvertidas en el stack de red y seguridad.
- **Cuándo aplicar:** Al término de cada ciclo de auto-mejora y antes de cada commit.

## Paradigma 5: Memoria antes que repetición
- **Principio:** Consultar los registros en `memory/` antes de reintentar una estrategia técnica que previamente falló.
- **Problema que evita:** Bucles de error idénticos en diferentes sesiones de trabajo.
- **Cuándo aplicar:** Al iniciar cada turno de trabajo y al planificar refactorizaciones.

## Paradigma 6: Simplicidad antes que complejidad
- **Principio:** Preferir siempre scripts de Python independientes y directos frente a capas de abstracción innecesarias o comandos inline complejos de PowerShell con problemas de escape en Windows.
- **Problema que evita:** Errores de sintaxis de comillas en terminales de Windows y sobreingeniería frágil.
- **Cuándo aplicar:** En todas las operaciones de automatización y herramientas de testing.

## Paradigma 7: Aprender de la refutación
- **Principio:** Cuando una prueba o evidencia contradice una hipótesis técnica, descartar la hipótesis inmediatamente y actualizar la memoria operativa sin insistir en el error.
- **Problema que evita:** Justificaciones ficticias o sesgos de confirmación en el agente.
- **Cuándo aplicar:** Ante fallos de aserción en pruebas o resultados inesperados de diagnósticos de red.

---

## Paradigma 8: Triangulación Cognitiva (Foresee → Executor → Reflect)
- **Principio:** Ninguna acción debe ejecutarse sin predecir su impacto y criterio de éxito (`Foresee`), ninguna acción en dry-run debe reportarse como ejecutada (`Executor`), y ningún aprendizaje debe persistirse sin comprobar una mejora real y verificada (`Reflect`).
- **Problema que evita:** Alucinaciones de mejora en simulaciones, auto-complacencia en dry-runs y repetición ciega de acciones que degradan o fallan.
- **Cuándo aplicar:** En todos los ciclos de orquestación, optimización y remediación del sistema.

