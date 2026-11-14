# Patrones de Éxito Verificados (`SUCCESS_PATTERNS.md`)
*Soluciones arquitectónicas y operativas probadas con evidencia reproducible en OmniNet.*

---

## [2026-11-05] SUC-001: Invariante Zero NetLoss y Snapshot Manager Reversible
- **Problema:** Riesgo de desconexión catastrófica o degradación de red al aplicar cambios en el stack TCP/IP o adaptadores.
- **Solución:** Implementación de `SnapshotManager` (`netopt/rollback.py`) que captura el estado exacto del registro y de la pila de red antes de cualquier cambio, con prueba activa de gateway reachability; si falla, revierte automáticamente en menos de 2.5 segundos.
- **Contexto donde aplica:** Toda optimización ejecutada por `Optimizer` o `triage_repair`.
- **Evidencia:** 100% de tests unitarios aprobados (`test_rollback_manager_snapshot`, `test_t13_rollback_verification_gate`).
- **Límites conocidos:** Requiere privilegios administrativos en el sistema operativo anfitrión.

---

## [2026-11-06] SUC-002: Conector PostgREST Zero-Dependency para Supabase SaaS
- **Problema:** Dependencia de librerías externas pesadas o asíncronas para conectar con Supabase en entornos portables de Windows.
- **Solución:** `cloud_server/supabase_client.py` implementado con la librería estándar `urllib.request` y serialización JSON pura, manejando autenticación diferenciada (`SUPABASE_ANON_KEY` vs `SUPABASE_SERVICE_ROLE_KEY`).
- **Contexto donde aplica:** Verificación de licencias, telemetría SaaS y control de cuotas.
- **Evidencia:** Conexión en vivo exitosa contra `zptywckomuewpcshldcg.supabase.co` validando licencias activas y pasando tests `test_global_saas_licensing_and_quota`.
- **Límites conocidos:** Conexión sincrónica con timeout de 10 segundos.

---

## [2026-11-07] SUC-003: Arnés y Orquestador Hermes con Compuerta de Regresión Cero
- **Problema:** Necesidad de auto-mejora autónoma del agente sin riesgo de introducir regresiones de código.
- **Solución:** `HermesSelfImprovementEngine` (`hermes/self_improvement.py`) con entorno de ejecución aislado `execute_python(code, timeout_sec=15.0)` y compuerta estricta que aborta la evolución si `unittest discover` no aprueba al 100%.
- **Contexto donde aplica:** Ciclo recurrente de 40 minutos del agente IA.
- **Evidencia:** Múltiples ciclos evolutivos exitosos (`evo-1794073242`, `evo-1794075641`) manteniendo 53/53 tests aprobados.
- **Límites conocidos:** Las habilidades destiladas deben ser validadas en tests unitarios formales.

---

## [2026-11-08] SUC-004: Auditoría Sistemática Anti-Alucinación (`ERR-004` a `ERR-013`) con Mocks Negativos
- **Problema:** Riesgo de valores estáticos de éxito (`or True`), procesos huérfanos (`Popen`), promedios distorsionados con `0.0ms` en caídas de red (100% packet loss), y parámetros MCP declarados pero ignorados.
- **Solución:** Aplicación sistemática del protocolo `.agents/skills/hallucination-control/SKILL.md` (Sección 6) sobre todos los módulos de `netopt/`, `hermes/`, `cloud_server/`, `main.py` y `mcp_server.py`, acompañando cada corrección con pruebas unitarias de caso negativo (`disabled`, `100% loss`, HTTP `403`, `REVERTED`, `No ARP Entries`).
- **Contexto donde aplica:** Todo diagnóstico, sub-agente del ecosistema, motor de rollback y herramienta MCP.
- **Evidencia:** Incremento de la suite de 53 a 62 tests unitarios (`python -m unittest discover -s tests -v` -> 62/62 OK, 0 `ResourceWarning`).
- **Límites conocidos:** Requiere mantener pruebas negativas por cada nueva heurística o herramienta añadida.

---

## [2026-11-09] SUC-005: Ciclo Cognitivo Foresee → Executor → Reflect con Aprendizaje Persistente
- **Problema:** Riesgo de bucles ciegos donde un agente reintenta indefinidamente optimizaciones fallidas o reporta falsos éxitos en entornos simulados/dry-run.
- **Solución:** Implementación de arquitectura tripartita en `hermes/` (`foresee.py`, `executor.py`, `reflect.py`, `cognitive_loop.py`). Todo paso declara criterio de éxito observable. Si una mutación no se ejecuta realmente (dry-run), se clasifica como `SIMULATED` sin alimentar falsos aprendizajes ni contar como mejora. Si falla de forma real (2 fallos consecutivos), `Foresee` la excluye automáticamente de futuras iteraciones.
- **Contexto donde aplica:** Triage, remediación y optimización autónoma dirigida por metas.
- **Evidencia:** 76/76 tests unitarios aprobados (`test_hermes_cognitive.py` 4/4 OK) y validación en vivo contra red real reportando veredicto `SIMULATED` honesto.
- **Límites conocidos:** La evaluación de re-planificación depende de métricas de red reproducibles.

---

## [2026-11-14] SUC-006: Persistencia Atómica Thread-Safe y Despertar Instantáneo con `threading.Event`
- **Problema:** Los demonios y planificadores que usaban `time.sleep(interval)` tardaban hasta 60–600s en detenerse, y la escritura JSON directa `open(..., "w")` bajo hilos concurrentes (`ThreadingHTTPServer`, `HermesMemory`, `LicenseManager`, `telemetry.py`) exponía corrupción de estado.
- **Solución:** Uso sistemático de `self._stop_event.wait(interval)` + `self._stop_event.set()` en `stop()`, `threading.RLock()` en singletons y accesos compartidos, y escritura atómica con `tempfile.mkstemp(..., dir=parent)` + `os.replace()`.
- **Contexto donde aplica:** `netopt/auto_trigger.py`, `netopt/autonomous_scheduler.py`, `netopt/persistence.py`, `netopt/telemetry.py`, `netopt/licensing.py`, `cloud_server/proxy_server.py`, `hermes/self_improvement.py`, `hermes/executor.py`, `hermes/orchestrator.py`.
- **Evidencia:** Pruebas unitarias dedicadas de despertar inmediato (`timeout=1.0s`) y concurrencia multi-hilo en `tests/test_fastapi_app.py`, `tests/test_cloud_server.py` y `tests/test_hermes.py`.
- **Límites conocidos:** En sistemas de archivos sin atomicidad POSIX/NTFS entre volúmenes distintos, el archivo temporal debe crearse siempre en el mismo directorio destino (`dir=parent`).

---

## [2026-11-14] SUC-007: Defensa en Profundidad en Fronteras de Entrada y Criptografía Ed25519 Real
- **Problema:** Superficies expuestas a CWE-22 (traversal de snapshots), CWE-78 (nombres de interfaz en HAL), inyección de flags (`-t` en PMTU), bypass SSRF por subcadena (`"localhost" in url`) o esquemas `file://` en `urllib`, y firma simétrica débil en `DeviceDID`.
- **Solución:** Validadores dedicados (`_validate_probe_target`, `_validate_iface_name`, `_is_local_llm_url`, `_validate_http_url`), `os.path.realpath()` para snapshots, `subprocess.list2cmdline()` + `shutil.which()` en elevación, y migración a `Ed25519PrivateKey`/`Ed25519PublicKey` (`cryptography`).
- **Contexto donde aplica:** `netopt/diagnostics.py`, `netopt/rollback.py`, `netopt/hal.py`, `netopt/llm_gateway.py`, `netopt/adapters.py`, `netopt/telemetry.py`, `netopt/licensing.py`, `netopt/elevation.py`, `netopt/micro_internet.py`.
- **Evidencia:** Suites `tests/test_fastapi_app.py` (32/32 OK), `tests/test_cloud_server.py` (11/11 OK) y `tests/test_micro_internet.py` (7/7 OK).
- **Límites conocidos:** Las reglas de validación deben mantenerse sincronizadas cuando se incorporen nuevos endpoints o adaptadores de red.


