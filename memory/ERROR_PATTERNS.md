# Patrones de Errores y Lecciones Aprendidas (`ERROR_PATTERNS.md`)
*Registro persistente de errores analizados, sus causas raíz comprobadas y procedimientos de prevención.*

---

## [2026-11-05] ERR-001: Fallo de escape de comillas en comandos inline de PowerShell
- **Síntoma:** Comandos complejos de PowerShell ejecutados vía `run_command` fallaban con errores de sintaxis (`ParserError`, comillas anidadas no reconocidas).
- **Causa raíz demostrada:** El shell por defecto en Windows es PowerShell, el cual interpola de forma impredecible comillas dobles, simples y signos `$` en cadenas inline de una sola línea.
- **Corrección aplicada:** Adoptar la directiva global de escribir y ejecutar scripts independientes de Python (`python -c "..."` o archivos `.py`) en lugar de scripts inline de PowerShell con tuberías complejas.
- **Evidencia de verificación:** Ejecución sin errores de suites de diagnóstico y scripts de backend.
- **Prevención para futuras tareas:** Siempre preferir scripts de Python para lógica de automatización o consultas al sistema.
- **Estado:** Verificado (C5).

---

## [2026-11-06] ERR-002: BBR2 Loopback Hang en Windows 11 24H2
- **Síntoma:** Al habilitar el proveedor de congestión TCP `bbr2` globalmente en Windows 11 24H2, las aplicaciones locales dependientes de loopback (`127.0.0.1`, proxies locales, WebSockets de Steam/Sunshine/Docker) se colgaban o sufrían timeouts de 21 segundos.
- **Causa raíz demostrada:** Comportamiento documentado en el kernel de Windows 11 24H2 donde el Large Receive Offload en el adaptador de loopback genera bloqueo de socket cuando el algoritmo de congestión es BBR2.
- **Corrección aplicada:** Desactivar explícitamente el MTU grande en loopback junto con BBR2 mediante `netsh int ipv4 set global loopbacklargemtu=disable` y `netsh int ipv6 set global loopbacklargemtu=disable`.
- **Evidencia de verificación:** Pruebas de conectividad local a localhost en daemon OmniNet y suite de sockets.
- **Prevención para futuras tareas:** Todo script u optimizador que asigne `CongestionProvider=bbr2` debe ejecutar el apagado de loopbacklargemtu preventivamente.
- **Estado:** Verificado (C5).

---

## [2026-11-07] ERR-003: Aserción de cadena en comando de poda de rutas de prueba
- **Síntoma:** `test_netopt_mock.py` fallaba con `AssertionError: '0.0.0.0/0' not found in 'e'`.
- **Causa raíz demostrada:** Indexación por corchetes en un objeto comando que devolvía el primer caracter del string en lugar de evaluar el texto completo de la propiedad `.command`.
- **Corrección aplicada:** Corrección de la aserción a `self.assertIn("0.0.0.0/0", prune_actions[0].command)`.
- **Evidencia de verificación:** `python -m unittest discover -s tests -v` pasando 53/53 tests.
- **Prevención para futuras tareas:** Comprobar siempre los tipos de datos de los objetos de acción (`OptimAction.command` como string) antes de indexar.
- **Estado:** Verificado (C4).

---

## [2026-11-07] ERR-004: Expresión `uro_enabled or True` y constantes estáticas en diagnósticos (`diagnostics.py`)
- **Síntoma:** `check_udp_offload_uro_uso_status()` devolvía `"uro_enabled": uro_enabled or True` y `"uso_enabled": uso_enabled or True`, forzando siempre `True` aunque `netsh interface udp show global` reportara `disabled`. Asimismo, `run_full_diagnostics()` fijaba `active_interface=None` y `detected_pmtu=1500` de forma estática.
- **Causa raíz demostrada:** Patrón clásico de alucinación de telemetría (Sección 6 de `hallucination-control`: *"Variables que declaran éxito sin comprobarlo"* y *"Resultados constantes utilizados para simular diagnósticos"*).
- **Corrección aplicada:** Eliminación de `or True` en `check_udp_offload_uro_uso_status()`, lectura real del estado de `netsh`/`sysctl` en `check_l4s_ecn_status` (incluyendo `tcp_ecn=3` AccECN RFC 9330), `check_rss_packet_steering_status`, `check_tcp_fast_open_status`, `check_hystart_plusplus_status`, `check_tcp_prague_accecn_status`, resolución real de `active_interface` y `mtu` en `run_full_diagnostics()`, y ejecución efectiva de `uso=enabled` y `loopbacklargemtu=disable` en `optimize_gaming_and_l4s_qos()`.
- **Evidencia de verificación:** Test unitario específico `test_hallucination_control_telemetry_truthfulness` en `tests/test_netopt_mock.py` (54/54 tests).
- **Prevención para futuras tareas:** Prohibir operadores `or True` en diccionarios de retorno de diagnóstico y exigir tests con mocks negativos (`disabled`).
- **Estado:** Verificado.

---

## [2026-11-07] ERR-005: Subprocesos huérfanos (`Popen`), bypass de `dry_run` y datos de muestra en `ecosystem_subagents.py`
- **Síntoma:** `test_10_specialized_ecosystem_subagents` emitía `ResourceWarning: subprocess ... is still running` y ejecutaba comandos reales del sistema (`MpCmdRun.exe -Scan`, `reg add`) cuando `LLMGateway` invocaba sub-agentes con `execute=True`, ignorando `self.hal.dry_run`. Además, `run_antivirus_subagent` reportaba siempre `"ACTIVO"` aunque `RealTimeProtectionEnabled` fuera `False`, y `run_startup_boost_subagent` devolvía una lista fija de ejemplo sin distinguir si el SO fue consultado.
- **Causa raíz demostrada:** Invocación directa de `subprocess.Popen` / `subprocess.run` en lugar de verificar `not self.hal.dry_run` o delegar en `self.hal.run_cmd`, y mensajes de resumen estáticos (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Respeto estricto de `self.hal.dry_run` y `self.hal.run_cmd` en `run_antivirus_subagent`, `run_privacy_shield_subagent` y `run_os_repair_subagent`; reemplazo de `Popen` por `subprocess.run` con timeout; consulta de `AMServiceEnabled`/`IsTamperProtected` y resumen condicional real; lectura rápida de claves `Run` del registro con banderas `os_probed` e `is_sample_fallback`; y detección de bandas múltiples MLO Wi-Fi 7 (`mlo_active`) en `inspect_wifi_and_nic()`.
- **Evidencia de verificación:** `test_ecosystem_subagents_hallucination_control` en `tests/test_netopt_mock.py` (55/55 tests OK, cero `ResourceWarning`).
- **Prevención para futuras tareas:** Toda acción mutadora o escaneo pesado en sub-agentes debe comprobar `execute and not self.hal.dry_run` y nunca usar `subprocess.Popen` sin espera controlada.
- **Estado:** Verificado.

---

## [2026-11-07] ERR-006: Binario ficticio `builtin-cleanerml` en `device_maintenance.py` y estado `COMPLETED` tras rollback en `autonomous_scheduler.py`
- **Síntoma:** Cuando BleachBit CLI no estaba instalado y se llamaba a `run_bleachbit_deep_clean(execute=True)`, devolvía `"installed": True, "binary": "builtin-cleanerml", "status": "EXECUTED"`. En `AutonomousTaskScheduler._execute_task()`, cuando `optimizer.execute_plan()` fallaba la compuerta de salud y revertía el cambio (`ok=False`), la tarea seguía marcándose al final como `task.status = "COMPLETED"`, y la categoría `L4S_ECN_TUNING` no capturaba snapshot previo.
- **Causa raíz demostrada:** Declaración de éxito e instalación ficticia sin comprobar el resultado real de la operación (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Retorno honesto `"installed": False, "binary": None, "status": "FALLBACK_NATIVE_CLEANER"` en `run_bleachbit_deep_clean()` cuando el binario externo no existe; eliminación de `subprocess.Popen` en `run_bleachbit_deep_clean()` y `update_system_and_drivers()`; asignación de `task.status = "REVERTED"` cuando `execute_plan()` revierte; y captura obligatoria de snapshot Zero NetLoss antes de `L4S_ECN_TUNING`.
- **Evidencia de verificación:** `test_device_maintenance_and_scheduler_hallucination_control` en `tests/test_netopt_mock.py` (56/56 tests OK).
- **Prevención para futuras tareas:** Verificar siempre la tupla `(ok, logs)` de retorno antes de asignar el estado final de una tarea programada.
- **Estado:** Verificado.

---

## [2026-11-07] ERR-007: Falso `RESOLVED` con 100% de pérdida en `auto_trigger.py` y ausencia de `L1_INTERFACE_DOWN` / purga ARP en `repair.py`
- **Síntoma:** En `AutoSentinel.check_health_and_auto_heal()`, cuando una caída total de red devolvía `after_metrics.avg_ms = 0.0` (0 paquetes recibidos) frente a `metrics_before["latency_ms"] = 999.0`, la condición `after_metrics.avg_ms < metrics_before["latency_ms"]` evaluaba a `True` y marcaba el incidente como `"RESOLVED"` pese a seguir con 100% de pérdida; además nunca podía devolver `"FAILED"`. En `repair.py`, `L1_INTERFACE_DOWN` estaba documentado en el docstring pero no implementado, y `L2_DHCP_OR_GATEWAY_FAILURE` omitía vaciar la caché ARP prometida en el comentario.
- **Causa raíz demostrada:** Comparación numérica ingenua sobre `avg_ms = 0.0` cuando `packets_received == 0` y omisión de rama `FAILED` (Sección 6 de `hallucination-control`: *"Variables que declaran éxito sin comprobarlo"* y *"Documentación que afirma capacidades inexistentes"*).
- **Corrección aplicada:** Exigencia de `packets_received > 0` y conectividad real (`internet_reachable and dns_resolving`) antes de declarar `RESOLVED`/`MITIGATED`, asignando `"FAILED"` si el corte persiste; respeto de `self.hal.dry_run` en `AutoSentinel`; e implementación real de `L1_INTERFACE_DOWN` y purga de tabla ARP (`netsh interface ip delete arpcache` / `ip neigh flush all`) en `repair.py`.
- **Evidencia de verificación:** `test_repair_and_autosentinel_hallucination_control` en `tests/test_netopt_mock.py` (57/57 tests OK).
- **Prevención para futuras tareas:** Nunca comparar métricas de latencia post-acción sin validar primero `packets_received > 0` y `internet_reachable == True`.
- **Estado:** Verificado.

---

## [2026-11-07] ERR-008: Validación superficial de firmas (`len == 64`) en `micro_internet.py` y reporte de pruebas omitidas como aprobadas en `hermes/self_improvement.py`
- **Síntoma:** `DeviceDID.verify_message()` en `netopt/micro_internet.py` solo comprobaba `len(signature) == 64` y devolvía `True` sin verificar el HMAC del mensaje; `GatewayFederation.elect_active_gateway()` seleccionaba gateways federados aunque tuvieran `health != "HEALTHY"`; y `HermesSelfImprovementEngine.run_evolution_cycle(run_tests=False)` imprimía `"Tests 100% aprobados: True"` en su resumen además de mantener `tests_ok = True` si `subprocess.run` lanzaba una excepción.
- **Causa raíz demostrada:** Ejemplos directos de la Sección 6 de `hallucination-control`: *"Funciones que parecen implementadas, pero no realizan ninguna operación real"* (`verify_message`) y *"Pruebas omitidas que aparecen como aprobadas"* (`run_evolution_cycle`).
- **Corrección aplicada:** Verificación criptográfica real `hmac.compare_digest` en `DeviceDID.verify_message()`, validación de rutas `PATH_CHALLENGE`/`PATH_RESPONSE` (`draft-ietf-quic-multipath`) en `MultipathIdentityTransport`, filtrado de `health == "HEALTHY"` en `GatewayFederation.elect_active_gateway()`, y adición de `tests_executed` más manejo de excepciones con `tests_ok = False` y texto explícito `"Tests omitidos (run_tests=False)"` en `hermes/self_improvement.py`.
- **Evidencia de verificación:** `tests/test_micro_internet.py` y `tests/test_hermes.py` (57/57 tests OK).
- **Prevención para futuras tareas:** Toda función de verificación criptográfica debe incluir aserciones negativas (firma alterada y mensaje alterado) en su test unitario, y nunca reportar pruebas aprobadas cuando `run_tests=False`.
- **Estado:** Verificado.

---

## [2026-11-07] ERR-009: Respuestas incondicionales de éxito en `_local_cognitive_fallback` (`llm_gateway.py`), versión desincronizada en `mcp_server.py` y descuento prematuro de cuota en `proxy_server.py`
- **Síntoma:** En `netopt/llm_gateway.py`, `_local_cognitive_fallback()` respondía siempre `"🩺 Tu Internet está funcionando Muy Bien"` para `network_diagnose` incluso cuando `overall_health == "down"` o `internet_reachable == False`; respondía `"✅ ¡Listo! Tu Internet fue Acelerado"` para `network_execute_optimization` aunque `success == False` o `status == "REVERTED"`; y afirmaba `"se activó SDIO en segundo plano"` en `device_full_maintenance` aunque `sdio_driver_engine.installed == False`. Además, `mcp_server.py` reportaba versión `"2.0.0"` en lugar de `__version__` (`"2.9.6"`), y `cloud_server/proxy_server.py` descontaba cuota mensual antes de verificar `DEEPSEEK_API_KEY`.
- **Causa raíz demostrada:** Plantillas de texto estáticas que ignoraban los campos booleanos y estados reales de `tool_output` (Sección 6 de `hallucination-control`: *"Mensajes de éxito que no dependen del resultado real"*).
- **Corrección aplicada:** Ramificación condicional en `_local_cognitive_fallback()` según `overall_health`/`internet_reachable`, `success`/`status != "REVERTED"`, `sdio_info.get("installed")` y `doh_enabled`; eliminación de snapshot/verificación duplicada en `LLMGateway.chat()`; sincronización de `OMNINET_VERSION` y campos `active_interface`/`detected_pmtu` en `mcp_server.py`; cierre `finally: sock.close()` en `check_doq_status()`/`check_doh3_rfc9297_status()` y validación `if not DEEPSEEK_API_KEY:` previa al cobro de cuota en `cloud_server/proxy_server.py`.
- **Evidencia de verificación:** `test_llm_gateway_and_mcp_hallucination_control` en `tests/test_netopt_mock.py` (58/58 tests OK).
- **Prevención para futuras tareas:** Todo generador de respuestas o fallback conversacional debe inspeccionar explícitamente las banderas de éxito/fallo/reversión de la herramienta ejecutada antes de emitir mensajes afirmativos al usuario.
- **Estado:** Verificado.

---

## [2026-11-07] ERR-010: Promedio distorsionado con `0.0ms` ante 100% de pérdida en `rollback.py`, falso `installed=True` por subcadena `"installed"` en `software_catalog.py` y falta de validación MTU en `hal.py`
- **Síntoma:** En `RollbackManager.capture_baseline()` y `verify_post_action_health()` (`netopt/rollback.py`), se promediaba `(m1.avg_ms + m2.avg_ms) / 2.0` sin comprobar `packets_received > 0`, provocando que un destino caído (`avg_ms == 0.0`) redujera artificialmente la latencia calculada a la mitad. En `install_software_package()` (`netopt/software_catalog.py`), la condición `if res.returncode == 0 or ... or "installed" in res.stdout.lower():` hacía inalcanzable la rama `elif "already installed"` y marcaba falsamente `"installed": True` cuando `winget` fallaba con `"No installed package found"` o `"could not be installed"`. En `netopt/hal.py`, `DarwinHAL.get_dns_servers()` devolvía `["1.1.1.1", "8.8.8.8"]` inventados si la lista estaba vacía y `set_interface_mtu()` carecía de validación de rango (576-9000) y sanitización.
- **Causa raíz demostrada:** Coincidencia laxa de subcadenas (`"installed"` en mensajes de error) y cálculo de media sobre muestras sin paquetes recibidos (`avg_ms == 0.0`), violando la Sección 6 de `hallucination-control`.
- **Corrección aplicada:** Filtrado `[m.avg_ms for m in (m1, m2) if m.packets_received > 0]` en `rollback.py` con fallo inmediato si no hay paquetes recibidos; evaluación prioritaria de `"already installed"` y restricción de éxito a `res.returncode == 0` o `"successfully installed"`/`"instalado correctamente"` en `software_catalog.py`; propagación de `dry_run` en `NetworkDaemon.check_and_heal_once()` (`persistence.py`); y validación de interfaz y rango MTU `576 <= mtu <= 9000` más eliminación de DNS inventados en `hal.py`.
- **Evidencia de verificación:** `test_rollback_persistence_software_and_hal_hallucination_control` en `tests/test_netopt_mock.py` (59/59 tests OK).
- **Prevención para futuras tareas:** Nunca buscar palabras genéricas como `"installed"` en `stdout` sin verificar `returncode == 0` o frases inequívocas, y nunca promediar latencias sin filtrar `packets_received > 0`.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-011: Banners UI incondicionales y snapshots sin orden cronológico en `main.py`, bypass de HTTP 403 en `licensing.py` y propagación de fallo en `hermes/harness.py`
- **Síntoma:** En `main.py`, `oneClickBoostInternet()` no leía la respuesta JSON de `/api/optimize` y mostraba `"¡Tu Internet fue acelerado con éxito!"` aunque el plan hubiera sido revertido (`status == "REVERTED"`); `oneClickCleanAndRepairPC()` afirmaba siempre haber usado SDIO; `/api/snapshots` listaba archivos sin ordenar por `getmtime`; y `/api/rollback` (al igual que `mcp_server.py`) devolvía `applied=True` incluso cuando el snapshot no existía (`ERROR: Snapshot ... not found`). En `netopt/licensing.py`, un rechazo explícito HTTP 403 del Cloud Proxy era capturado por `except Exception: pass` y saltaba a la validación local. En `hermes/harness.py` y `hermes/orchestrator.py`, `dispatch_tool()` devolvía `success=True` aunque `execute_python` fallara (`exit_code != 0`), y `synthesize_results([])` devolvía `all_succeeded=True` con 0 sesiones.
- **Causa raíz demostrada:** Ignorar el payload de respuesta en el frontend, capturar `HTTPError` 401/403 con un `except Exception: pass` genérico y no propagar el campo `success` de diccionarios internos en `dispatch_tool()` (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Verificación de `data.success && data.status !== 'REVERTED'` y `sdioInstalled` en `main.py`; ordenamiento cronológico por `os.path.getmtime` en `/api/snapshots`; inclusión de `"success": ok` y `"applied": execute and ok` en `/api/rollback` y `mcp_server.py`; manejo explícito de `urllib.error.HTTPError` (401/403) en `LicenseManager.activate_license()`; y propagación de `inner_ok` y `total > 0` en `hermes/harness.py` y `hermes/orchestrator.py`.
- **Evidencia de verificación:** `test_main_licensing_and_mcp_rollback_hallucination_control` en `tests/test_netopt_mock.py` y aserciones adicionales en `tests/test_hermes.py` (60/60 tests OK).
- **Prevención para futuras tareas:** Nunca usar `except Exception: pass` sobre llamadas HTTP de autorización sin distinguir errores de red (5xx/timeout) de rechazos explícitos de autorización (401/403).
- **Estado:** Verificado.

---

## [2026-11-08] ERR-012: Ausencia de `import time` en `cli.py`, detección ciega de `"tail loss"` en `check_tcp_rack_tlp_prr_status()` y MAC de gateway fabricada (`74:24:9f:36:d4:77`) en `check_gateway_mac_pinning_status()`
- **Síntoma:** En `netopt/cli.py`, el subcomando `daemon` invocaba `time.strftime('%X')` sin haber importado `time` (`NameError`) y fijaba `dry_run=True` incluso con `--auto-heal`. En `netopt/diagnostics.py`, `check_tcp_rack_tlp_prr_status()` asignaba `tlp_enabled = "cola" in stdout_low or "tail loss" in stdout_low` sin verificar si la línea indicaba `"disabled"`/`"deshabilitado"`, `check_quic_datagram_rfc9221_status()` cerraba el socket dentro del `try` sin `finally`, y `check_gateway_mac_pinning_status()` devolvía la MAC inventada `"74:24:9f:36:d4:77"` cuando `arp -a` no encontraba la puerta de enlace.
- **Causa raíz demostrada:** Subcadenas evaluadas sin contexto de línea (`enabled` vs `disabled`) y valores constantes de relleno (`"74:24:9f:36:d4:77"`) contrarios a la Sección 6 de `hallucination-control`.
- **Corrección aplicada:** Inclusión de `import time`, campos `active_interface`/`detected_pmtu`, orden cronológico de snapshots y `dry_run=not args.auto_heal` en `netopt/cli.py`; parseo línea por línea de `enabled`/`disabled` en `check_tcp_rack_tlp_prr_status()`, bloque `try ... finally: s.close()` en `check_quic_datagram_rfc9221_status()`, y retorno honesto `"gateway_mac": current_mac or "unknown"` con `"mac_resolved": bool(current_mac)` en `check_gateway_mac_pinning_status()`.
- **Evidencia de verificación:** `test_cli_and_rack_tlp_gateway_mac_hallucination_control` en `tests/test_netopt_mock.py` (61/61 tests OK).
- **Prevención para futuras tareas:** Nunca devolver direcciones MAC, IPs o identificadores de hardware de ejemplo cuando una consulta al sistema operativo no arroje resultados; usar `"unknown"` o `None` junto a una bandera booleana de resolución.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-013: `TypeError` latente en `vars(diag.active_interface)` y parámetros ignorados en `mcp_server.py` frente a `tools_manifest.json`
- **Síntoma:** En `mcp_server.py`, `handle_tool_call("network_diagnose", ...)` ejecutaba `vars(diag.active_interface) if diag.active_interface else None`, lo cual lanzaba `TypeError: vars() argument must have __dict__ attribute` cuando `diag.active_interface` era un string (`"Ethernet"`). Además, ignoraba `include_dns_benchmarks` en `network_diagnose`, `domains` en `network_benchmark_dns`, `target_profile` en `network_generate_optimization_plan` y `action` (`"status"` vs `"sample_once"`) en `network_persistent_monitor`, y la documentación (`AGENTS.md`, `PROJECT_STATE.md`, `mcp_server.py`) indicaba 12 herramientas MCP en lugar de las 15 definidas en `config/tools_manifest.json`.
- **Causa raíz demostrada:** Desfase entre el esquema declarativo (`config/tools_manifest.json`) y la implementación real en `mcp_server.py` (Sección 6 de `hallucination-control`: *"Documentación que afirma capacidades inexistentes"* y parámetros declarados pero no conectados).
- **Corrección aplicada:** Serialización segura de `diag.active_interface` cuando es `str`, soporte real de `include_dns_benchmarks: bool = True` en `run_full_diagnostics()` y `domains: Optional[List[str]] = None` en `benchmark_all_resolvers()` (`netopt/diagnostics.py`), propagación de `target_profile` en `NetworkOptimizer.generate_plan()` (`netopt/optimizer.py`), manejo de `action == "status"` en `network_persistent_monitor` (`mcp_server.py`), y sincronización documental de las 15 herramientas MCP en `AGENTS.md` y `PROJECT_STATE.md`.
- **Evidencia de verificación:** `test_mcp_manifest_parameter_parity_hallucination_control` en `tests/test_netopt_mock.py` (62/62 tests OK).
- **Prevención para futuras tareas:** Todo parámetro expuesto en `config/tools_manifest.json` debe estar conectado y verificado mediante test unitario en `handle_tool_call()`.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-014: Constante estática `loopback_latency_us = 120` y omisión de verificación `loopbacklargemtu` en `check_windows_24h2_loopback_bbr_safety()`, más fallo de `isdigit()` con sufijo `ms` en `check_tcp_initial_rto_syn_status()`
- **Síntoma:** En `netopt/diagnostics.py`, `check_windows_24h2_loopback_bbr_safety()` devolvía siempre `"loopback_latency_us": 120` y `"zero_netloss_safe": True` sin medir el socket loopback ni comprobar si `bbr2` coexistía con `Loopback Large Mtu : enabled` (`ERR-002`). En `check_tcp_initial_rto_syn_status()`, `val.isdigit()` fallaba cuando `netsh int tcp show global` incluía unidades (`"2000 ms"`), y `discover_path_mtu()` no indicaba si el sondeo ICMP DF fue verificado (`probe_verified`) o asumido por bloqueo ICMP.
- **Causa raíz demostrada:** Uso de constantes fijas (`120`) para simular mediciones y `str.isdigit()` sobre salidas de consola con unidades adjuntas (Sección 6 de `hallucination-control`: *"Resultados constantes utilizados para simular diagnósticos"*).
- **Corrección aplicada:** Sondeo real de latencia UDP loopback en `127.0.0.1` en microsegundos con cierre `finally: s_loop.close()` y evaluación de `loopback_large_mtu_disabled` cuando `active_provider == "bbr2"`; extracción numérica con `re.search(r"(\d+)", val)` y evaluación condicional de `handshake_stall_mitigated` en `check_tcp_initial_rto_syn_status()`; preservación de rutas únicas en Linux en `check_duplicate_default_gateways_status()`; y bandera `probe_verified` en `discover_path_mtu()`.
- **Evidencia de verificación:** `test_loopback_bbr_rto_and_pmtu_hallucination_control` en `tests/test_netopt_mock.py` (63/63 tests OK).
- **Prevención para futuras tareas:** Nunca usar `str.isdigit()` al parsear métricas de CLI del sistema operativo que puedan incluir sufijos de unidad (`ms`, `%`, `B`), y medir siempre tiempos reales de socket en lugar de retornar constantes.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-015: Resumen estático de éxito en `run_drivers_subagent()`, `run_os_repair_subagent()` y `run_backup_subagent()` (`ecosystem_subagents.py`), y ausencia de guarda `dry_run` en `run_elevated_admin_repairs()` (`device_maintenance.py`)
- **Síntoma:** En `netopt/ecosystem_subagents.py`, `run_drivers_subagent()` afirmaba `"Verificación de hardware y periféricos completada; adaptadores de red y gráficos al día"` aunque SDIO no estuviera instalado (`status == "UNAVAILABLE"`); `run_os_repair_subagent()` devolvía `"sin corrupción de paquetes del sistema"` incluso cuando `integrity_status == "REQUIERE_REPARACION"`; y `run_backup_subagent()` no comprobaba `not self.hal.dry_run` ni la existencia del archivo `.zip` antes de declarar `'creado con éxito'`. Además, en `netopt/device_maintenance.py`, `run_elevated_admin_repairs()` podía invocar `Start-Process ... -Verb RunAs` incluso con `self.hal.dry_run == True`, y `CCLEANER_JUNK_CACHES`/`CCLEANER_REGISTRY` reportaban `status="SUCCESS"` en modo `execute=False`.
- **Causa raíz demostrada:** Mensajes de resumen estáticos desacoplados del estado real de retorno (`installed`, `integrity_status`, `archive_created`, `dry_run`) contrarios a la Sección 6 de `hallucination-control`.
- **Corrección aplicada:** Inclusión de `installed` y resumen condicional en `run_drivers_subagent()`; ramificación de `summary` según `integrity_status == "REQUIERE_REPARACION"` y `health_checked` en `run_os_repair_subagent()`; verificación de `archive_created = os.path.exists(backup_file)` y `not self.hal.dry_run` en `run_backup_subagent()`; y guarda `if self.hal.dry_run:` en `run_elevated_admin_repairs()` más estado `"DRY_RUN"` cuando `execute=False` en `run_full_device_maintenance()`.
- **Evidencia de verificación:** `test_drivers_os_repair_backup_and_admin_dry_run_hallucination_control` en `tests/test_netopt_mock.py` (64/64 tests OK).
- **Prevención para futuras tareas:** Todo campo `summary` o `status` en sub-agentes debe derivarse directamente de las banderas verificadas (`installed`, `integrity_status`, `archive_created`, `should_apply`).
- **Estado:** Verificado.

---

## [2026-11-08] ERR-016: Bypass de `self.hal.dry_run` en `_clean_temp_files_safe()`, `_clean_windows_registry_orphans()`, `run_sdio_driver_update()` y `run_full_device_maintenance()` (`device_maintenance.py`)
- **Síntoma:** En `netopt/device_maintenance.py`, cuando `DeviceMaintenanceEngine` se instanciaba con un HAL en modo `dry_run=True` (por ejemplo, desde `EcosystemOrchestrator` o pruebas unitarias) pero se llamaba con `execute=True` (como hace `LLMGateway` al invocar `run_cleaner_subagent(execute=True)`), `_clean_temp_files_safe(execute=True)` llamaba a `os.remove()` sobre archivos reales del sistema, `_clean_windows_registry_orphans(execute=True)` abría el registro con `KEY_SET_VALUE` y llamaba a `winreg.DeleteValue()`, y `run_sdio_driver_update(execute=True)` podía lanzar el binario SDIO sin respetar `self.hal.dry_run`.
- **Causa raíz demostrada:** Evaluar únicamente el argumento `if execute:` en lugar de la compuerta combinada `should_apply = bool(execute and not self.hal.dry_run)` (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Aplicación uniforme de `if not execute or self.hal.dry_run:` / `should_apply = bool(execute and not self.hal.dry_run)` en `_clean_temp_files_safe()`, `_clean_windows_registry_orphans()`, `inspect_and_remediate_system_logs()`, `run_sdio_driver_update()` y `run_full_device_maintenance()`.
- **Evidencia de verificación:** `test_device_maintenance_strict_dry_run_guard_hallucination_control` en `tests/test_netopt_mock.py` (65/65 tests OK).
- **Prevención para futuras tareas:** Ningún método que elimine archivos (`os.remove`), modifique el registro (`winreg.DeleteValue`) o ejecute binarios externos puede actuar basándose solo en `execute=True` sin comprobar simultáneamente `not self.hal.dry_run`.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-017: `AttributeError` en `plan.pre_snapshot_id` y omisión de anomalías ARP en `llm_gateway.py`, más falso positivo `[] is not None` en `supabase_client.py`
- **Síntoma:** En `netopt/llm_gateway.py`, la intención conversacional `"aplicar"` accedía a `plan.pre_snapshot_id`, atributo inexistente en `OrchestrationPlan` (cuyo campo real es `rollback_snapshot_id`), lanzando `AttributeError`. Además, `_local_cognitive_fallback()` buscaba `rtt_ms` en lugar de `baseline_rtt_ms` para `network_discover_and_schedule_tasks`, ignoraba la clave real `"sdio_drivers"` en `device_full_maintenance`, declaraba `"100% segura"` en `network_lan_radar` cuando `new_devices_found` estaba vacío aunque existieran anomalías ARP (`anomalies` / `gateway_impersonation_detected`), y afirmaba éxito en `device_admin_repair` aunque `admin_repairs_applied` fuera `False`. En `cloud_server/supabase_client.py`, `update_license_devices()` y `upsert_license_in_supabase()` evaluaban `return res is not None`, devolviendo `True` cuando PostgREST respondía `[]` (0 filas actualizadas), y `upsert_license_in_supabase()` omitía la cabecera `Prefer: resolution=merge-duplicates`.
- **Causa raíz demostrada:** Desajuste de nombres de atributos/claves entre modelos y gateway (`pre_snapshot_id` vs `rollback_snapshot_id`, `rtt_ms` vs `baseline_rtt_ms`) y evaluación `res is not None` sobre listas vacías de PostgREST (`[]`), violando la Sección 6 de `hallucination-control`.
- **Corrección aplicada:** Uso de `plan.rollback_snapshot_id`, `baseline_rtt_ms`, `sdio_drivers`, verificación de `admin_repairs_applied` y chequeo de `anomalies`/`gateway_impersonation_detected` en `netopt/llm_gateway.py`; y adición de `prefer="resolution=merge-duplicates,return=representation"` más validación `isinstance(res, list) and len(res) > 0` en `cloud_server/supabase_client.py`.
- **Evidencia de verificación:** `test_llm_gateway_apply_snapshot_and_supabase_postgrest_hallucination_control` en `tests/test_netopt_mock.py` (66/66 tests OK).
- **Prevención para futuras tareas:** Verificar siempre en `models.py` el nombre exacto de los campos de dataclass antes de referenciarlos en diccionarios de salida, y validar `len(res) > 0` en respuestas PostgREST con `return=representation`.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-018: Estado fijo en `optimize_gaming_and_l4s_qos()`, falso positivo multi-red en `audit_lan_radar_devices()` y resúmenes estáticos en DoQ/DoH3 (`optimizer.py`, `diagnostics.py`)
- **Síntoma:** En `netopt/optimizer.py`, `optimize_gaming_and_l4s_qos(execute=True)` pasaba `execute` sin verificar `self.hal.dry_run`, ignoraba el retorno `AgentActionLog` de `self.hal.run_cmd()`, y reportaba `"executed": True` y `"gaming_mode_active": True` incluso cuando `dry_run=True` o cuando todos los comandos fallaban (`success=False`). En `netopt/diagnostics.py`, `audit_lan_radar_devices()` comparaba la MAC del gateway contra `trusted_gateway.json` sin verificar si `gateway_ip` correspondía a la misma red, disparando falsas alarmas de ARP Spoofing al cambiar de red/subred (ej. `192.168.1.1` a `10.0.0.1`), y `check_doq_status()` / `check_doh3_rfc9297_status()` reportaban `"activo"` en `summary` incluso cuando `outbound_udp_permitted` era `False`.
- **Causa raíz demostrada:** Ignorar el resultado de ejecución de los comandos `run_cmd` y omitir la asociación por `gateway_ip` en el archivo de estado `trusted_gateway.json` (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** En `optimize_gaming_and_l4s_qos()`, uso de `should_apply = bool(execute and not (getattr(self.hal, "dry_run", False) is True))`, conteo de `commands_failed` sobre `cmd_logs` y desactivación de `gaming_mode_active` si todos los comandos fallan; en `audit_lan_radar_devices()`, diccionario `known_gateways` indexado por `gateway_ip`; en `check_doq_status()` y `check_doh3_rfc9297_status()`, `summary` condicional según `outbound_udp_permitted`; e incorporación de `RFC 9768 (Accurate ECN)` en `check_tcp_prague_accecn_status()`.
- **Evidencia de verificación:** `test_gaming_l4s_optimizer_and_per_gateway_arp_radar_hallucination_control` en `tests/test_netopt_mock.py` (67/67 tests OK).
- **Prevención para futuras tareas:** Indexar siempre las líneas base de seguridad de capa 2 (MAC de gateway) por IP de subred/gateway para soportar equipos portátiles multi-red sin falsos positivos.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-019: Calificación `A+` falsa cuando el 100% de sondeos en ráfaga expiran en `check_bufferbloat()`, aceptación de `SERVFAIL`/`REFUSED` en `query_dns_resolver_latency()` y mensajes fijos en `llm_gateway.py` (`diagnostics.py`, `llm_gateway.py`)
- **Síntoma:** En `netopt/diagnostics.py`, cuando todos los `tcp_ping` bajo carga en `check_bufferbloat()` expiraban (`burst_samples == []`), `active_rtt` hacía fallback a `idle_rtt`, resultando en `delta = 0.0` y otorgando falsamente grado `"A+"` ante un colapso del 100% bajo ráfaga. Además, `query_dns_resolver_latency()` consideraba exitosa cualquier respuesta UDP de `>= 12` bytes sin verificar coincidencia de Transaction ID ni `RCODE` (`SERVFAIL=2`, `REFUSED=5`), e `inspect_wifi_and_nic()` no invalidaba `connected` cuando `State` era `disconnected`. En `netopt/llm_gateway.py`, `_local_cognitive_fallback()` afirmaba fluidez en `network_traceroute_and_bufferbloat` aunque el grado fuera `D`/`F`, seguridad en `network_audit_arp_lan` aunque hubiera `anomalies`, y rapidez (`0.0 ms`) en `network_live_probe` cuando `packet_loss_pct == 100.0`.
- **Causa raíz demostrada:** Fallback de promedio vacío al valor en reposo (`else idle_rtt`) y ausencia de inspección de cabeceras DNS RFC 1035 (`TXID`/`RCODE`) (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Retorno de `("F", round(idle_rtt, 2), 999.0)` si `not burst_samples` en `check_bufferbloat()`; validación de `data[:2] == query[:2]` y `rcode not in (1, 2, 4, 5)` en `query_dns_resolver_latency()`; chequeo de `State: disconnected` en `inspect_wifi_and_nic()`; y ramificación por estado real (`grade in ("D", "F")`, `anomalies`, `packet_loss_pct >= 100.0`, `gaming_mode_active`) en `netopt/llm_gateway.py`.
- **Evidencia de verificación:** `test_dns_rcode_bufferbloat_burst_loss_and_fallback_hallucination_control` en `tests/test_netopt_mock.py` (68/68 tests OK).
- **Prevención para futuras tareas:** Nunca usar la métrica en reposo (`idle_rtt`) como valor por defecto cuando una lista de muestras bajo carga queda vacía por timeouts.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-020: Contaminación de `baseline_jitter_ms` en cortes del 100% (`avg_rtt=0.0`), aceptación de DNS con `success_rate_percent=0` y marcado `COMPLETED` sin verificar fallos en `AutonomousTaskScheduler` (`autonomous_scheduler.py`)
- **Síntoma:** En `netopt/autonomous_scheduler.py`, `_evolve_telemetry()` actualizaba `baseline_jitter_ms` con `jitter=0.0` incluso cuando `avg_rtt == 0.0` (100% pérdida de paquetes) y sobrescribía `best_dns_ip` aunque `best_dns.success_rate_percent == 0.0`. Además, `_execute_task()` marcaba tareas `PMTU_TUNE`, `L4S_ECN_TUNING`, `SOCKET_HYGIENE` y `TRIAGE_REPAIR` como `COMPLETED` y grababa `last_applied_mtu` / `last_l4s_tune_attempt = "applied"` sin comprobar si los comandos habían fallado (`success=False` o `gaming_mode_active=False`) o si `self.hal.dry_run` era `True`.
- **Causa raíz demostrada:** Falta de compuerta `avg_rtt > 0` antes de actualizar el EWMA de jitter, ausencia de filtro `success_rate_percent >= 90.0` para DNS candidato, e ignorar banderas de éxito en `_execute_task()` (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Exigencia de `avg_rtt > 0 and jitter >= 0` y `success_rate_percent > 0.0` en `_evolve_telemetry()`; verificación de `task_failed` e `is_dry_hal` en `_execute_task()` antes de persistir `last_applied_mtu`, `last_applied_dns` o `last_l4s_tune_attempt`; y paso de `diag` a `repair_engine.diagnose_and_triage(diag=diag)` en `netopt/repair.py` para evitar doble barrido de red.
- **Evidencia de verificación:** `test_scheduler_telemetry_jitter_dns_and_task_failure_hallucination_control` en `tests/test_netopt_mock.py` (69/69 tests OK).
- **Prevención para futuras tareas:** Toda actualización de estado evolutivo (`evolution_state.json`) debe estar condicionada a que la acción haya tenido éxito real (`not task_failed and not is_dry_hal`).
- **Estado:** Verificado.

---

## [2026-11-08] ERR-021: Divergencia de diagnóstico en `AutoSentinel.check_health_and_auto_heal()` por re-ejecución sin `diag=diag` e `IndexError` en `MultipathIdentityTransport.route_payload()` con `transports=[]` (`auto_trigger.py`, `micro_internet.py`)
- **Síntoma:** En `netopt/auto_trigger.py`, `check_health_and_auto_heal()` capturaba `diag = run_full_diagnostics()` para evaluar el incidente, pero luego invocaba `self.repair_engine.diagnose_and_triage()` y `self.optimizer.generate_plan()` sin pasar `diag=diag`, provocando dos barridos adicionales de red en vivo cuyo estado podía diferir del reporte que disparó la alerta (y omitía el prefijo `[SIMULACIÓN DRY-RUN]` en `human_summary` cuando `dry_run=True`). En `netopt/micro_internet.py`, `MultipathIdentityTransport.route_payload()` evaluaba `peer.get("transports", ["UDP"])[0]`, lanzando `IndexError: list index out of range` cuando un nodo se registraba con `transports=[]`.
- **Causa raíz demostrada:** Omitir la propagación del `DiagnosticsReport` activo hacia `diagnose_and_triage(diag=diag)` / `generate_plan(diag=diag)` y usar `dict.get(key, default)[0]` cuando el valor almacenado puede ser una lista vacía `[]` (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Paso explícito de `diag=diag` a `self.repair_engine.diagnose_and_triage(diag=diag)` y `self.optimizer.generate_plan(diag=diag)` más etiqueta `[SIMULACIÓN DRY-RUN]` en `netopt/auto_trigger.py`; y uso de `(peer.get("transports") or ["UDP"])[0]` en `netopt/micro_internet.py`.
- **Evidencia de verificación:** `test_autosentinel_diag_reuse_and_micro_internet_empty_transports_hallucination_control` en `tests/test_netopt_mock.py` (70/70 tests OK).
- **Prevención para futuras tareas:** Siempre usar `(d.get("lista") or [ fallback ])[0]` al indexar listas provenientes de cachés JSON o registros externos.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-022: Rotación no atómica `os.rename`, omisión de `diag=diag` / escalado SLA y falta de snapshot Zero NetLoss en `NetworkDaemon.check_and_heal_once()` (`persistence.py`, `elevation.py`)
- **Síntoma:** En `netopt/persistence.py`, `log_telemetry()` usaba `os.rename(TELEMETRY_LOG, f"{TELEMETRY_LOG}.bak")` (que falla en Windows con `FileExistsError` cuando `.bak` ya existe); `check_and_heal_once()` invocaba `self.repair_engine.diagnose_and_triage()` sin `diag=diag`, no escalaba a remediación cuando `sla_violation` era `True` pero `overall_health == HEALTHY`, y ejecutaba `execute_triage_repair(..., execute=True)` sin capturar un snapshot previo en `RollbackManager`. En `netopt/elevation.py`, `_is_root_posix()` invocaba `os.geteuid()` directamente sin guard para entornos Windows.
- **Causa raíz demostrada:** Uso de `os.rename` en lugar de `os.replace` en Windows, falta de propagación de `diag=diag` y omisión de captura de snapshot en el demonio persistente (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Reemplazo por `os.replace` en `log_telemetry()`, propagación de `diag=diag`, escalado de `sla_violation` a `L7_HIGH_LOSS_OR_DEGRADED` y captura de snapshot `RollbackManager` antes de reparar con `do_exec=True` en `netopt/persistence.py`; guard `getattr(os, "geteuid", lambda: -1)() == 0` en `netopt/elevation.py`.
- **Evidencia de verificación:** `test_persistence_daemon_sla_snapshot_and_atomic_rotate_hallucination_control` en `tests/test_netopt_mock.py` (71/71 tests OK).
- **Prevención para futuras tareas:** Todo flujo de remediación que opere con `execute=True` debe capturar un snapshot previo con `RollbackManager` y usar `os.replace` para rotaciones de archivos en Windows.
- **Estado:** Verificado.

---

## [2026-11-08] ERR-023: Falsos positivos de subcadena corta (`ip`, `obs`) e informe falso `browser_opened=True` cuando `webbrowser.open()` devuelve `False` en `software_catalog.py`, más descuento prematuro de cuota IA ante fallo HTTP 500 en `proxy_server.py`
- **Síntoma:** En `netopt/software_catalog.py`, `find_matching_software()` evaluaba `kw in q` sin límites de palabra para términos cortos (`<= 3` caracteres como `"ip"` u `"obs"`), provocando que consultas como `"optimizar mi equipo"` u `"observación"` coincidieran falsamente con Proton VPN u OBS Studio; además, `install_software_package()` ignoraba el valor booleano de retorno de `webbrowser.open(url)`, reportando `success=True, browser_opened=True` incluso cuando `webbrowser.open()` devolvía `False`. En `cloud_server/proxy_server.py`, `/v1/license/activate` no validaba `expires_at`, y `/v1/chat` incrementaba `queries_count` y guardaba la base de datos antes de verificar que la petición upstream a DeepSeek respondiera exitosamente.
- **Causa raíz demostrada:** Búsqueda por subcadena sin `\b` en tokens cortos, omisión de verificación del booleano de retorno de `webbrowser.open()`, y mutación prematura de estado de cuota antes de completar la llamada externa (Sección 6 de `hallucination-control`).
- **Corrección aplicada:** Función `_term_in_query()` con `re.search(rf"\b{re.escape(t)}\b", query)` para términos `<= 3` caracteres y verificación explícita `opened = bool(webbrowser.open(url))` en `netopt/software_catalog.py`; chequeo de `expires_at` en `/v1/license/activate` y descuento de `queries_count` únicamente tras recibir respuesta válida de DeepSeek en `cloud_server/proxy_server.py`.
- **Evidencia de verificación:** `test_software_catalog_word_boundary_and_proxy_quota_hallucination_control` en `tests/test_netopt_mock.py` (72/72 tests OK).
- **Prevención para futuras tareas:** Nunca descontar cuotas ni persistir contadores de éxito antes de que la operación I/O externa haya retornado un resultado válido, y verificar siempre el booleano devuelto por `webbrowser.open()`.
- **Estado:** Verificado.















