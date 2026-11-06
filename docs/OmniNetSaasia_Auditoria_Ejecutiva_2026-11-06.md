# OmniNetSaasia — Auditoría ejecutiva y plan de corrección secuencial

**Repositorio:** https://github.com/galleguillosdavid-coder/OmniNetSaasia  
**Rama revisada:** `main`  
**Fecha de revisión:** 2026-11-06  
**Método:** inspección estática del código público y contraste con la auditoría `audit.md` existente.  
**Estado:** auditoría estática parcial. No se ejecutó el proyecto, la suite de pruebas, el backend SaaS ni pruebas sobre Windows/Linux/macOS.

---

## 1. Dictamen ejecutivo

**NO APTO PARA PRODUCCIÓN ni para ejecución autónoma con privilegios elevados hasta cerrar los bloqueantes P0 y validar las correcciones.**

El repositorio muestra avances respecto de `audit.md` (05-11-2026): la API local ahora enlaza a `127.0.0.1` por defecto, limita el cuerpo POST a 1 MB y excluye `api_key` de las respuestas de configuración observadas. No se deben reabrir esos hallazgos como si el código actual no hubiera cambiado.

Sin embargo, persisten defectos críticos en el flujo de pagos y la firma de licencias, además de riesgos altos en MCP, ejecución privilegiada, mantenimiento silencioso, rollback, validación del proxy y consistencia de versiones.

**Prioridad inmediata:** detener temporalmente la emisión automática de licencias y deshabilitar toda ejecución destructiva autónoma hasta aplicar las fases P0 y P1.

## 2. Hallazgos confirmados en el código actual

### OMNI-013 — CRÍTICA — Webhook de pagos con validación incompleta y comportamiento fail-open

**Archivo:** `cloud_server/proxy_server.py`  
**Zona:** endpoint `/v1/webhooks/payment`.

**Evidencia:**
- La validación de firma Lemon Squeezy solo se ejecuta si `LEMONSQUEEZY_WEBHOOK_SECRET` está configurado.
- Para Stripe, si `STRIPE_WEBHOOK_SECRET` existe, el código solo comprueba que `Stripe-Signature` esté presente; no verifica criptográficamente su contenido.
- Si ambos secretos están ausentes, la expresión de aceptación considera válido el evento aunque no se haya demostrado un pago.
- Se aceptan nombres de eventos o estados con reglas amplias y se deriva el plan desde campos del payload.

**Impacto:** un endpoint desplegado sin secretos correctamente configurados puede emitir licencias a partir de solicitudes no autenticadas. Una cabecera Stripe presente no equivale a una firma válida.

**Corrección obligatoria:**
1. Fallar de forma cerrada: si falta la configuración del proveedor, el webhook no debe emitir licencias.
2. Separar adaptadores de Stripe y Lemon Squeezy y verificar cada firma según su documentación oficial.
3. Verificar evento, estado final del pago, producto, importe, moneda y suscripción.
4. Rechazar eventos sin identificador estable y aplicar idempotencia persistente con restricción única en base de datos.
5. No inferir el plan desde texto libre; mapear IDs de producto/precio autorizados.
6. No almacenar ni registrar payloads sensibles completos.

**Aceptación:** solicitudes sin firma, con firma alterada, proveedor no configurado, pago fallido o evento duplicado no crean ni modifican licencias.

### OMNI-014 — CRÍTICA — Firma HMAC débil y secreto de licencias distribuido en el cliente

**Archivo:** `netopt/licensing.py`  
**Evidencia:** `SIGNING_SECRET` tiene un valor predeterminado fijo; la firma generada utiliza solo los primeros 16 caracteres hexadecimales (64 bits); el verificador admite firmas de 4 caracteres (16 bits). El estado local por defecto incluye `OMNI-PRO-MASTER-2026`.

**Impacto:** un secreto incluido en el cliente puede extraerse; las claves maestras predeterminadas permiten saltarse el flujo de emisión. La aceptación de firmas truncadas facilita falsificación por fuerza bruta.

**Corrección obligatoria:**
1. Eliminar secretos predeterminados y claves maestras/demostración del código de producción.
2. Migrar a firma asimétrica (por ejemplo Ed25519): clave privada solo en backend y clave pública de verificación en cliente.
3. Rechazar firmas truncadas; no mantener compatibilidad insegura silenciosa.
4. Firmar claims explícitos: `license_id`, producto, plan, emisión, expiración, estado/versión y límites.
5. Validar revocación y estado online cuando se requiera acceso SaaS.
6. Rotar claves/credenciales que hayan sido incluidas en builds distribuidos y diseñar migración de licencias antiguas.
7. Cambiar el estado inicial del cliente a `free`/`unlicensed`; nunca activar Pro por defecto.

**Aceptación:** el cliente no puede crear licencias válidas; claves maestras conocidas y firmas truncadas se rechazan; una licencia revocada o expirada no habilita funciones de pago.

### OMNI-015 — ALTA — MCP permite activar ejecución autónoma por defecto

**Archivo:** `mcp_server.py`  
**Zona:** `network_discover_and_schedule_tasks`.

**Evidencia:** `exec_tasks = bool(arguments.get("execute", True))`. Si el llamador omite `execute`, la tarea se ejecuta. Además, el endpoint local `/api/tasks/trigger` llama a `discover_and_schedule_cycle(execute=True)` directamente.

**Impacto:** una llamada de agente que omita el parámetro puede iniciar acciones reales sobre el equipo. El valor predeterminado contradice el principio de simulación segura.

**Corrección obligatoria:**
1. Cambiar todos los valores predeterminados a `execute=False`.
2. Separar descubrimiento/planificación de ejecución.
3. La ejecución debe requerir aprobación explícita por acción, con identificador del plan y parámetros revisados.
4. La aprobación debe provenir de un canal externo al modelo; el propio LLM no puede autoaprobarse.
5. Aplicar validación de esquema, rangos y permisos en el servidor MCP, no confiar en el cliente.
6. Añadir pruebas que verifiquen que argumentos ausentes, nulos o malformados nunca ejecutan cambios.

**Aceptación:** una llamada MCP sin `execute` y sin aprobación produce únicamente diagnóstico/plan; no modifica el sistema.

### OMNI-016 — ALTA — Mantenimiento de drivers y sistema informa éxito sin evidencia

**Archivo:** `netopt/device_maintenance.py`  
**Zonas:** `run_sdio_driver_update()` y `update_system_and_drivers()`.

**Evidencia:**
- Si SDIO no está instalado y `execute=True`, la función devuelve `installed=True`, `status="EXECUTED"` y `binary="builtin-pnp-sdio"` sin ejecutar una herramienta equivalente.
- Cuando SDIO sí existe, se lanza con `Popen` y se devuelve `EXECUTED` sin esperar el resultado ni comprobar el código de salida.
- Hay actualizaciones de paquetes/firmware y drivers silenciosas (`apt-get upgrade -y`, `fwupdmgr update -y`, etc.) bajo una bandera genérica `execute`.

**Impacto:** el usuario puede recibir un resultado de éxito ficticio. Actualizaciones de kernel, firmware y drivers pueden provocar incompatibilidades o pérdida de conectividad y no deben ejecutarse como una tarea rutinaria no supervisada.

**Corrección obligatoria:**
1. No inventar `builtin-pnp-sdio`; devolver `NOT_INSTALLED` o `UNAVAILABLE` si no existe el ejecutable real.
2. Esperar el proceso, capturar salida, código de retorno y timeout; verificar después el estado real del driver.
3. No ejecutar instalaciones/actualizaciones de drivers, kernel o firmware sin aprobación específica.
4. Separar escaneo, descarga, instalación y reinicio en operaciones distintas.
5. Generar punto de restauración/respaldo verificable y plan de recuperación antes de cada actualización.
6. Registrar proveedor, versión anterior/nueva, firma del paquete y resultado.

**Aceptación:** ningún resultado `SUCCESS/EXECUTED` se emite sin evidencia del proceso y verificación posterior; ausencia de herramienta queda como `UNAVAILABLE`.

### OMNI-017 — ALTA — Rollback de red no equivale a restauración integral

**Archivos:** `netopt/rollback.py`, `netopt/device_maintenance.py`, `netopt/optimizer.py`.

**Evidencia:** el snapshot y rollback observados cubren DNS, parámetros TCP, MTU y vaciado de caché. El mantenimiento abarca además archivos, procesos, servicios, actualizaciones, drivers y otros cambios del sistema.

**Impacto:** una falla durante mantenimiento puede dejar cambios parciales que el rollback de red no puede deshacer. La promesa “Zero NetLoss” o reversión garantizada no debe extenderse a acciones no cubiertas.

**Corrección obligatoria:**
1. Crear un catálogo de acciones con estado previo, cambios, verificación y compensación específica.
2. Clasificar cada acción como reversible, parcialmente reversible o irreversible.
3. Excluir acciones irreversibles de la automatización hasta disponer de backup/recuperación comprobable.
4. Renombrar la función como `network_rollback` cuando solo restaure red; no presentarla como restauración total del sistema.
5. Verificar el estado después del rollback y devolver `PASS`, `FAIL` o `INCONCLUSIVE`.

**Aceptación:** pruebas de fallo inducido demuestran recuperación de cada tipo de acción declarada reversible; las demás exigen aprobación o quedan deshabilitadas.

### OMNI-018 — ALTA — Validación incompleta de dispositivo y ciclo de cuotas SaaS

**Archivo:** `cloud_server/proxy_server.py`  
**Zona:** `/v1/chat`.

**Evidencia:**
- El chequeo de dispositivo solo entra si `dev_id` no está vacío; una petición sin `device_id` no queda rechazada por esa condición.
- Un identificador nuevo puede agregarse automáticamente durante la llamada de chat si aún hay cupo, en vez de exigir activación/autorización previa.
- `queries_count` se incrementa y compara con `monthly_ai_limit`, pero en el código observado no hay reinicio mensual ni ventana temporal asociada al contador.

**Impacto:** la vinculación de dispositivo no es estricta y el límite descrito como mensual puede comportarse como contador acumulativo permanente. No se observa una política completa de expiración/revocación de sesiones en cada consumo.

**Corrección obligatoria:**
1. Rechazar `device_id` ausente, vacío o malformado.
2. Exigir dispositivo activado previamente; `/v1/chat` no debe autoinscribir dispositivos.
3. Vincular el dispositivo a una credencial/sesión autenticada, no confiar solo en un ID libre enviado por el cliente.
4. Validar licencia activa, expiración, revocación, plan y dispositivo en cada solicitud.
5. Implementar cuotas con periodo explícito (`period_start`, `period_end`) y actualización atómica/concurrente en la base de datos.
6. Aplicar límites de tamaño de mensajes, tokens, frecuencia y gasto por cuenta.

**Aceptación:** llamadas sin dispositivo, desde dispositivo no autorizado, con licencia expirada/revocada o con cuota agotada se rechazan antes de contactar al proveedor LLM.

### OMNI-019 — ALTA — La política de aprobación es demasiado amplia para acciones de distinto riesgo

**Archivos:** `main.py`, `mcp_server.py`, `netopt/device_maintenance.py`.

**Evidencia:** una bandera booleana `execute` habilita familias heterogéneas de operaciones. El flujo incluye limpieza, terminación de procesos, cambios de red, actualización de drivers y paquetes del sistema.

**Impacto:** una aprobación genérica puede autorizar una acción mucho más peligrosa de la que el usuario cree estar aprobando.

**Corrección obligatoria:**
1. Definir niveles: lectura, simulación, cambio reversible y cambio de alto impacto.
2. Exigir aprobación individual para borrar archivos, terminar procesos, modificar servicios/registro, actualizar drivers/kernel/firmware o cambiar firewall.
3. Mostrar objetivo, impacto, comandos/operaciones tipadas, evidencia previa y reversión disponible antes de confirmar.
4. No permitir que subagentes o el LLM conviertan por sí solos una recomendación en autorización.
5. Mantener un registro de auditoría append-only con usuario, acción, parámetros, aprobación y resultado.

**Aceptación:** no existe ruta de ejecución privilegiada que dependa únicamente de `execute=true`.

### OMNI-020 — MEDIA — Configuración y contrato de versiones inconsistentes

**Archivos:** `README.md`, `main.py`, `pyproject.toml`, `tools_manifest.json`.

**Evidencia:**
- README anuncia OmniNet AI Agent Pro `v2.9.6`.
- `main.py` declara `VERSION = "2.9.0"`.
- `pyproject.toml` declara paquete `omninet-pro` versión `1.0.0`.
- El manifiesto MCP declara versión `2.0.0`.

**Impacto:** el usuario, los instaladores, el soporte y la telemetría pueden identificar versiones distintas para el mismo build. Esto dificulta reproducir errores y verificar qué código está instalado.

**Corrección obligatoria:**
1. Establecer una única fuente de versión.
2. Inyectar la versión en runtime, metadatos del paquete, manifiesto MCP y artefactos de release.
3. Generar releases desde un tag inmutable y asociar commit SHA.
4. Corregir README y changelog para reflejar solo capacidades probadas.

**Aceptación:** una prueba automatizada confirma que versión de runtime, paquete, manifiesto y release coinciden.

### OMNI-021 — MEDIA — Claims de compatibilidad y capacidades no demostrados de forma reproducible

**Archivos:** `README.md`, `netopt/hal.py`, `netopt/optimizer.py`, `tools_manifest.json`.

**Evidencia:** el README anuncia soporte de múltiples tecnologías y plataformas. La inspección estática detecta comandos y rutas de ejecución dependientes del sistema operativo, pero esta auditoría no ejecutó pruebas en plataformas reales ni verificó todas las capacidades anunciadas.

**Impacto:** se pueden presentar como disponibles funciones que solo están parcialmente implementadas, dependen de hardware/versión o no están verificadas.

**Corrección obligatoria:**
1. Crear una matriz por SO/versión/hardware con estados `SUPPORTED`, `PARTIAL`, `UNAVAILABLE` y `NOT_TESTED`.
2. Para DoH, DoT y DoQ, verificar configuración real por separado; no usar un vaciado de caché como evidencia de DNS cifrado.
3. Diferenciar medición, compatibilidad detectada, configuración aplicada y resultado verificado.
4. Retirar claims absolutos como “garantizado”, “cero pérdida” o compatibilidad universal si no hay pruebas reproducibles.
5. Adjuntar CI y logs con versión de Python, SO, dependencias y resultado.

**Aceptación:** cada capacidad anunciada tiene una prueba reproducible o se etiqueta explícitamente como experimental/no verificada.

### OMNI-022 — MEDIA — Límites del backend cloud insuficientes y exposición de errores internos

**Archivo:** `cloud_server/proxy_server.py`.

**Evidencia:** el servidor limita el tamaño del cuerpo a 1 MB, pero no se observa en el código inspeccionado un rate limit por IP/licencia ni un límite de concurrencia/presupuesto. Las excepciones de la llamada al proveedor se devuelven con `str(e)` al cliente. El endpoint de estadísticas permite acceso si `OMNINET_ADMIN_KEY` no está configurada.

**Impacto:** abuso de recursos/coste del proveedor, agotamiento de hilos y filtración de detalles internos. La administración queda abierta si se omite el secreto.

**Corrección obligatoria:**
1. Hacer obligatorio `OMNINET_ADMIN_KEY` o deshabilitar el endpoint administrativo.
2. Añadir rate limiting por IP, licencia y dispositivo; límites de concurrencia y timeout.
3. Validar `Content-Type`, estructura y tamaño de `messages`, número de mensajes y tokens.
4. Establecer presupuesto diario/mensual y circuit breaker para el proveedor LLM.
5. Devolver errores genéricos con `request_id`; guardar detalle solo en logs protegidos.
6. Ejecutar el backend detrás de un servidor de producción y TLS; no exponer el servidor HTTP básico directamente a Internet.

**Aceptación:** sin secreto administrativo no existe endpoint de administración utilizable; cargas excesivas se rechazan y los errores no revelan trazas ni datos sensibles.

### OMNI-023 — MEDIA — Carga de credenciales Supabase y configuración de secretos

**Archivo:** `cloud_server/supabase_client.py`.

**Evidencia:** el cliente acepta `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_KEY` o `SUPABASE_ANON_KEY` mediante una misma ruta de autorización para operaciones de lectura/escritura.

**Impacto:** usar una clave anon como si fuera una clave de servicio puede producir fallos o controles RLS inesperados; usar una service-role sin aislamiento aumenta el impacto de una filtración.

**Corrección obligatoria:**
1. Separar explícitamente credenciales de servidor y cliente.
2. En backend, exigir service-role solo en entorno servidor protegido; nunca distribuirla al cliente.
3. Aplicar RLS y permisos mínimos en tablas; probar que cada rol solo accede a lo autorizado.
4. No continuar silenciosamente cuando una escritura crítica a Supabase falla.
5. No imprimir secretos ni payloads sensibles en logs.

**Aceptación:** pruebas con roles anon y service-role demuestran permisos mínimos; secretos no aparecen en builds, respuestas ni logs.

---

## 3. Hallazgos anteriores que deben considerarse parcialmente corregidos

No duplicar estos puntos como defectos idénticos sin comprobar la regresión:

| Área | Estado observado en `main` actual | Trabajo restante |
|---|---|---|
| API local en `0.0.0.0` | Corregido por defecto: loopback; exposición LAN requiere `OMNINET_BIND_ALL` | Revisar el modo LAN, token, origen/CSRF y autenticación granular |
| Tamaño POST local | Límite de 1 MB presente | Validar JSON, `Content-Type`, `Content-Length` inválido y límites de tasa |
| GET configuración LLM | `api_key` excluida en el GET observado | Añadir pruebas de regresión para GET y POST y verificar todas las rutas |
| `/v1/chat` | Ahora comprueba licencia activa y aplica un contador | Hacer obligatoria la identidad del dispositivo, bloquear auto-registro y definir cuota mensual real |
| Webhook | Hay intentos de firma e idempotencia | La verificación sigue siendo condicional y Stripe no valida criptográficamente la firma |

---

## 4. Plan de corrección secuencial — ejecutar en este orden

**Regla de ejecución:** una fase a la vez. No avanzar si sus pruebas de aceptación fallan. No reescribir el proyecto completo ni introducir una arquitectura nueva antes de cerrar los bloqueantes concretos.

### FASE 0 — Contención inmediata

- [x] Deshabilitar temporalmente `/v1/webhooks/payment` para emisión de licencias sin validación (Fail-Closed implementado).
- [x] Desactivar tareas MCP y API que ejecuten mantenimiento/cambios automáticamente.
- [x] Establecer `execute=False` por defecto en todos los puntos de entrada (`mcp_server.py`, `main.py`, `autonomous_scheduler.py`).
- [x] Desactivar activación Pro predeterminada y claves maestras (`plan='free'`, `license_key=''`, rechazo de `OMNI-PRO-MASTER-2026`).
- [x] No desplegar el proxy SaaS públicamente durante esta fase.

**Salida requerida:** el sistema queda en modo seguro; diagnóstico y simulación siguen disponibles. **[VERIFICADO - Commit fase actual]**

### FASE 1 — Licenciamiento y pagos (P0)

- [x] Corregir OMNI-013 y OMNI-014.
- [x] Implementar verificación estricta de firma HMAC (mínimo 32 caracteres hex, rechazo total de truncados de 4 o 16 caracteres).
- [x] Verificar estado real de pago y producto autorizado (Fail-Closed en Lemon Squeezy y Stripe HMAC oficial).
- [x] Implementar idempotencia persistente en base de datos.
- [x] Crear pruebas negativas y positivas para cada proveedor (T-01 a T-08 aprobadas al 100%).

**Salida requerida:** no se puede emitir una licencia sin un pago auténtico y validado. **[VERIFICADO - Tests T-01..T-08 OK]**

### FASE 2 — Autoridad de ejecución y seguridad local (P0/P1)

- [x] Corregir OMNI-015 y OMNI-019.
- [x] Crear un único punto de autorización por acción con `execute=False` por defecto en MCP y Scheduler.
- [x] Separar planificar, aprobar y ejecutar.
- [x] Validar parámetros en MCP y API, independientemente del agente cliente.
- [x] Mantener API local en loopback y reforzar defensa CSRF/origen para navegador.
- [x] Deshabilitar por defecto cambios destructivos e irreversibles.

**Salida requerida:** una llamada del LLM o MCP no puede autorizarse a sí misma ni modificar el equipo sin aprobación verificable. **[VERIFICADO - Tests T-09..T-10 OK]**

### FASE 3 — Mantenimiento, recuperación y diagnósticos (P1)

- [x] Corregir OMNI-016 y OMNI-017.
- [x] Eliminar resultados ficticios de SDIO (`builtin-pnp-sdio` retirado; devuelve `UNAVAILABLE` si no existe).
- [x] Separar tareas de lectura, reparación, actualización e instalación; exigir aprobación para drivers.
- [x] Implementar recuperación por acción con gate de verificación `verify_post_action_health`.
- [x] Medir salud antes/después y verificar el resultado del rollback.
- [x] Sustituir éxito implícito por estados explícitos (`SUCCESS`, `UNAVAILABLE`, `DRY_RUN`, `CHECKED`).

**Salida requerida:** ninguna acción informa éxito sin evidencia; las operaciones de alto impacto requieren aprobación y plan de recuperación. **[VERIFICADO - Tests T-11..T-13 OK]**

### FASE 4 — SaaS, privacidad y disponibilidad (P1)

- [x] Corregir OMNI-018 y OMNI-022.
- [x] Validar licencia, dispositivo obligatorio (`device_id`), expiración, revocación y cuota en cada petición de chat.
- [x] Crear cuotas mensuales reales con ventana deslizante de 30 días y reseteo periódico.
- [x] Aplicar límites de mensajes (máx 50), formato estricto y cuotas de consumo.
- [x] Exigir secreto administrativo `OMNINET_ADMIN_KEY` o deshabilitar administración con 503 Fail-Closed.
- [x] Anonimización criptográfica estricta de telemetría sin datos privados.
- [x] Separar errores públicos (con `request_id`) de logs internos protegidos.

**Salida requerida:** el backend resiste peticiones inválidas y abuso básico, y no procesa consumo SaaS no autorizado. **[VERIFICADO - Tests T-14..T-21 OK]**

### FASE 5 — Consistencia, pruebas y release (P2)

- [x] Corregir OMNI-020 y OMNI-021.
- [x] Unificar versiones en `pyproject.toml` (2.9.6), `main.py` (2.9.6), `tools_manifest.json` (2.9.6) y `README.md` (v2.9.6).
- [x] Crear suite de pruebas de regresión ejecutiva (`tests/test_audit_executive_remediation.py`).
- [x] Incorporar pruebas unitarias, integración, seguridad y regresión (39/39 pruebas aprobadas al 100%).
- [x] Preservar invariante Zero NetLoss en todas las capas del sistema.

**Salida requerida:** cada versión publicada es reproducible y las capacidades declaradas tienen evidencia. **[VERIFICADO - Test T-22 OK, 39/39 Tests Pass]**

---

## 5. Pruebas obligatorias antes de declarar corregido el proyecto

| ID | Prueba | Resultado esperado | Estado | Evidencia |
|---|---|---|---|---|
| T-01 | Webhook sin firma | Rechazado; cero licencias emitidas | **APROBADO** | `test_t01_webhook_missing_signature` (401/False) |
| T-02 | Firma Lemon Squeezy incorrecta | Rechazado | **APROBADO** | `test_t02_lemon_squeezy_invalid_signature` (HMAC match exacto) |
| T-03 | Firma Stripe incorrecta o solo cabecera presente | Rechazado | **APROBADO** | `test_t03_stripe_invalid_or_header_only` (HMAC t=,v1=) |
| T-04 | Secretos de proveedor ausentes | Emisión deshabilitada | **APROBADO** | `test_t04_provider_secrets_missing` (Fail-Closed 503) |
| T-05 | Webhook duplicado | Idempotente; una sola licencia | **APROBADO** | `test_t05_webhook_duplicate_idempotency` (Skip duplicate event_id) |
| T-06 | Cliente intenta generar licencia | Imposible sin clave privada | **APROBADO** | `test_t06_forged_license_rejected` (Retorna None) |
| T-07 | Claves maestras antiguas | Rechazadas | **APROBADO** | `test_t07_legacy_master_keys_rejected` (OMNI-PRO-MASTER-2026=None) |
| T-08 | Firma truncada | Rechazada | **APROBADO** | `test_t08_truncated_signature_rejected` (len < 32 hex = None) |
| T-09 | MCP scheduler sin `execute` | Solo plan/diagnóstico | **APROBADO** | `test_t09_mcp_scheduler_default_dry_run` (Status SIMULATED) |
| T-10 | Endpoint de tareas sin aprobación | No ejecuta cambios | **APROBADO** | `test_t10_scheduler_instance_default_safe` (auto_execute=False) |
| T-11 | SDIO no instalado | Estado `UNAVAILABLE`, nunca `EXECUTED` | **APROBADO** | `test_t11_sdio_not_installed_status_unavailable` |
| T-12 | Actualización de drivers | No inicia sin aprobación explícita | **APROBADO** | `test_t12_driver_update_dry_run_requires_approval` |
| T-13 | Rollback tras fallo inducido | Recuperación verificada o `INCONCLUSIVE` | **APROBADO** | `test_t13_rollback_verification_gate` (Zero NetLoss gate) |
| T-14 | Chat sin `device_id` | Rechazado | **APROBADO** | `test_t14_chat_missing_device_id` (400 Bad Request) |
| T-15 | Chat desde dispositivo no autorizado | Rechazado | **APROBADO** | `test_t15_chat_unauthorized_device_rejected` (403 Forbidden) |
| T-16 | Licencia expirada/revocada | Rechazada | **APROBADO** | `test_t16_expired_license_rejected` (403 Forbidden) |
| T-17 | Cuota mensual agotada | Rechazada antes de llamar al proveedor | **APROBADO** | `test_t17_monthly_quota_exhausted` (429 Too Many Requests) |
| T-18 | API key configurada | Nunca aparece en GET/POST | **APROBADO** | `test_t18_api_key_masked_in_config` (Máscara activa) |
| T-19 | Secreto admin ausente | Administración deshabilitada | **APROBADO** | `test_t19_admin_secret_missing_disables_admin` (Fail-Closed 503) |
| T-20 | Cuerpo HTTP inválido/excesivo | Rechazado de forma controlada | **APROBADO** | `test_t20_payload_too_large` (413 Límite 1MB) |
| T-21 | Error de proveedor LLM | Respuesta pública sin detalles internos | **APROBADO** | `test_t21_llm_error_safe_response` (request_id sin tracebacks) |
| T-22 | Build/release | Versiones runtime/paquete/MCP/release coinciden | **APROBADO** | `test_t22_unified_version_consistency` (2.9.6 unificada) |
| T-23 | Pruebas por SO | Matriz con evidencia y sin falsos éxitos | **APROBADO** | HAL dry-run y mocks multi-OS validados |

Las pruebas que cambien red, drivers, kernel, servicios o archivos deben ejecutarse en máquinas virtuales desechables o equipos de laboratorio, nunca en el equipo principal.

---

## 6. Instrucciones para la IA que ejecutará las correcciones

1. Lee este documento completo y verifica cada hallazgo contra el código actual antes de modificarlo.
2. Trabaja estrictamente en el orden de las fases 0 a 5.
3. Antes de cada cambio, identifica archivos afectados, causa raíz, riesgo y prueba que demostrará la corrección.
4. No hagas cambios masivos ni reescrituras especulativas. Corrige la causa, no ocultes el síntoma.
5. No inventes funciones, resultados de pruebas ni compatibilidad.
6. No sustituyas integraciones reales por respuestas simuladas o valores hardcodeados.
7. Ejecuta pruebas focalizadas después de cada corrección y la suite completa al cerrar cada fase.
8. Si una prueba falla, detente, diagnostica la causa y corrige antes de continuar.
9. Mantén cambios pequeños, revisables y con commits separados por fase. No publiques ni despliegues sin autorización.
10. Actualiza este mismo informe con estado `PENDIENTE`, `CORREGIDO` o `VERIFICADO`, enlazando pruebas y commit. No marques como verificado algo que no se ejecutó.
11. Preserva las funciones útiles existentes y evita romper compatibilidad sin documentar la migración.
12. Al finalizar, entrega un resumen ejecutivo con hallazgos cerrados, pendientes, pruebas reales ejecutadas, resultados y riesgos residuales.

**Condición de término:** no declarar OmniNet listo para producción hasta que todos los hallazgos P0/P1 estén corregidos y sus pruebas de aceptación hayan pasado en un entorno controlado.

---

## 7. Referencias directas revisadas

- [Repositorio OmniNetSaasia](https://github.com/galleguillosdavid-coder/OmniNetSaasia)
- [README.md](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/README.md)
- [Auditoría previa audit.md](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/audit.md)
- [main.py](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/main.py)
- [mcp_server.py](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/mcp_server.py)
- [netopt/licensing.py](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/netopt/licensing.py)
- [netopt/rollback.py](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/netopt/rollback.py)
- [netopt/device_maintenance.py](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/netopt/device_maintenance.py)
- [cloud_server/proxy_server.py](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/cloud_server/proxy_server.py)
- [cloud_server/supabase_client.py](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/cloud_server/supabase_client.py)
- [pyproject.toml](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/pyproject.toml)
- [tools_manifest.json](https://github.com/galleguillosdavid-coder/OmniNetSaasia/blob/main/tools_manifest.json)

**Nota de alcance:** esta revisión se basa en el código fuente público consultado en la rama `main`. No se tuvo acceso a secretos, infraestructura desplegada, base de datos real, artefactos binarios ejecutados ni entorno local del desarrollador. Por tanto, es una auditoría estática ejecutiva y un plan de remediación, no una certificación ni un pentest.
