# OmniNetSaasia — Auditoría técnica integral
**Fecha:** 10-11-2026  
**Repositorio:** https://github.com/galleguillosdavid-coder/OmniNetSaasia  
**Rama:** `main`  
**HEAD revisado:** `91398688b053858c890b67ccf94cf31c9ac5001e`  
**Comparación:** 45 commits posteriores al commit `822924b5495988c6d170c13fb7067118e02d2eba`  
**Método:** inspección estática del árbol, código fuente, diffs, configuración y pruebas versionadas. No se ejecutó el binario ni la suite en un equipo Windows/Linux/macOS real.

---

## 1. Dictamen ejecutivo

# NO APTO PARA PRODUCCIÓN CON EJECUCIÓN AUTÓNOMA O LICENCIAMIENTO COMERCIAL

El repositorio ha avanzado considerablemente en estructura: incorpora el ciclo cognitivo Hermes, memoria, skills, un scheduler, telemetría declarada, más diagnósticos y cambios de seguridad en el proxy.

Pero el principal problema no es la cantidad de código. Es la distancia entre **lo que el sistema declara que verificó** y **lo que el código realmente comprueba o ejecuta**.

Se encontraron bloqueantes en la seguridad del licenciamiento, en la ejecución autónoma y en la validez de las pruebas. También hay nuevas funciones de diagnóstico que devuelven estados positivos constantes sin medir ni configurar los protocolos que dicen verificar.

**No recomiendo distribuir OmniNet como producto comercial ni habilitar su autorreparación real hasta cerrar los P0 y demostrar las pruebas de aceptación de esta auditoría.**

### Estado resumido

| Área | Evaluación |
|---|---|
| Arquitectura y organización | Avance real |
| Diagnóstico de red | Parcial; algunas métricas no representan lo que afirman |
| Optimización y reparación | Requiere validación en sistemas reales |
| Hermes / razonamiento autónomo | No demostrado como agente LLM funcional |
| Sandbox | No es un sandbox de seguridad |
| Memoria y auto-mejora | Persistencia real; validación de aprendizaje insuficiente |
| Licencias y pagos | Bloqueante |
| Pruebas | Evidencia de aprobación no confiable en su estado actual |
| Producción SaaS | No apto todavía |

---

## 2. Hallazgos priorizados

### P0 — Bloqueantes: corregir antes de distribuir o permitir ejecución real

#### OMNI-024 — Secreto HMAC de licencias incluido en el cliente

**Archivo:** `netopt/licensing.py`  
**Referencias:** líneas 19, 56–66 y 69–99.

**Evidencia**
- El código contiene un secreto predeterminado: `omninet-global-saas-hmac-2026-secret`.
- El cliente contiene tanto la función que genera licencias como la que las verifica.
- La firma HMAC se genera y valida en el mismo módulo distribuible.

**Impacto**
Un usuario puede inspeccionar el ejecutable o el código, recuperar el secreto y fabricar claves aceptadas por cualquier instalación que use ese secreto predeterminado. Si el servidor utiliza otro secreto por variable de entorno, el cliente y el servidor pueden terminar validando claves con secretos diferentes.

**Corrección**
1. Migrar a firma asimétrica Ed25519.
2. Mantener la clave privada exclusivamente en el backend.
3. Distribuir únicamente la clave pública de verificación en el cliente.
4. Eliminar secretos predeterminados, claves maestras y cualquier ruta de emisión local.
5. Rotar el secreto anterior y definir migración/revocación de claves ya emitidas.
6. Validar licencia, producto, plan, expiración, estado y dispositivo desde una autoridad central.

**Aceptación**
- El cliente no puede generar una licencia válida.
- Una clave inventada, manipulada, expirada o revocada es rechazada.
- Extraer el ejecutable no permite obtener material secreto de firma.

#### OMNI-025 — El centinela arranca habilitado y puede modificar el equipo sin una activación explícita

**Archivos:** `netopt/auto_trigger.py`, `main.py`  
**Referencias:** `AutoSentinel.__init__()` y `start_api_server()`.

**Evidencia**
- `AutoSentinel` tiene `enabled=True` por defecto.
- Si no recibe un HAL, construye uno con `get_hal(dry_run=False)`.
- Al iniciar el servidor local, `start_api_server()` inicia el centinela automáticamente.
- El bucle ejecuta `check_health_and_auto_heal()` cada 60 segundos.
- Ante determinadas anomalías, el centinela ejecuta triage y optimización con `do_exec=True` cuando el HAL no está en dry-run.

**Impacto**
Abrir la aplicación puede habilitar reparaciones reales en segundo plano sin que el usuario haya aprobado una acción concreta. Un cambio de DNS, rutas, parámetros TCP o configuración de red puede interrumpir la conectividad o afectar una configuración corporativa/VPN.

**Corrección**
1. El estado inicial debe ser `disabled` y `dry_run=True`.
2. El primer inicio debe limitarse a diagnóstico y propuesta.
3. La ejecución real debe requerir consentimiento explícito y visible.
4. Aprobar una reparación concreta no debe autorizar futuras reparaciones distintas.
5. Mantener registro de estado anterior, cambio aplicado, resultado y rollback.
6. Si no puede verificarse la restauración, detener nuevas mutaciones.

**Aceptación**
Después de instalar e iniciar OmniNet, no se modifica ningún parámetro del sistema hasta que el usuario autorice expresamente esa operación. Reiniciar la aplicación no reactiva permisos anteriores silenciosamente.

---

### P1 — Críticos: corregir antes de declarar el sistema verificado

#### OMNI-026 — Hermes llama “sandbox” a un subproceso sin aislamiento de seguridad

**Archivo:** `hermes/harness.py`  
**Referencias:** líneas 87–115.

**Evidencia**
`execute_python()` ejecuta código mediante:

`subprocess.run([sys.executable, "-c", clean_code], ...)`

No se observa aislamiento de sistema de archivos, red, procesos, credenciales, permisos, namespaces, contenedor ni usuario restringido. El proceso hereda los permisos del usuario que ejecuta OmniNet.

**Impacto**
Un subproceso no equivale a un sandbox. Si en el futuro el modelo ejecuta código generado, ese código puede leer archivos accesibles, utilizar la red, iniciar procesos y modificar recursos con los permisos del usuario.

**Corrección**
1. Cambiar el nombre a `subprocess_runner` hasta implementar aislamiento real.
2. Ejecutar código no confiable en un entorno aislado con usuario sin privilegios.
3. Bloquear red por defecto, limitar filesystem a un directorio temporal y montar el proyecto como solo lectura.
4. Aplicar límites de CPU, memoria, procesos, tiempo y tamaño de salida.
5. No exponer secretos ni variables de entorno del proceso anfitrión.
6. Separar las herramientas de lectura, escritura y ejecución; aprobar las mutaciones.

**Aceptación**
Una prueba de escape intenta leer un archivo externo, acceder a credenciales, abrir sockets y modificar el proyecto anfitrión. Todas esas acciones deben fallar por controles del sistema operativo, no por instrucciones del prompt.

#### OMNI-027 — `run_turn()` no invoca ningún modelo de lenguaje

**Archivo:** `hermes/harness.py`  
**Referencias:** líneas 170–199.

**Evidencia**
`run_turn()` usa una condición de palabras clave. Si detecta ciertas expresiones ejecuta un script fijo de prueba; en los demás casos devuelve un texto genérico. No se observa una llamada HTTP al proveedor, selección efectiva de modelo, interpretación de respuestas del LLM ni ciclo de tool-calling en esa función.

El resultado puede indicar `model_used=self.config.model`, aunque esa función no haya consultado ese modelo.

**Impacto**
La presencia de configuración DeepSeek/OpenAI y de herramientas registradas no demuestra que Hermes razone mediante esos modelos. El comportamiento actual es un despachador determinista básico, no un agente cognitivo conectado al LLM.

**Corrección**
1. Implementar la llamada real al proveedor configurado.
2. Validar respuesta, errores, timeout y autenticación.
3. Implementar ciclo de herramientas: solicitud del modelo → validación de argumentos → autorización → ejecución → resultado → respuesta final.
4. Registrar proveedor y modelo realmente usados; nunca inferirlos desde la configuración.
5. Mantener el modo determinista como modo explícito de prueba/offline.

**Aceptación**
Una prueba con servidor LLM simulado demuestra petición, respuesta, tool call, ejecución de herramienta y respuesta final. Si el proveedor no responde, Hermes informa fallo y no simula que razonó.

#### OMNI-028 — La auto-mejora puede registrar éxito sin haber probado nada

**Archivo:** `hermes/self_improvement.py`  
**Referencias:** `distill_skill()` y `run_evolution_cycle()`.

**Evidencia**
- `distill_skill()` incrementa `success_count` de una habilidad existente sin recibir ni verificar un resultado exitoso.
- `run_evolution_cycle(run_tests=False)` mantiene `tests_ok=True`.
- En ese caso el informe puede dejar `zero_regressions_verified=True` aunque `tests_executed=False`.

**Impacto**
La memoria puede acumular éxitos ficticios y el motor puede emitir un informe de cero regresiones sin ejecutar pruebas. Esto contamina el aprendizaje y la confianza del estado del proyecto.

**Corrección**
1. Separar `attempt_count`, `success_count` y `failure_count`.
2. Solo incrementar éxito después de una verificación observable.
3. Si se omiten pruebas, `zero_regressions_verified` debe ser `false` o `null`, nunca `true`.
4. Diferenciar `NOT_RUN`, `PASSED`, `FAILED` y `ERROR`.
5. Guardar evidencia: comando, código de salida, duración, commit probado y artefactos.
6. No convertir una ejecución simulada en una habilidad exitosa.

**Aceptación**
Con `run_tests=False`, el informe dice explícitamente `NOT_RUN` y no afirma cero regresiones. Una habilidad solo aumenta su contador de éxito tras una prueba que realmente pasa.

#### OMNI-029 — Telemetría declarada como verificada, pero módulo ausente del repositorio

**Archivos:** `PROJECT_STATE.md`, `tests/test_audit_executive_remediation.py`, árbol `netopt/`.

**Evidencia**
- `PROJECT_STATE.md` declara que existe `netopt/telemetry.py` y que la telemetría empírica está verificada.
- La prueba `test_empirical_device_probes_and_global_telemetry_collector` importa `netopt.telemetry`.
- El árbol completo de `main` revisado no contiene `netopt/telemetry.py`.
- La consulta directa de ese archivo devuelve 404.

**Impacto**
La prueba versionada no puede importar ese módulo en el commit examinado. Por tanto, la declaración de 98/98 pruebas aprobadas no es reproducible desde el contenido publicado de `main`, salvo que se haya probado otro árbol o existiera un archivo local no incorporado al commit.

**Corrección**
1. Incorporar el módulo real o retirar las declaraciones y pruebas que dependen de él.
2. Verificar que todos los imports del conjunto de pruebas existan en el commit.
3. Ejecutar la suite desde un checkout limpio del SHA exacto.
4. Adjuntar logs de ejecución y código de salida como artefacto de CI.
5. Actualizar `PROJECT_STATE.md` solo después de comprobar el commit publicado.

**Aceptación**
Un checkout limpio del HEAD instala dependencias y ejecuta toda la suite sin archivos locales, secretos ni recursos no versionados.

#### OMNI-030 — Pruebas de remediación no ejercitan el comportamiento que dicen validar

**Archivo:** `tests/test_audit_executive_remediation.py`

**Evidencia**
Varias pruebas verifican condiciones construidas dentro de la propia prueba, no el endpoint o la lógica productiva. Ejemplos:
- T-05 comprueba que un ID está dentro de una lista local creada en el test; no llama al webhook ni demuestra idempotencia concurrente.
- T-14 y T-15 construyen variables locales para simular validaciones; no llaman a `/v1/chat`.
- T-16 calcula localmente si una fecha está vencida; no verifica el flujo real de licencia.
- T-17 compara dos números constantes; no consume la cuota del backend.
- T-18 construye un diccionario filtrado dentro del test; no llama al endpoint GET real.
- T-19 prueba un booleano local; no consulta el endpoint administrativo.
- T-20 comprueba una constante y una suma; no envía un POST HTTP sobredimensionado.

**Impacto**
La suite puede aprobar aunque el endpoint real esté mal implementado. Los nombres de los tests transmiten una cobertura mayor que la realmente demostrada.

**Corrección**
1. Probar handlers HTTP completos con solicitudes reales en servidor de prueba.
2. Probar webhook con firma correcta, firma incorrecta, evento duplicado y solicitudes concurrentes.
3. Probar licencias con backend simulado, dispositivos excedidos, expiración y revocación.
4. Probar cuotas con contador persistente y solicitudes concurrentes.
5. Probar CSRF, origen, token y límites de payload mediante peticiones HTTP.
6. Reservar pruebas unitarias de funciones auxiliares para lógica aislada; no presentarlas como integración.

**Aceptación**
Cada requisito de seguridad debe tener al menos una prueba que invoque el componente productivo responsable y falle si se elimina la validación.

#### OMNI-031 — Incompatibilidad declarada: Python 3.9/3.10 frente a `tomllib`

**Archivos:** `pyproject.toml`, `tests/test_audit_executive_remediation.py`.

**Evidencia**
`pyproject.toml` declara `requires-python = ">=3.9"`, pero T-22 importa `tomllib`, incorporado a la biblioteca estándar en Python 3.11.

**Impacto**
La suite falla en Python 3.9 y 3.10 si no existe un fallback o dependencia compatible.

**Corrección**
Usar `tomli` como fallback para Python anterior a 3.11 o elevar explícitamente la versión mínima del proyecto a 3.11 y alinear documentación, instalador y CI.

**Aceptación**
La matriz de CI coincide con las versiones realmente soportadas y todas pasan.

#### OMNI-032 — Webhook: idempotencia susceptible a carreras y plan no ligado a precio/producto verificado

**Archivo:** `cloud_server/proxy_server.py`  
**Referencias:** bloque `/v1/webhooks/payment`.

**Evidencia**
- El ID del evento se comprueba y registra en un archivo JSON local.
- El servidor utiliza `ThreadingHTTPServer`; no se observa un bloqueo transaccional ni una restricción única de base de datos alrededor de la comprobación y creación.
- El plan se obtiene de `custom_data.plan` / `metadata.plan` o de texto de nombre/descripción del producto.
- No se observa comprobación estricta de IDs autorizados de precio/producto, importe y moneda antes de emitir la licencia.

**Impacto**
Dos entregas concurrentes del mismo evento pueden superar la comprobación antes de que se guarde el ID y generar más de una licencia. Además, la selección del plan no está ligada de forma inequívoca al precio que el proveedor confirmó como pagado.

**Corrección**
1. Guardar eventos en una tabla transaccional con `event_id` único.
2. Reclamar el evento y crear la licencia en una única transacción.
3. Mapear IDs inmutables de producto/precio del proveedor a planes internos.
4. Verificar importe, moneda, estado, producto y tipo de evento.
5. Rechazar metadatos de plan no autorizados.
6. Mantener la respuesta idempotente incluso ante reintentos concurrentes.

**Aceptación**
Cien entregas paralelas del mismo evento generan una sola licencia y un solo registro de pago. Un precio/moneda/producto no autorizado nunca concede Family/Pro.

#### OMNI-033 — API local: las peticiones loopback eluden el token CSRF

**Archivo:** `main.py`  
**Referencias:** `OmniNetAPIHandler.do_POST()`.

**Evidencia**
La API acepta cualquier petición POST desde loopback sin exigir `X-OmniNet-Token`. El token solo se comprueba para clientes que no son loopback. No se observa una validación estricta de `Origin`/`Host` para las operaciones mutantes.

**Impacto**
El token no protege frente a todas las peticiones originadas desde el navegador del propio equipo. Debe evaluarse el riesgo de CSRF y DNS rebinding para una API local que puede cambiar configuraciones del sistema.

**Corrección**
1. Exigir token impredecible también en loopback para operaciones mutantes.
2. Validar `Origin` y `Host` contra el origen local esperado.
3. No aceptar `csrf_token` dentro del JSON como sustituto de una cabecera protegida.
4. Aplicar autenticación y autorización por operación.
5. Añadir pruebas con origen externo, origen nulo, host alternativo y peticiones cross-site.

**Aceptación**
Una página externa no puede activar optimización, reparación, mantenimiento ni ejecución de subagentes mediante el navegador del usuario.

#### OMNI-034 — Las funciones de diagnóstico de estándares devuelven afirmaciones constantes

**Archivo:** `netopt/diagnostics.py`  
**Evidencia directa:** último commit `91398688b053858c890b67ccf94cf31c9ac5001e`, función `check_webtransport_prioritization_and_rfc9205_bcp56_status()`.

La función devuelve, entre otros:
- `webtransport_incremental_delivery_active: True`
- `unreliable_datagram_prioritization: True`
- `bcp56_idempotency_rules_enforced: True`
- `bcp56_canonical_status_handling: True`

No inspecciona una implementación WebTransport, no abre una sesión QUIC/HTTP/3, no mide prioridades ni verifica una pila HTTP. Devuelve valores constantes.

El commit anterior añadió el mismo patrón en `check_rfc8446_tls13_antireplay_and_rfc9293_tcp_status()`: tickets de un solo uso, ventanas anti-replay, ISN criptográfico y mitigación RST aparecen como `True` sin inspeccionar el kernel, servidor TLS ni conexiones reales. También se añadió un valor fijo de reducción ACK de 28,5% en `check_cake_diffserv4_ack_filter_status()`.

**Impacto**
Se presentan estándares y propiedades de protocolos como activos/verificados sin evidencia del sistema. Esto puede inducir al usuario a creer que OmniNet activa o protege mecanismos que en realidad no controla.

**Corrección**
1. Renombrar estas funciones como `capability_reference` o `standards_checklist` si solo describen conceptos.
2. Para afirmar `active`, consultar el estado real de la pila, configuración, implementación o sesión correspondiente.
3. Para afirmar `compliant`, ejecutar pruebas de conformidad con entradas y resultados observables.
4. Devolver `UNKNOWN` / `NOT_SUPPORTED` / `NOT_CONFIGURED` cuando no haya evidencia.
5. Eliminar métricas de rendimiento constantes; medirlas con una carga reproducible y guardar metodología.

**Aceptación**
Ningún indicador de estado positivo se devuelve sin una fuente de evidencia observable, con plataforma, método y timestamp.

---

### P2 — Importantes: corregir para obtener mediciones confiables

#### OMNI-035 — La medición denominada bufferbloat no genera una carga de saturación representativa

**Archivo:** `netopt/diagnostics.py`  
**Referencias:** `measure_target_metrics()` y `check_bufferbloat()`.

**Evidencia**
- `measure_target_metrics()` mide conexiones TCP a un puerto fijo y denomina pérdida de paquetes al porcentaje de intentos TCP que no conectan.
- `check_bufferbloat()` compara esa latencia con una carga compuesta por pequeñas consultas DNS UDP y conexiones TCP cortas.
- No se genera una carga sostenida y controlada de subida/bajada que sature el enlace para observar la latencia bajo carga.

**Impacto**
El resultado no equivale a una prueba de bufferbloat bajo saturación. Puede clasificar incorrectamente la calidad de la conexión y alimentar decisiones de auto-reparación con una señal débil.

**Corrección**
Implementar una prueba de carga controlada, con límites de ancho de banda, duración, tráfico ascendente/descendente y medición de latencia simultánea. Diferenciar pérdida TCP de pérdida ICMP/UDP y etiquetar claramente cada métrica.

**Aceptación**
Comparar resultados con una herramienta de referencia en enlaces con bufferbloat conocido y en enlaces sin bufferbloat; documentar repetibilidad y margen de error.

#### OMNI-036 — El sistema inicia varios ciclos autónomos con responsabilidades superpuestas

**Archivos:** `main.py`, `netopt/auto_trigger.py`, `netopt/autonomous_scheduler.py`.

**Evidencia**
El inicio de la API arranca el centinela cada 60 segundos y el scheduler cada 600 segundos. Ambos realizan diagnósticos y pueden proponer o ejecutar acciones sobre la misma red. El centinela usa HAL real por defecto; el scheduler arranca con `auto_execute=False`.

**Impacto**
Hay duplicación de barridos, consumo innecesario y posibilidad de decisiones concurrentes o contradictorias. El límite de seguridad no debería depender de que dos motores mantengan estados separados.

**Corrección**
Centralizar la planificación y la autorización de mutaciones. Compartir una cola de acciones con exclusión mutua, deduplicación, prioridades, cooldown y un único administrador de snapshots/rollback.

**Aceptación**
Una misma anomalía detectada por ambos motores produce una única tarea autorizable, una sola mutación y un solo registro de resultado.

#### OMNI-037 — Persistencia local de datos críticos sin garantías transaccionales suficientes

**Archivos:** `cloud_server/proxy_server.py`, `netopt/licensing.py`, `hermes/self_improvement.py`, `netopt/autonomous_scheduler.py`.

**Evidencia**
Se observan archivos JSON locales para licencias, eventos procesados, feedback, memoria, evolución y tareas. Varios guardados sobrescriben directamente el archivo y capturan excepciones sin propagar el fallo.

**Impacto**
Una interrupción durante la escritura puede corromper el estado; procesos concurrentes pueden sobrescribir actualizaciones; errores de persistencia pueden quedar ocultos.

**Corrección**
Usar SQLite transaccional para estado local crítico o una base de datos central para SaaS. Para archivos no críticos, escribir temporal + fsync + replace atómico, validar esquema y registrar errores de persistencia.

**Aceptación**
Pruebas de interrupción, corrupción y concurrencia no pierden licencias, eventos, historial ni memoria verificada.

---

## 3. Avances reales respecto de la revisión anterior

La comparación entre `822924b5495988c6d170c13fb7067118e02d2eba` y el HEAD actual muestra 45 commits nuevos. Entre los cambios positivos observables:

- Se incorporó el ciclo cognitivo Hermes: `foresee → executor → reflect`.
- Se añadió persistencia de reflexiones y memoria de patrones.
- Se añadieron tests específicos para planificación, simulación, fallo, rollback y replanificación.
- El proxy ahora valida criptográficamente las firmas Stripe y Lemon Squeezy y falla cerrado cuando faltan secretos.
- La API local limita el cuerpo POST a 1 MB, enlaza a `127.0.0.1` por defecto y excluye la clave API completa de las respuestas de configuración.
- El scheduler tiene `auto_execute=False` por defecto y el MCP interpreta `execute` como falso cuando se omite.

Estos avances se reconocen. No eliminan los hallazgos nuevos ni justifican declarar producción verificada.

---

## 4. Plan de corrección secuencial

No conviene abrir más frentes de estándares de red hasta cerrar esta secuencia.

| Orden | Hallazgos | Trabajo | Condición para avanzar |
|---:|---|---|---|
| 1 | OMNI-024 | Firma asimétrica y retirada del secreto del cliente | Licencias no falsificables desde el cliente |
| 2 | OMNI-025 | Centinela deshabilitado y dry-run inicial | Ninguna mutación sin consentimiento |
| 3 | OMNI-026 | Aislamiento real de ejecución | Pruebas de escape bloqueadas |
| 4 | OMNI-027 | Conexión LLM real y tool-calling | Modelo y herramientas comprobables |
| 5 | OMNI-028 | Evidencia de éxito y auto-mejora honesta | Ningún éxito sin verificación |
| 6 | OMNI-029 | Incorporar o retirar telemetría ausente | Checkout limpio consistente |
| 7 | OMNI-030 / 031 | Pruebas de integración y compatibilidad Python | CI reproducible en versiones soportadas |
| 8 | OMNI-032 | Webhook transaccional y catálogo de precios | Idempotencia concurrente demostrada |
| 9 | OMNI-033 | Protección CSRF de API local | Peticiones externas rechazadas |
| 10 | OMNI-034 | Diagnósticos basados en evidencia | Sin estados positivos constantes |
| 11 | OMNI-035 / 036 / 037 | Métricas, coordinación y persistencia | Validación operativa estable |

---

## 5. Pruebas de aceptación obligatorias

Antes de declarar el producto apto:

1. **Licencias:** fabricar claves, modificar planes, revocar, expirar y exceder dispositivos.
2. **Pagos:** firma inválida, secreto ausente, evento repetido y 100 entregas concurrentes.
3. **Ejecución autónoma:** instalar, abrir, reiniciar y dejar el sistema funcionando sin aprobar cambios; comprobar que no modifica el equipo.
4. **Sandbox:** intentar leer archivos del host, acceder a red, robar variables de entorno y crear procesos.
5. **Hermes:** demostrar una llamada real al proveedor y un ciclo completo de tool-calling.
6. **Auto-mejora:** ejecutar con pruebas omitidas, fallidas y aprobadas; cada estado debe reflejar exactamente lo sucedido.
7. **Suite limpia:** checkout del SHA auditado, instalación reproducible y `python -m unittest discover -s tests -v`.
8. **Diagnóstico:** comprobar que cada estado `ACTIVE` o `COMPLIANT` proviene de una lectura o prueba real.
9. **Plataformas:** probar Windows, Linux y macOS por separado; no inferir compatibilidad multiplataforma desde mocks.
10. **Rollback:** inducir una degradación real controlada y comprobar restauración efectiva, no solo generación de snapshot.

---

## 6. Estado de evidencia y límites de esta auditoría

- El repositorio y el árbol de `main` fueron consultados directamente.
- Se inspeccionaron archivos de implementación, pruebas, manifiestos y diffs recientes.
- Se verificó que el HEAD es posterior al commit anterior por 45 commits.
- No se ejecutó la suite de pruebas ni se inspeccionó un equipo físico.
- El dato `98/98 tests aprobados` procede de `PROJECT_STATE.md`; no se considera evidencia independiente y entra en conflicto con la ausencia de `netopt/telemetry.py` requerida por una prueba versionada.
- No se auditó el despliegue real de Supabase, secretos del proveedor de pagos, configuración de DNS/QUIC del equipo ni el binario `dist/OmniNet.exe`.

**Conclusión:** hay una base de arquitectura y trabajo de ingeniería aprovechable, pero hoy el riesgo principal es la verificación ficticia de capacidades y la posibilidad de ejecutar cambios reales sin una autorización suficientemente estricta. Primero hay que hacer que el sistema diga la verdad, mida de verdad y solo actúe con permiso verificable. Después conviene ampliar capacidades.
