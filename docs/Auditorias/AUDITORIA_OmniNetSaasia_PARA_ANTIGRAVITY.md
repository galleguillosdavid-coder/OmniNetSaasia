# AUDITORÍA TÉCNICA Y PLAN DE CORRECCIÓN — OmniNetSaasia
## Instrucciones ejecutables para Antigravity

**Destinatario:** Antigravity  
**Repositorio:** https://github.com/galleguillosdavid-coder/OmniNetSaasia  
**Rama objetivo:** `main`  
**Commit base solicitado:** `563a312`  
**Commit padre declarado:** `126306f`  
**Alcance declarado del commit:** 33 archivos, +1.281 / -554 líneas; seguridad, concurrencia, Ed25519, `dry-run` y continuidad.

---

## 0. Mandato principal

Antigravity: realiza una auditoría correctiva real del repositorio completo, partiendo exactamente del commit `563a312`. No te limites a editar los fragmentos de este documento ni a hacer cambios cosméticos.

Debes:

1. Clonar/actualizar el repositorio y confirmar que `HEAD` corresponde a `563a312` o a un descendiente cuyo historial incluya ese commit.
2. Leer el código completo, configuración, dependencias, workflows CI, documentación y todas las pruebas relacionadas.
3. Verificar cada hallazgo de este documento contra el código actual. Si un hallazgo no aplica, explica por qué y aporta evidencia.
4. Corregir defectos confirmados con cambios mínimos, compatibles y testeables.
5. Añadir pruebas de regresión antes de declarar resuelto cualquier problema.
6. Ejecutar la suite completa y pruebas específicas de concurrencia, seguridad y fallos.
7. No borrar funcionalidades, datos, historial ni pruebas para conseguir un resultado verde.
8. No modificar secretos reales ni imprimirlos en logs.
9. No hacer push, publicar releases, desplegar ni ejecutar operaciones destructivas sin autorización explícita.
10. Entregar un informe final con archivos modificados, causa raíz, pruebas ejecutadas, resultados y riesgos pendientes.

**No declares “100 % seguro”, “producción lista” ni “todos los tests pasan” sin evidencia reproducible.** Diferencia claramente entre pruebas ejecutadas, pruebas no ejecutadas y pruebas que no existen.

---

## 1. Evidencia inicial y límites de esta revisión

La página pública del commit `563a312` confirma el mensaje de commit, el padre, los 33 archivos y el volumen de cambios. Entre los archivos visibles están:

- `cloud_server/proxy_server.py`
- `hermes/executor.py`
- `hermes/harness.py`
- `hermes/orchestrator.py`
- `hermes/self_improvement.py`
- `mcp_server.py`
- `netopt/adapters.py`
- `netopt/auto_trigger.py`
- `netopt/autonomous_scheduler.py`
- `netopt/cli.py`
- `netopt/diagnostics.py`
- `netopt/ecosystem_subagents.py`
- `netopt/elevation.py`
- `netopt/fastapi_app.py`
- `netopt/hal.py`
- `netopt/licensing.py`
- `netopt/llm_gateway.py`
- `netopt/micro_internet.py`
- `netopt/optimizer.py`
- `netopt/persistence.py`
- `netopt/repair.py`
- `netopt/rollback.py`
- `netopt/schemas.py`
- `netopt/telemetry.py`
- `tests/test_cloud_server.py`
- `tests/test_fastapi_app.py`
- `tests/test_hermes.py`
- `tests/test_hermes_cognitive.py`
- `tests/test_micro_internet.py`

La revisión externa disponible permitió inspeccionar partes del diff publicado, pero no ejecutar el proyecto ni verificar todo el árbol de archivos en un entorno local. Por tanto, los puntos siguientes son **hallazgos estáticos sobre fragmentos visibles y controles obligatorios para verificar en el repositorio**, no una certificación integral ni una afirmación de que todos los defectos estén presentes.

---

## 2. Hallazgos prioritarios

### H-01 — Corrupción de JSON tratada como base vacía: riesgo de pérdida silenciosa de datos
**Archivo:** `cloud_server/proxy_server.py`  
**Prioridad:** CRÍTICA — corregir antes de producción.

En el diff se observa que `_read_json_list()` captura cualquier excepción al leer/decodificar el archivo y devuelve `[]`. Después, `_append_json_list()` añade un elemento y escribe la lista resultante mediante reemplazo atómico.

Secuencia problemática:

1. El archivo existente está truncado, corrupto o parcialmente ilegible.
2. `_read_json_list()` oculta el error y devuelve una lista vacía.
3. `_append_json_list()` añade el nuevo registro.
4. `_atomic_write_json()` reemplaza el archivo anterior.
5. Se pierden los registros históricos sin alarma ni recuperación.

El reemplazo atómico protege frente a archivos parcialmente escritos, pero no evita la pérdida lógica causada por interpretar corrupción como “no hay datos”.

**Corrección exigida:**

- Distinguir archivo inexistente de archivo corrupto.
- Si el archivo no existe, devolver una lista vacía.
- Si existe pero no se puede decodificar, registrar un error controlado, conservar intacto el original y abortar la escritura.
- Validar que la raíz JSON sea una lista y que sus elementos tengan el tipo/estructura esperados.
- No reparar automáticamente sobrescribiendo el archivo corrupto.
- Si se implementa recuperación, conservar una copia íntegra del original con nombre único, permisos restrictivos y registro auditable; la recuperación debe ser explícita.

Patrón mínimo orientativo:

```python
import json
import os
from typing import Any, Dict, List

class CloudDataCorruptionError(RuntimeError):
    """El archivo persistente existe, pero no contiene datos JSON válidos."""

def _read_json_list(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CloudDataCorruptionError(
            f"No se pudo leer el almacén persistente: {os.path.basename(path)}"
        ) from exc

    if not isinstance(data, list):
        raise CloudDataCorruptionError(
            f"Formato inválido en almacén: se esperaba una lista ({os.path.basename(path)})"
        )

    if not all(isinstance(item, dict) for item in data):
        raise CloudDataCorruptionError(
            f"Registros inválidos en almacén: se esperaban objetos JSON"
        )

    return data
```

No incluyas el contenido del archivo ni secretos en el mensaje de error. Si el proyecto necesita aceptar listas de otros tipos, adapta la validación al contrato real y añade pruebas.

**Pruebas obligatorias:**

- Archivo inexistente → lista vacía.
- JSON válido → contenido íntegro.
- JSON truncado/corrupto → error; bytes originales intactos.
- JSON válido cuya raíz es un objeto/string/null → error; original intacto.
- Lista con elementos de tipo inesperado → error.
- Fallo de permisos/lectura → error sin sobrescribir.

### H-02 — Lock de Python no protege frente a múltiples procesos
**Archivo:** `cloud_server/proxy_server.py`  
**Prioridad:** ALTA.

El commit introduce `_CLOUD_IO_LOCK = threading.RLock()` y lo usa alrededor de lectura/escritura. Esto coordina hilos dentro de un único proceso, pero no coordina dos procesos independientes que escriban al mismo archivo.

Dos workers/procesos pueden leer el mismo estado, añadir entradas diferentes y reemplazar el archivo sucesivamente. El último escritor puede borrar la actualización del otro. `os.replace()` no convierte la operación leer-modificar-escribir en una transacción.

**Corrección exigida:**

- Determina cómo se despliega el servidor: un proceso, varios workers, múltiples réplicas o almacenamiento compartido.
- Si se garantiza estrictamente un solo proceso escritor, documenta y valida esa restricción en el arranque y en el despliegue.
- Si puede haber más de un proceso escritor, migra el estado mutable a SQLite con transacciones (`BEGIN IMMEDIATE`) o a un almacén transaccional compartido adecuado.
- No presentes `threading.RLock` como bloqueo multiproceso.
- Si mantienes archivos JSON, implementa un bloqueo interproceso portable y probado para los sistemas operativos soportados, además del lock de hilos. Evita crear un mecanismo casero sin pruebas de bloqueo, liberación tras crash y timeout.

**Pruebas obligatorias:** dos o más procesos concurrentes agregando registros; verificar que no se pierda ninguno, que el archivo final sea válido y que los procesos fallen limpiamente ante timeout/lock no disponible.

### H-03 — El estado de sesiones puede expulsar sesiones todavía activas
**Archivo:** `hermes/orchestrator.py`  
**Prioridad:** ALTA.

El nuevo `_record_session()` elimina la primera clave insertada mientras `len(active_sessions) > 200`. La inserción ordenada no implica que la sesión más antigua haya terminado. Si hay más de 200 tareas largas, puede eliminarse del registro una sesión que continúa ejecutándose.

Consecuencias posibles: pérdida de trazabilidad, imposibilidad de consultar una tarea activa y estado inconsistente entre el worker y el registro.

**Corrección exigida:**

- No expulsar sesiones con `status == "running"` (ni otros estados activos definidos por el proyecto).
- Aplicar retención/TTL únicamente a sesiones terminales (`completed`, `failed`, `cancelled`, etc.).
- Si se alcanza el límite y todas las sesiones están activas, aplicar backpressure/rechazo controlado o ampliar capacidad mediante una política explícita; nunca borrar una sesión activa silenciosamente.
- Proteger todas las lecturas, escrituras, iteraciones y eliminaciones de `active_sessions` con el mismo lock.
- Si hay consumidores que acceden directamente al diccionario, encapsular el acceso mediante métodos seguros o una API de consulta.
- No cambiar el contrato público de sesiones sin actualizar callers y tests.

**Pruebas obligatorias:** crear 201+ sesiones activas y comprobar que ninguna desaparezca; completar sesiones y verificar que solo las terminales sean candidatas a retención; hacer lecturas concurrentes mientras se crean/limpian sesiones.

### H-04 — Validación insuficiente de `max_workers` y tareas delegadas
**Archivo:** `hermes/orchestrator.py`  
**Prioridad:** MEDIA-ALTA.

El fragmento visible limita `max_workers` con `int(max_workers)` y `len(tasks)`. La conversión puede lanzar `TypeError`, `ValueError` u `OverflowError`; además, no se observa en ese fragmento validación de que cada tarea sea un diccionario con `role` y `prompt` válidos.

**Corrección exigida:**

- Validar que `tasks` sea una secuencia finita y que cada elemento tenga `role` y `prompt` con tipos y límites razonables.
- Rechazar valores inválidos con errores de dominio claros; no ocultarlos.
- Validar `max_workers` como entero positivo y limitarlo a un máximo configurado.
- Definir qué ocurre con tareas individuales fallidas: resultado fallido por tarea, sin perder resultados de las demás.
- Evitar crear un `ThreadPoolExecutor` con un número de workers controlado sin límite por el usuario.

**Pruebas obligatorias:** `tasks=[]`, `None`, tarea sin claves, valores no-string, `max_workers=0`, negativo, string inválido, `None`, número enorme y lista con varias tareas donde una falla.

### H-05 — `dry_run` debe ser una barrera de seguridad transversal, no solo una condición local
**Archivos:** `hermes/executor.py`, `netopt/hal.py`, adaptadores y herramientas mutables  
**Prioridad:** CRÍTICA.

En `executor.py` se observa:

```python
do_exec = bool(execute) and not (getattr(self.hal, "dry_run", False) is True)
```

Esto impide la ejecución real desde ese punto cuando `hal.dry_run` es exactamente `True`, pero no demuestra que todas las herramientas mutables, rutas alternativas, subagentes, llamadas MCP, adaptadores o funciones de bajo nivel respeten el modo seguro.

**Corrección exigida:**

- Auditar todas las operaciones mutables: cambios de interfaz/red, firewall, rutas, DNS, servicios, archivos, configuración, elevación de privilegios, rollback y comandos del sistema.
- Implementar una comprobación central en la capa de ejecución/HAL, no confiar exclusivamente en el caller.
- El modo dry-run debe impedir efectos secundarios reales incluso si una herramienta se invoca directamente.
- Los resultados simulados deben marcarse inequívocamente como simulados y nunca confundirse con `SUCCEEDED` real en telemetría, dependencias o UI.
- Mantener una lista explícita de operaciones de solo lectura y mutables.
- Para operaciones desconocidas o no clasificadas, denegar en dry-run y preferiblemente fallar de forma segura.
- No ejecutar rollback real si la operación original no llegó a ejecutarse.

**Pruebas obligatorias:** invocar directamente cada herramienta mutante con dry-run activado; verificar que no se llame a subprocess, APIs de sistema ni escritura real; comprobar que los mocks no registren efectos secundarios; comprobar que `execute=True` no anule el dry-run.

### H-06 — El criterio de verificación/rollback puede no identificar la verificación correcta
**Archivo:** `hermes/executor.py`  
**Prioridad:** ALTA — confirmar con el modelo de plan.

El diff visible conserva una búsqueda de la primera entrada cuyo `strategy == "verify"` y usa ese resultado para decidir si revierte. Si un plan admite varias verificaciones, una verificación temprana podría no representar el estado final. También debe comprobarse qué sucede cuando no hay verificación, cuando una verificación queda `SKIPPED` o cuando hay varios pasos mutables.

**Corrección exigida:**

- Definir formalmente qué paso(s) constituyen la verificación final del plan.
- Exigir verificación posterior a todas las mutaciones relevantes, o asociar verificaciones a los pasos que validan.
- Si una mutación real requiere snapshot y no hay verificación final válida, el plan debe fallar de forma segura y ejecutar rollback según política.
- Distinguir “rollback intentado” de “rollback confirmado”.
- Si rollback falla, reflejarlo como incidente crítico y no marcar `rolled_back=True`.
- No confiar en la primera verificación encontrada si el contrato permite más de una.

**Pruebas obligatorias:** sin verify; verify omitida; verify fallida; varias verify con resultados distintos; excepción durante verify; rollback exitoso y fallido; fallo crítico antes y después de una mutación.

### H-07 — Escritura atómica: completar durabilidad, permisos y limpieza
**Archivo:** `cloud_server/proxy_server.py`  
**Prioridad:** MEDIA-ALTA.

`_atomic_write_json()` usa `tempfile.mkstemp()` en el directorio de destino y `os.replace()`, lo cual es una buena base para evitar archivos parcialmente escritos. Aun así, debe verificarse durabilidad y protección del archivo:

- El contenido debe vaciarse y sincronizarse (`flush` + `os.fsync`) antes del reemplazo.
- En sistemas POSIX, considerar sincronizar el directorio después de `os.replace()` si se requiere durabilidad frente a caída de energía.
- Mantener permisos restrictivos del temporal y del archivo final; no asumir que el reemplazo conserva permisos del archivo anterior.
- Garantizar limpieza del temporal si falla `fdopen`, serialización, `fsync` o `replace`.
- No dejar archivos temporales con datos sensibles.
- No cambiar permisos/propietario de archivos existentes de forma inesperada.

Implementa esto de acuerdo con los sistemas operativos realmente soportados y cubre las ramas de error con pruebas.

### H-08 — `Content-Length` no basta para proteger el cuerpo HTTP
**Archivo:** `cloud_server/proxy_server.py`  
**Prioridad:** ALTA — revisar el servidor HTTP completo.

El fragmento nuevo valida que `Content-Length` sea entero, no negativo y no supere `MAX_PAYLOAD_SIZE`. Es correcto como control inicial, pero debe revisarse el flujo completo:

- ¿Qué ocurre si falta `Content-Length`?
- ¿Se acepta `Transfer-Encoding: chunked`? `BaseHTTPRequestHandler` no lo procesa automáticamente como un body chunked estándar.
- ¿Se lee exactamente la cantidad anunciada?
- ¿Qué sucede si el cliente anuncia un tamaño y envía menos bytes?
- ¿Se evita que una conexión lenta retenga un thread indefinidamente?
- ¿Se rechazan métodos/rutas/cabeceras no esperados?
- ¿Se cierra o drena correctamente la conexión tras un error?

**Corrección exigida:** establecer un contrato HTTP explícito para el body; rechazar transferencias no soportadas; limitar tamaño real leído, tiempo de lectura y concurrencia; devolver errores 4xx coherentes; nunca leer ilimitadamente con `rfile.read()`.

### H-09 — Manejo de excepciones y fuga de información
**Archivos:** `hermes/orchestrator.py`, `hermes/executor.py`, servidor y logs  
**Prioridad:** MEDIA-ALTA.

El fragmento de `orchestrator.py` convierte una excepción en `HarnessTurnResult(..., error=str(e))`. Verifica que ese texto no termine exponiendo tokens, rutas sensibles, prompts privados, datos de licencia, cabeceras HTTP o información del entorno a usuarios, telemetría o logs.

**Corrección exigida:**

- Registrar internamente un identificador de correlación y tipo de error.
- Devolver al usuario un mensaje sanitizado.
- No incluir secretos ni cuerpos de petición en logs.
- Mantener el traceback solo en logs protegidos cuando sea necesario.
- Definir límites de longitud para mensajes y resultados almacenados.
- No capturar `BaseException` salvo que exista una razón muy justificada.

### H-10 — Timeout de subprocess: límite correcto, pero comprobar recursos y terminación
**Archivo:** `hermes/harness.py`  
**Prioridad:** MEDIA.

El diff limita `timeout_sec` a un rango entre 0,5 y 60 segundos. Verifica además:

- Validación de `NaN`, infinito y valores no numéricos.
- Terminación del proceso hijo al vencer el timeout.
- Tratamiento de procesos descendientes/hijos.
- Límites de stdout/stderr para evitar consumo de memoria.
- Restricciones de entorno, directorio de trabajo, permisos y acceso a red.
- Si el código ejecutado es generado por un LLM o usuario, tratarlo como ejecución de código no confiable.

Un timeout por sí solo **no es un sandbox**. Si se ejecuta código no confiable, usar aislamiento del sistema operativo/contenedor con permisos mínimos, límites de CPU/memoria/procesos, filesystem restringido y red deshabilitada salvo autorización.

---

## 3. Auditoría criptográfica obligatoria — Ed25519

El mensaje del commit declara endurecimiento Ed25519, pero la inspección parcial del diff no permite certificar su implementación. Antigravity debe localizar todas las funciones de firma/verificación, generación/almacenamiento de claves y validación de licencias.

Comprobar:

1. Uso de una biblioteca criptográfica mantenida y API Ed25519 estándar; no implementar primitivas criptográficas manualmente.
2. Verificación sobre los bytes exactos del mensaje firmado, con serialización canónica y versionada.
3. Rechazo de firma ausente, malformada, truncada, de longitud incorrecta o con codificación inválida.
4. Rechazo de clave pública inválida y de algoritmos/formatos no permitidos.
5. Separación entre claves privadas de firma y claves públicas de verificación.
6. La clave privada no debe estar en el repositorio, logs, imágenes Docker, artefactos ni variables expuestas al cliente.
7. Rotación de claves con `key_id`, periodo de transición y revocación.
8. No aceptar fallback silencioso a HMAC, RSA u otro algoritmo si Ed25519 falla.
9. Comparación segura cuando aplique a secretos simétricos; no confundirla con la verificación Ed25519.
10. Validación de expiración, audiencia, producto, licencia, nonce/identificador y protección contra replay según el modelo de amenazas.
11. Mensajes de error que no filtren material criptográfico.
12. Vectores de prueba oficiales/conocidos y pruebas negativas.

**Pruebas mínimas:** firma válida; mensaje alterado; firma alterada; clave equivocada; firma vacía; firma truncada; clave malformada; payload malformado; algoritmo no permitido; clave revocada; licencia expirada; replay; rotación de claves.

No inventes una implementación Ed25519 propia. No des por seguro un sistema de licencias solo porque una prueba de firma válida pase.

---

## 4. Auditoría de persistencia, webhooks y pagos

En `cloud_server/proxy_server.py` se observan archivos JSON, una lista `processed_webhook_events`, verificación de firmas de Stripe/Lemon Squeezy y límites de payload. Revisar el flujo completo de extremo a extremo:

- Verificar la firma sobre el cuerpo HTTP crudo, antes de confiar en el JSON parseado.
- Validar formato, longitud y codificación de la firma.
- Comparar firmas con la primitiva segura adecuada.
- Rechazar si el secreto del webhook no está configurado; nunca aceptar por defecto.
- Implementar idempotencia transaccional: registrar el ID de evento y aplicar el efecto de negocio en una misma transacción.
- Evitar la carrera “comprobar evento no procesado → dos workers procesan el mismo evento”.
- No permitir que un evento repetido reactive, extienda o degrade licencias incorrectamente.
- Validar proveedor, tipo de evento, ID, estado, importe, moneda, producto y metadata según el contrato real.
- No confiar en campos enviados por el cliente para activar licencias.
- Definir retención de IDs de eventos y comportamiento ante reintentos.
- Evitar que un JSON corrupto se convierta en una base vacía (H-01).
- Proteger datos de clientes y licencias con permisos adecuados y política de backup.

**Criterio de aceptación:** el mismo webhook enviado concurrentemente N veces debe producir exactamente un efecto de negocio, con resultado idempotente y evidencia de auditoría.

---

## 5. Revisión de toda la superficie de seguridad

Antigravity debe inspeccionar el repositorio completo y no limitarse a los archivos del commit:

### API y servidor
- Autenticación y autorización por endpoint.
- Fail-closed cuando falten secretos/configuración.
- CORS, CSRF si aplica, SSRF, traversal, inyección y validación de entrada.
- Límites de cuerpo, frecuencia, conexiones y concurrencia.
- Bind de red: no exponer servicios administrativos en `0.0.0.0` por defecto.
- Endpoints administrativos protegidos y sin filtración de datos.
- Cabeceras HTTP seguras y errores sin stacktrace público.

### Secretos y configuración
- Buscar claves, tokens, contraseñas y certificados en el historial y árbol actual.
- Revisar `.env`, `.gitignore`, Docker, workflows y archivos de ejemplo.
- Los ejemplos deben usar placeholders no funcionales.
- No imprimir valores secretos durante diagnósticos.
- Rotar credenciales si se detecta una exposición real; eliminar del historial no sustituye la rotación.

### MCP, herramientas y ejecución
- Lista permitida explícita de herramientas.
- Validación de argumentos y permisos por herramienta.
- No ejecutar comandos arbitrarios por una instrucción de un modelo.
- Confirmación explícita para acciones destructivas o de alto impacto.
- Separar lectura, simulación y mutación.
- Límites de tiempo, memoria, salida y procesos.
- Auditar elevación de privilegios y rollback.

### Dependencias y cadena de suministro
- Revisar dependencias directas/transitivas, versiones y vulnerabilidades conocidas.
- Fijar versiones reproducibles donde corresponda.
- Revisar GitHub Actions: permisos mínimos (`contents: read` cuando baste), pin de actions a SHA, secretos protegidos y triggers de PR seguros.
- No ejecutar código no confiable de forks con secretos disponibles.
- Generar SBOM si el proyecto tiene un proceso de release/producción.

### Privacidad y telemetría
- Confirmar que prompts, tokens, datos personales, direcciones IP e identificadores sensibles no se almacenan sin necesidad.
- Aplicar minimización, retención y controles de acceso.
- Revisar anonimización real, no solo comentarios/docstrings.
- Evitar que estadísticas globales permitan reidentificación por grupos pequeños.

---

## 6. Pruebas de regresión que deben añadirse

Organiza las pruebas por módulo y evita pruebas que solo comprueben implementación interna.

### Persistencia/concurrencia
- Escrituras simultáneas desde threads.
- Escrituras simultáneas desde procesos.
- Corrupción JSON y preservación de archivo.
- Fallo de disco/permisos/rename.
- Reinicio durante escritura.
- Lectura mientras se reemplaza el archivo.
- Idempotencia de webhook bajo concurrencia.

### Hermes
- Dos `execute()` simultáneos sobre la misma instancia.
- Dos instancias independientes del executor.
- Excepción durante ejecución y limpieza de contexto.
- Snapshot fallido antes de mutación.
- Fallo de paso crítico.
- Dependencias no satisfechas.
- Dry-run en cada herramienta mutante.
- Verificación final y rollback fallido.
- 201+ sesiones activas en el orquestador.
- Lectura concurrente del registro de sesiones.
- Subagentes que fallan, expiran o devuelven resultado malformado.

### HTTP/API
- `Content-Length` ausente, negativo, no numérico, demasiado grande y cuerpo truncado.
- Cuerpo vacío, JSON inválido y JSON válido con esquema incorrecto.
- Timeout de lectura.
- Método y ruta no soportados.
- Admin sin secreto, secreto incorrecto y secreto correcto.
- Requests concurrentes y límites de rate/connections.

### Criptografía/licencias
- Vectores positivos y negativos Ed25519.
- Rotación/revocación de claves.
- Webhook repetido y concurrente.
- Secretos ausentes.
- Payload alterado.
- Expiración y replay.

---

## 7. Secuencia de trabajo exigida

Ejecuta en este orden y registra comandos/resultados:

1. `git status --short` y `git rev-parse HEAD`.
2. Inspección de `README`, `AGENTS.md`, manifiestos, dependencias, CI y documentación de despliegue.
3. Inventario de endpoints, herramientas mutables, almacenamiento, procesos y claves criptográficas.
4. Revisión del diff `126306f..563a312` y lectura completa de los archivos actuales afectados.
5. Reproducción de H-01 a H-10; registrar cada uno como confirmado, no reproducible o no aplicable.
6. Crear pruebas de regresión.
7. Corregir primero los riesgos críticos, luego los altos y después los medios.
8. Ejecutar pruebas unitarias específicas.
9. Ejecutar suite completa.
10. Ejecutar análisis estático/lint/type-check si están configurados.
11. Ejecutar pruebas de seguridad/dependencias disponibles.
12. Revisar `git diff --check`, diff completo y estado final.
13. Confirmar que no hay secretos, datos reales ni artefactos temporales añadidos.
14. Entregar el informe final.

No cambies simultáneamente arquitectura, formato de persistencia y comportamiento de negocio sin migración, pruebas y plan de rollback.

---

## 8. Criterios de aceptación para cerrar la auditoría

No cierres el trabajo hasta cumplir o documentar explícitamente cada punto:

- [ ] Los archivos persistentes corruptos no se sobrescriben silenciosamente.
- [ ] No hay pérdida de actualizaciones entre escritores concurrentes.
- [ ] Las sesiones activas nunca se eliminan por una política de retención.
- [ ] Los límites de workers/tareas están validados y acotados.
- [ ] Dry-run bloquea efectos reales desde todas las rutas de ejecución.
- [ ] La verificación final y el rollback tienen semántica inequívoca.
- [ ] Escrituras atómicas con limpieza, permisos y durabilidad adecuados.
- [ ] El servidor HTTP limita el cuerpo real, tiempo y concurrencia.
- [ ] Errores/logs no exponen secretos ni datos privados.
- [ ] Ejecución de código no confiable está aislada; timeout no se presenta como sandbox.
- [ ] Ed25519 está probado con vectores positivos/negativos y rotación/revocación.
- [ ] Webhooks son auténticos e idempotentes bajo concurrencia.
- [ ] La suite completa pasa en un entorno reproducible.
- [ ] La documentación describe el comportamiento real y las limitaciones.
- [ ] No se han eliminado pruebas ni rebajado aserciones para conseguir verde.

---

## 9. Formato obligatorio del informe de Antigravity

Entrega el resultado en este formato:

```text
AUDITORÍA OmniNetSaasia — RESULTADO

Commit base:
Commit final:
Rama:
Fecha:
Entorno / versión Python:

RESUMEN
- Hallazgos críticos:
- Hallazgos altos:
- Hallazgos medios:
- Hallazgos no reproducidos:
- Riesgos pendientes:

HALLAZGOS Y CORRECCIONES
Para cada hallazgo:
- ID:
- Archivo y líneas:
- Evidencia / reproducción:
- Causa raíz:
- Corrección aplicada:
- Prueba de regresión:
- Resultado:

PRUEBAS
- Comando:
- Resultado:
- Total ejecutadas:
- Aprobadas:
- Fallidas:
- Omitidas:

SEGURIDAD
- Ed25519:
- Secretos:
- Webhooks:
- API:
- Ejecución de herramientas:
- Dry-run:
- Persistencia/concurrencia:

CAMBIOS
- Archivos modificados:
- Migraciones:
- Compatibilidad:
- Riesgos de despliegue:

VEREDICTO
- APTO / NO APTO / APTO CON RESTRICCIONES
- Justificación basada en evidencia:
- Acciones pendientes:
```

No marques “APTO” si queda un hallazgo crítico abierto, si dry-run permite una mutación real, si hay pérdida de datos concurrente o si la suite relevante no se pudo ejecutar.

---

## 10. Enlaces de referencia del trabajo

- Repositorio: https://github.com/galleguillosdavid-coder/OmniNetSaasia
- Commit auditado: https://github.com/galleguillosdavid-coder/OmniNetSaasia/commit/563a312
- Comparación del commit con su padre: https://github.com/galleguillosdavid-coder/OmniNetSaasia/compare/126306f..563a312
- Árbol exacto del commit: https://github.com/galleguillosdavid-coder/OmniNetSaasia/tree/563a312

---

## Instrucción final para Antigravity

Antigravity: prioriza integridad de datos, seguridad por defecto y comportamiento determinista. No aceptes una solución porque “parece funcionar” ni porque un conjunto reducido de tests pase. Reproduce los fallos, corrige la causa raíz, demuestra la corrección con pruebas y conserva compatibilidad.

Si necesitas cambiar una interfaz, esquema o persistencia, identifica primero todos sus consumidores y añade una migración segura. No elimines funcionalidades para simplificar la corrección. No inventes resultados de pruebas. No hagas push ni despliegues sin autorización.

**El resultado esperado es código corregido en el repositorio, pruebas de regresión reproducibles y un informe honesto de lo que quedó resuelto y lo que aún no puede certificarse.**
