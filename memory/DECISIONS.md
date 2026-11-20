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

---

## [2026-11-10] DEC-005: Telemetría Empírica In Situ y Colector Global Anónimo
- **Decisión:** Exigir pruebas empíricas reales sobre el hardware del host (`netopt/telemetry.py` → `run_real_device_empirical_probes()`) en cada ciclo autónomo y conectar de forma anónima con el colector global (`/v1/telemetry/report` y Supabase) para retroalimentar las heurísticas del optimizador.
- **Alternativas consideradas:** Depender únicamente de mocks o diagnósticos sintéticos en memoria. Descartado: ocultaba degradaciones reales de Wi-Fi, ARP, DNS o sockets del anfitrión.
- **Consecuencias:** Cada ciclo contrasta la realidad física del dispositivo contra las pruebas automatizadas y valida la cadena completa de telemetría.

---

## [2026-11-12] DEC-006: Estándares DNS Cifrados (DDR/DNR) y Reporte de Errores (DNER/EDE) en Scheduler y Hermes
- **Decisión:** Integrar las categorías `ENCRYPTED_DNS_DISCOVERY` (RFC 9462/9463 DDR y RFC 9540 DNR) y `DNS_ERROR_REPORTING` (RFC 9578 DNER y RFC 8914 EDE) tanto en `AutonomousTaskScheduler` (`netopt/autonomous_scheduler.py`) como en `ForeseePlanner` y `HermesExecutor` (`hermes/foresee.py`, `hermes/executor.py`) — Ciclos 96–98.
- **Alternativas consideradas:** Mantener solo latencia ICMP/DNS básica sin descubrimiento SVCB ni decodificación EDE. Descartado: impedía detectar silenciosamente fallos de resolución DNS cifrada o secuestro de resolver local.
- **Consecuencias:** Diagnóstico proactivo no mutante de resolvers cifrados y errores extendidos DNS en los ciclos de 10 minutos y en planes cognitivos Hermes.

---

## [2026-11-13] DEC-007: Validación Pydantic v2, Sanitización de Claves y Comparación Timing-Safe en API & Proxy
- **Decisión:** Estandarizar esquemas Pydantic v2 (`ExecuteFlagRequest`, `LLMConfigUpdateRequest`) en `netopt/schemas.py`, rechazar `Content-Length` inválido/negativo con HTTP 400, aplicar comparación `hmac.compare_digest` para tokens/Bearer, enmascarar claves cortas (`_sanitize_llm_config`), y sustituir comprobaciones por subcadena (`"localhost" in base_url`) por validación de hostname vía `urlparse` (`_is_local_llm_url`) en `netopt/llm_gateway.py` — Ciclos 99–100.
- **Alternativas consideradas:** Validación manual ad-hoc de JSON en cada endpoint y comparación directa `==` de tokens. Descartado por riesgo de bypass SSRF, fugas de claves cortas y ataques de temporización.
- **Consecuencias:** Frontera HTTP/LLM endurecida y verificada con `tests/test_fastapi_app.py` y `tests/test_pydantic_schemas.py`.

---

## [2026-11-14] DEC-008: Migración de Identidad `DeviceDID` a Firma Asimétrica Real Ed25519 (`cryptography`)
- **Decisión:** Reemplazar la firma simétrica HMAC-con-clave-pública en `netopt/micro_internet.py` por criptografía asimétrica **Ed25519** (`Ed25519PrivateKey` / `Ed25519PublicKey`) mediante `cryptography`, exportando documentos `Ed25519VerificationKey2020` con migración automática de identidades legadas — Ciclo 101.
- **Alternativas consideradas:** Mantener HMAC-SHA256 sobre la clave pública o implementar curvas elípticas artesanales. Descartado: HMAC con clave pública no provee autenticación asimétrica real y el código criptográfico artesanal viola la política de bibliotecas maduras.
- **Consecuencias:** Identidades federadas criptográficamente verificables (firmas de 128 caracteres hex) y 7/7 pruebas aprobadas en `tests/test_micro_internet.py`.

---

## [2026-11-14] DEC-009: Endurecimiento Sistemático de Fronteras de Entrada (CWE-22, CWE-78, Flags y Esquemas URL)
- **Decisión:** Aplicar validación estricta en todas las entradas que alcanzan el sistema de archivos, subprocesos o clientes HTTP — Ciclos 102, 103, 109, 113, 114, 116 y 117:
  1. `netopt/rollback.py`: `[A-Za-z0-9_-]+` + `os.path.realpath()` contra Path Traversal (CWE-22) en `load_snapshot()`.
  2. `netopt/hal.py`: `_validate_iface_name()` en `LinuxHAL.renew_dhcp_lease()` (CWE-78) y validación de interfaz/IPs en `DarwinHAL.set_dns_servers()`.
  3. `netopt/diagnostics.py` y `netopt/telemetry.py`: `_validate_probe_target()` (IP o hostname RFC 1123; bloquea flags `-*` y metacaracteres), devolviendo HTTP 400 en `/api/pmtu`.
  4. `netopt/adapters.py`, `netopt/telemetry.py` y `netopt/licensing.py`: validación obligatoria de esquema `http`/`https` vía `urlparse` antes de cualquier petición `httpx` o `urllib.request.urlopen` (bloquea `file://`, `ftp://`), además de acotar timeouts.
  5. `netopt/elevation.py`: `subprocess.list2cmdline()` en Windows (`ShellExecuteW`) y resolución absoluta `shutil.which("sudo"|"pkexec")` + `os.execv` con `--` en POSIX.
- **Alternativas consideradas:** Confiar en validación únicamente en la capa FastAPI. Descartado porque los módulos son invocados directamente por CLI, MCP, Hermes y tests.
- **Consecuencias:** Defensa en profundidad en cada frontera de módulo sin romper compatibilidad con llamadas válidas.

---

## [2026-11-14] DEC-010: Cumplimiento Estricto `dry-run-by-default` y Tabla de Despacho en Ejecutores
- **Decisión:** Exigir `should_apply = bool(execute and not (getattr(self.hal, "dry_run", False) is True))` en toda ruta de mutación (`NetworkOptimizer.execute_plan`, `NetworkRepairEngine.execute_triage_repair`, `HermesSelfImprovementEngine.run_evolution_cycle`), fijar `execute=False` por defecto en `execute_subagent_by_id()`, y reemplazar cadenas largas `if/elif` por tablas de despacho (`dict`) — Ciclos 104, 108, 112 y 119.
- **Alternativas consideradas:** Permitir que cada método HAL individual decida si simula o aplica sin normalizar en el orquestador. Descartado: generaba reportes contradictorios (`plan.status = "verified"` cuando `hal.dry_run=True`).
- **Consecuencias:** Honestidad epistemológica uniforme (`SIMULATED` vs `SUCCEEDED`), código más compacto y eliminación de ramas duplicadas.

---

## [2026-11-14] DEC-011: Concurrencia Segura (`threading.Event`, `RLock`) y Persistencia JSON Atómica
- **Decisión:** Sustituir todos los `time.sleep()` bloqueantes en bucles de fondo por `threading.Event.wait()` con despertar inmediato en `stop()`, proteger singletons y estados compartidos con `threading.RLock()`, acotar colas/workers (`max_workers` `[1, 16]`, tope 200 sesiones en `HermesOrchestrator`) y migrar toda escritura JSON crítica a patrón atómico (`tempfile.mkstemp` + `os.replace`) — Ciclos 105, 106, 110, 111, 115, 116, 119 y 120.
- **Alternativas consideradas:** `time.sleep` corto con polling o escritura directa `open(..., "w")`. Descartado: `time.sleep(60)`/`(600)` bloqueaba apagados limpios y la escritura directa corrompía archivos bajo `ThreadingHTTPServer` o hilos concurrentes.
- **Consecuencias:** Módulos afectados (`auto_trigger.py`, `autonomous_scheduler.py`, `persistence.py`, `hermes/executor.py`, `hermes/orchestrator.py`, `hermes/self_improvement.py`, `cloud_server/proxy_server.py`, `netopt/telemetry.py`, `netopt/licensing.py`) operan sin condiciones de carrera ni archivos truncados.

---

## [2026-11-14] DEC-012: Endurecimiento JSON-RPC 2.0 en `mcp_server.py` y Límites Seguros en `netopt/cli.py`
- **Decisión:** Extraer `process_jsonrpc_line()` y `_write_jsonrpc()` en `mcp_server.py` con códigos estándar JSON-RPC 2.0 (`-32700`, `-32600`, `-32601`, silencio en notificaciones sin `id`) y acotar `poll_interval_sec` (`[5, 86400]`) y `max_hops` (`[1, 30]`); en `netopt/cli.py`, parametrizar `main(argv=None) -> int`, acotar `--interval` (`[5, 86400]s`) y `--cycles` (`>= 1`), manejar `KeyboardInterrupt` llamando `daemon.stop()` y usar `default=str` en `repair --json` — Ciclos 107 y 118.
- **Alternativas consideradas:** Dejar parseo inline en `stdin` y aceptar intervalos `<= 0` en CLI/MCP. Descartado por riesgo de busy-loop infinito y errores no conformes al protocolo MCP.
- **Consecuencias:** Servidor MCP y CLI 100% conformes, testables herméticamente y protegidos contra parámetros fuera de rango.

---

## [2026-11-15] DEC-013: Arquitectura de Ciclos/Sub-Ciclos y Vigilancia Persistente de Herramientas Antigravity
- **Decisión:** Estructurar la mejora continua en ciclos y sub-ciclos **Periódicos** (macro 40m + vigilancia Antigravity), **Por Necesidad** (reactivos ante fallos/regresiones/seguridad), **Ocasionales** (suite completa, paridad documental, migración de bibliotecas) y **Por Voluntad** (innovación RFC/kernel), integrando la búsqueda y uso persistente de actualizaciones y herramientas de Antigravity (`run_workflow`, `swarm`, `schedule`, `search_marketplace`).
- **Alternativas consideradas:** Mantener un único ciclo lineal de 40 minutos. Descartado tras las lecciones de la auditoría H-01..H-10 y el endurecimiento `execute is True` (Ciclos 121–131).
- **Consecuencias:** Mayor velocidad de respuesta ante regresiones, aprovechamiento sistemático de nuevas herramientas Antigravity y propagación uniforme en `AGENTS.md`, `AUTONOMOUS_OPERATIONAL_MANIFESTO.md` y `.continuity/`.
