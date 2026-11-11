# Capa de continuidad externa para Antigravity
## Especificación MVP — v1.0

### Objetivo

Evitar que Antigravity pierda decisiones, contradiga la arquitectura o rompa funcionalidades existentes cuando trabaja durante mucho tiempo en un proyecto grande.

**Principio central:** el agente no es la fuente de verdad del proyecto. La fuente de verdad es el repositorio, sus pruebas y los registros verificables.

Esta capa no intenta mejorar la memoria interna del modelo. Hace que el agente reconstruya el contexto desde artefactos persistentes y que sus cambios deban superar controles externos.

---

## 1. Diseño mínimo

Crear en la raíz del repositorio:

```text
.continuity/
  PROJECT.md          # propósito, arquitectura e invariantes globales
  STATE.md            # estado actual comprobable
  DECISIONS.md        # decisiones vigentes y su justificación
  TASK.md             # contrato de la tarea activa
  HISTORY.md          # registro breve de tareas terminadas
  tasks/
    TEMPLATE.md       # plantilla para nuevas tareas
  evidence/
    .gitkeep          # evidencias de validación por tarea
```

No duplicar documentación existente. Si ya hay un documento canónico de arquitectura, `PROJECT.md` debe enlazarlo en lugar de copiarlo.

### Qué guarda cada archivo

| Archivo | Contenido | Cuándo cambia |
|---|---|---|
| `PROJECT.md` | Propósito, límites, módulos, dependencias críticas e invariantes | Solo si cambia la arquitectura o el objetivo |
| `STATE.md` | Qué funciona, qué está incompleto, pruebas conocidas y último commit validado | Al cerrar cada tarea |
| `DECISIONS.md` | Decisiones vigentes, alternativas descartadas y decisiones reemplazadas | Cuando se toma una decisión relevante |
| `TASK.md` | Objetivo, alcance, archivos permitidos/prohibidos, aceptación y pruebas | Al iniciar cada tarea |
| `HISTORY.md` | Resultado, commit, pruebas ejecutadas y pendientes | Al cerrar cada tarea |

Mantener estos archivos pequeños. No convertirlos en diarios ni copiar conversaciones enteras.

---

## 2. Contrato obligatorio de cada tarea

Antes de tocar código, Antigravity debe completar `.continuity/TASK.md` con:

```markdown
# Tarea activa

## Objetivo observable
[Qué debe poder comprobarse al terminar]

## Contexto que se debe consultar
- [Documentos y módulos relevantes]

## Alcance permitido
- [Archivos o módulos que puede modificar]

## Fuera de alcance
- [Qué no debe cambiar]

## Invariantes que deben conservarse
- [Comportamientos, APIs, formatos o contratos existentes]

## Dependencias y efectos posibles
- [Módulos que consumen o dependen de lo que se cambiará]

## Criterios de aceptación
- [ ] [Resultado verificable 1]
- [ ] [Resultado verificable 2]

## Pruebas que deben ejecutarse
- [Pruebas concretas y comandos]

## Riesgos y plan de reversión
- [Riesgo]
- [Cómo revertir el cambio]
```

Si no puede completar una sección, debe escribir `DESCONOCIDO` y averiguarlo antes de implementar. No debe inventar respuestas.

Una tarea no puede mezclar objetivos independientes. Si descubre trabajo adicional, lo registra como tarea pendiente y no amplía silenciosamente el alcance.

---

## 3. Protocolo de trabajo

### Fase A — Reconstruir el proyecto

Antes de cada tarea:

1. Leer `PROJECT.md`, `STATE.md`, `DECISIONS.md` y el `TASK.md` activo.
2. Consultar `git status`, rama y commit actual.
3. Revisar los archivos reales y las pruebas de los módulos afectados.
4. Contrastar la documentación con el código. Si difieren, el código y las pruebas muestran el estado real; registrar la discrepancia.
5. Identificar dependencias entrantes y salientes del componente que se modificará.
6. No implementar hasta que el contrato de tarea esté completo.

### Fase B — Plan mínimo

Antes de editar:

1. Explicar en pocas líneas qué cambiará y por qué.
2. Enumerar los archivos que espera modificar.
3. Indicar qué comportamiento existente podría verse afectado.
4. Definir las pruebas que demostrarán que el cambio funciona.
5. Si la solución exige cambiar una decisión vigente o un invariante, detenerse y solicitar autorización.

No generar planes extensos. El plan debe ser lo bastante pequeño para poder compararlo con el diff final.

### Fase C — Implementación controlada

1. Hacer cambios pequeños y coherentes.
2. No reescribir módulos completos para resolver un defecto localizado.
3. No crear implementaciones paralelas si ya existe una funcionalidad equivalente.
4. No sustituir integraciones reales por respuestas simuladas, valores fijos o datos ficticios.
5. No declarar una integración operativa por el mero hecho de que compile.
6. No borrar ni debilitar pruebas para conseguir que la suite pase.
7. Si necesita ampliar el alcance, detenerse, explicar el motivo y actualizar el contrato antes de continuar.

### Fase D — Verificación

Antes de declarar terminada la tarea:

1. Revisar el diff completo.
2. Ejecutar las pruebas específicas del cambio.
3. Ejecutar las pruebas de regresión disponibles.
4. Ejecutar lint, tipos o build cuando existan en el proyecto.
5. Comparar el resultado con cada criterio de aceptación.
6. Registrar los comandos ejecutados, su código de salida y resultados.
7. Si una prueba no pudo ejecutarse, marcarla `NO EJECUTADA`; nunca como aprobada.
8. Si falla una prueba, no ocultar el fallo ni declarar éxito parcial como éxito total.

### Fase E — Cierre y continuidad

Solo después de verificar:

1. Actualizar `STATE.md` con hechos y evidencia.
2. Registrar decisiones nuevas en `DECISIONS.md`.
3. Añadir una entrada breve a `HISTORY.md`.
4. Registrar la referencia del commit, si existe.
5. Dejar `TASK.md` cerrada o crear una tarea nueva claramente separada.
6. Informar qué quedó sin verificar.

---

## 4. Reglas no negociables

- **No inventar estado:** si no hay evidencia, usar `DESCONOCIDO`.
- **No fingir pruebas:** una prueba no ejecutada no es una prueba aprobada.
- **No fingir integraciones:** una función simulada no equivale a una integración real.
- **No cambiar contratos silenciosamente:** APIs, formatos persistidos y comportamiento público requieren análisis de impacto.
- **No eliminar comportamiento existente sin autorización:** primero identificar quién lo utiliza.
- **No asumir que un archivo está actualizado:** comprobar el repositorio.
- **No ampliar el alcance por iniciativa propia.**
- **No actualizar la memoria para hacer parecer correcto un cambio incorrecto:** la evidencia prevalece sobre el relato del agente.
- **No marcar una tarea como completa si algún criterio obligatorio falla.**

---

## 5. Control externo: lo que realmente impide regresiones

Los archivos de continuidad ayudan a conservar contexto, pero por sí solos no impiden que un agente los ignore. La protección real debe estar fuera de sus instrucciones.

Implementar por etapas:

### Nivel 1 — Control local

- Proteger `.continuity/` mediante revisión del diff.
- Ejecutar automáticamente las pruebas relevantes antes de aceptar cambios.
- Mantener una rama de trabajo por tarea o un commit de referencia para facilitar rollback.
- No permitir que el agente reescriba la historia de decisiones sin dejar registro.

### Nivel 2 — Integración continua

Configurar CI para ejecutar, como mínimo:

- pruebas unitarias;
- pruebas de integración disponibles;
- lint y análisis estático;
- comprobación de tipos, si aplica;
- build reproducible.

Un cambio no se considera validado si CI no termina correctamente. Los fallos deben bloquear el merge cuando la plataforma y la configuración del repositorio lo permitan.

### Nivel 3 — Protección de rama

Cuando el repositorio lo permita:

- exigir CI aprobado;
- exigir revisión del diff;
- impedir push directo a la rama principal;
- exigir aprobación humana para cambios en arquitectura, autenticación, licencias, pagos, seguridad, persistencia o ejecución de comandos.

**Importante:** los hooks locales se pueden omitir. Para una barrera más fuerte, usar CI y reglas de protección de rama en el servidor Git.

---

## 6. Plantilla de registro de estado

`STATE.md` debe usar este formato breve:

```markdown
# Estado comprobado

Última actualización: [fecha]
Commit validado: [SHA o NO VALIDADO]

## Funciona y tiene evidencia
- [Componente] — [prueba/evidencia]

## Implementado, pero no verificado
- [Componente] — [qué falta comprobar]

## Incompleto
- [Componente] — [pendiente concreto]

## Deuda y riesgos conocidos
- [Riesgo] — [impacto]

## Próximo paso recomendado
- [Una tarea pequeña y verificable]
```

No utilizar porcentajes subjetivos como «proyecto 85 % terminado». Informar capacidades concretas y evidencia.

---

## 7. Plantilla de decisiones

`DECISIONS.md`:

```markdown
# Decisiones vigentes

## DEC-001 — [Título]
- Estado: VIGENTE | REEMPLAZADA
- Fecha:
- Decisión:
- Motivo:
- Alternativas descartadas:
- Componentes afectados:
- Evidencia o referencia:
- Si se reemplaza, indicar DEC que la sustituye.
```

Una decisión reemplazada no se borra: se marca como reemplazada y se enlaza con la nueva. Así se evita que el agente resucite soluciones antiguas.

---

## 8. Prompt operativo corto para Antigravity

Guardar este texto como instrucción principal del agente o incluirlo en la skill del proyecto:

> Trabaja bajo el protocolo de `.continuity/`.
>
> Antes de modificar código, reconstruye el estado desde el repositorio y lee `PROJECT.md`, `STATE.md`, `DECISIONS.md` y `TASK.md`. Comprueba rama, commit y cambios sin guardar.
>
> No confundas memoria con evidencia. No inventes estado, pruebas, integraciones ni resultados. Si algo es desconocido, decláralo y averígualo.
>
> Respeta estrictamente el alcance, los contratos y los invariantes de la tarea. No amplíes el alcance ni cambies decisiones vigentes sin autorización. Identifica dependencias antes de modificar un componente.
>
> Haz cambios pequeños. No reescribas módulos completos para arreglos localizados. No introduzcas mocks, valores fijos o implementaciones ficticias para aparentar funcionalidad real.
>
> Antes de cerrar, revisa el diff, ejecuta las pruebas definidas y registra exactamente qué se ejecutó y qué resultado tuvo. Una prueba omitida es `NO EJECUTADA`, no aprobada.
>
> Actualiza los archivos de continuidad únicamente con hechos comprobados. No declares una tarea terminada si no satisface todos sus criterios de aceptación.
>
> Si el contexto es insuficiente, hay contradicciones o el cambio amenaza un invariante, detente y pregunta. No improvises.

---

## 9. Criterios de aceptación del MVP

La capa está correctamente implantada cuando se demuestra todo lo siguiente:

- [ ] Al iniciar una sesión nueva, el agente reconstruye el estado desde el repositorio sin depender del chat anterior.
- [ ] Puede identificar una decisión vigente y explicar qué archivos o componentes protege.
- [ ] Antes de editar, produce un contrato de tarea con alcance y criterios comprobables.
- [ ] Detecta cambios previos del usuario y no los sobrescribe silenciosamente.
- [ ] Una prueba fallida impide declarar la tarea completa.
- [ ] Una prueba no ejecutada queda expresamente identificada como tal.
- [ ] El cierre deja estado, historial y evidencia suficientes para retomar el trabajo en otra sesión.
- [ ] Los cambios no relacionados con la tarea aparecen en el diff y se justifican o se revierten.

---

## 10. Orden de implantación recomendado

No implementar todo de golpe.

1. **Primero:** crear `.continuity/` y completar `PROJECT.md`, `STATE.md` y `DECISIONS.md` a partir del repositorio real.
2. **Segundo:** exigir `TASK.md` antes de cada tarea.
3. **Tercero:** conectar el protocolo con las pruebas y CI que ya existan. No crear una infraestructura nueva si el repositorio ya tiene una.
4. **Cuarto:** activar protección de rama y revisión humana para cambios críticos.
5. **Quinto:** probar con una tarea real pequeña y después con una tarea mediana. Medir si conserva decisiones y evita regresiones antes de ampliar el mecanismo.

### Regla de simplicidad

No crear un segundo sistema de gestión de proyectos, un motor multiagente ni una base de datos de memoria para este MVP. Git, Markdown, las pruebas existentes y CI son suficientes para empezar.

### Límite honesto

Esta especificación establece un método y controles, pero no demuestra que Antigravity los esté cumpliendo. Para conseguir enforcement real, hay que integrar las comprobaciones con el flujo de Git/CI y verificar que la rama protegida no acepte cambios que no hayan pasado las pruebas.
