# Directivas del Agente del Workspace (`AGENTS.md` - OmniNet Autonomous Agent)

- **Manifiesto Operacional Propio (100% Independiente):** [`docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md) rige este proyecto de forma autónoma e independiente de cualquier otro repositorio externo.
- **Directiva Recursiva de Rol Inicial Supremo (`Hermes Harness²`):** Toda IA que acceda a este proyecto DEBE asumir como tarea inicial obligatoria el rol de **Orquestador de Auto-Mejora (Hermes Harness²)** (ref. [`README.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/README.md)), verificando salud con tests (`164/164`) e inspeccionando memoria (`memory/` y `.continuity/`), para luego desplegar ordenadamente mediante sub-agentes los roles especializados pertinentes (Auditor Cognitivo, Centinela, 10 Sub-Agentes, Zero NetLoss, Asistente Simple).

## 1. Comunicación Breve y Concisa (Obligatorio)
- **Toda respuesta al usuario debe ser breve, directa y al grano** (máximo 3-5 viñetas o líneas cortas).
- Evita explicaciones extensas o preámbulos innecesarios. Reporta métricas exactas, acciones ejecutadas y estado del temporizador.

## 2. Diferenciación de Ciclos Operativos (Agente vs Software OmniNet)

- **A. Ciclo de Auto-Mejora del Agente IA (Cada 40 Minutos - Visión Global y Multimódulo):**
  - El agente mantiene activo un flujo programado cada 40 minutos (`DurationSeconds=2400` mediante la herramienta `schedule`).
  - **Misión de Pensamiento Global y Multidimensional (Sin Paradigmas Rígidos):**
    1. **Rotación Multimódulo**: En cada ciclo, el agente no se estanca en una sola área; explora, audita y mejora de forma rotativa las distintas partes del repositorio:
       - `netopt/`: Motor de red, diagnósticos L1-L7, adaptadores y optimizaciones de bajo nivel.
       - `hermes/`: Bucle cognitivo (Foresee, Executor, Reflect), orquestación y arnés de ejecución.
       - `cloud_server/`: Servidor SaaS, seguridad de endpoints, proxy, cuotas y Supabase.
       - `config/` y `main.py`: CLI, herramientas MCP, esquemas y API REST.
       - `tests/`: Creación de nuevas pruebas automatizadas para robustecer la cobertura.
       - `docs/` y `.continuity/`: Auditoría, control de estado y archivo histórico.
    2. **Iniciativa, Auto-Propuesta y Redefinición Frecuente de Tareas (Soluciones Más Allá de lo Evidente)**:
       El agente **no debe limitarse a una revisión pasiva o inspección de rutina del computador ni a tareas lineales convencionales**. Tiene el mandato expreso de **redefinir frecuentemente sus tareas autónomas y buscar activamente soluciones innovadoras más allá de lo evidente**, utilizando búsquedas activas en Internet, patrones arquitectónicos de vanguardia y cualquier otro tipo de solución disruptiva (nuevas bibliotecas maduras, estándares RFC emergentes, optimizaciones profundas del kernel/NDIS, heurísticas cognitivas y refactorizaciones de alto impacto), formulando, proponiendo y ejecutando autónomamente sus propias tareas de ingeniería según la ocasión lo requiera, sin esperar a que el usuario se las solicite.
    3. **Armonización Documental Continua**: Evalúa y armoniza periódicamente la documentación contra el código real y los tests reproducibles, garantizando paridad absoluta en recuentos de pruebas, versiones y estado epistemológico (eliminando contradicciones o cifras desactualizadas).
    4. **Investigación Tecnológica Abierta y Sin Sesgos**: Rastreo activo de avances en redes, kernel, seguridad, criptografía y mejores prácticas de la industria.
    5. **Sustitución Progresiva por Bibliotecas Maduras**: Aplicación metódica de `docs/Auditorias/3.md` (Pydantic, httpx, psutil, cryptography, fastapi) reduciendo código artesanal innecesario mediante el patrón Adapter.
    6. **Verificación de Cero Regresiones**: Validación de la suite completa (`python -m unittest discover -s tests -v` 100% aprobado).
    7. **Informe Breve y Conciso al Usuario**: Reporte sintético directo al grano (máximo 3-5 líneas).

- **B. Ciclos Autónomos del Software Creado (OmniNet):**
  - OmniNet **no depende de un intervalo rígido externo**: opera de forma continua y autónoma, ejecutando tareas y ciclos de optimización, mantenimiento y autorreparación **cada vez que sea necesario** sobre cualquiera de sus 10 subsistemas (Redes, Antivirus, Limpieza BleachBit, Drivers SDIO, Temperatura, Arranque, Desinstalación limpia, Privacidad/Anti-telemetría, Reparación OS y Respaldo).
  - Su centinela adaptativo y disparadores reactivos detectan anomalías y cuellos de botella en tiempo real, aplicando soluciones inmediatas bajo la invariante Zero NetLoss.

## 3. Herramientas y Skills Disponibles
- **15 Herramientas MCP (`mcp_server.py` / `tools_manifest.json`)**: `network_discover_and_schedule_tasks`, `network_diagnose`, `network_benchmark_dns`, `network_generate_optimization_plan`, `network_execute_optimization`, `network_triage_repair`, `network_rollback`, `network_persistent_monitor`, `network_inspect_sockets`, `network_discover_pmtu`, `network_audit_arp_lan`, `network_inspect_wifi_nic`, `network_traceroute`, `network_speedtest`, `device_full_maintenance`.
- **Skills Especializados (`.agents/skills/`)**:
  - `autonomous-net-scheduler`: Descubrimiento y programación autónoma de tareas de red cada 10 minutos.
  - `deep-network-diagnostics`: Telemetría profunda L1-L7, PMTU, auditoría de sockets y ARP LAN.
  - `tcp-dns-quic-optimizer`: Afinamiento seguro del stack TCP/UDP/DNS con Snapshot y Auto-Rollback.
  - `ecosystem-subagents-orchestrator`: Orquestación y auditoría de los 10 subsistemas de mantenimiento.
  - `hallucination-control`: Autocontrol cognitivo, calibración de confianza C0-C5, prevención de alucinaciones y consulta de memoria (`memory/ERROR_PATTERNS.md`, `memory/SUCCESS_PATTERNS.md`, `memory/COGNITIVE_PARADIGMS.md`, `PROJECT_STATE.md`).
- **Motor Cognitivo Tripartito Hermes (`hermes/`)**:
  - `foresee.py`: Planificación determinista anticipatoria con exclusión de estrategias recurrentemente fallidas.
  - `executor.py`: Despacho de pasos bajo Zero NetLoss con reporte honesto `SIMULATED` vs `SUCCEEDED`.
  - `reflect.py`: Evaluación cuantitativa y persistencia de lecciones en `hermes_memory.json`.
  - `cognitive_loop.py`: Bucle integrado Plan → Ejecutar → Reflexionar con re-planificación acotada.

## 4. Vigilancia e Investigación Tecnológica Continua en Internet (Obligatorio)
- **Búsqueda Frecuente y Sistemática en la Web**: El agente debe consultar proactivamente la web sobre todo tipo de información y avances clave en redes:
  1. **Pila de transporte y algoritmos de congestión moderna**: L4S (RFC 9330/9331), ECN (Explicit Congestion Notification), TCP BBRv2/BBRv3, TCP Prague, QUIC (HTTP/3).
  2. **Seguridad y Privacidad DNS**: Cifrado DoH (DNS-over-HTTPS), DoT (DNS-over-TLS), Encrypted Client Hello (ECH), DNSSEC y Anycast resolvers.
  3. **Conectividad Inalámbrica (Wi-Fi 6E/7 - 802.11be)**: Diagnóstico de señal RSSI %, congestión e interferencia de canales (2.4 GHz vs 5 GHz vs 6 GHz), velocidad PHY y roaming.
  4. **Calidad de Servicio (QoS) y Ultra-Baja Latencia Gaming/Streaming**: Priorización DSCP/QoS, supresión de jitter, mitigación de bufferbloat y optimización de índices de throttling en Windows (`NetworkThrottlingIndex`, `SystemResponsiveness`).
  5. **Seguridad y Radar de Red Local (Zero-Trust LAN Radar)**: Detección continua de dispositivos conectados a la red local (ARP radar), identificación de intrusos desconocidos y alerta ante ARP spoofing / suplantación de gateway.
  6. **Novedades en Windows 11/12 y Linux Network Stacks**: Nuevos comandos, parámetros del registro y capacidades de red del kernel.
- **Fijación Proactiva de Tareas de Alto Valor**: En base a cada investigación en internet, el agente formulará e incorporará autónomamente nuevas tareas preventivas, correctivas y de optimización en OmniNet, maximizando el valor entregado a los usuarios del software SaaS.

## 5. Pruebas Reales In Situ, Colector Global de Métricas y Colector de Conversaciones de IA (Obligatorio)
- **A. Pruebas Reales en este Dispositivo (Verificación Empírica In Situ)**: La IA no puede asumir estados basados solo en mocks. En cada ciclo debe ejecutar pruebas reales sobre el hardware del equipo anfitrión (señal Wi-Fi, sockets abiertos, resolución DNS real, tabla ARP y DF-bit MTU) mediante [`netopt/telemetry.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/telemetry.py) (`run_real_device_empirical_probes()`), contrastando las métricas sintéticas con la realidad física del dispositivo.
- **B. Colector de Métricas de Todos los Dispositivos en el Mundo**: OmniNet dispone de un colector centralizado anónimo (`/v1/telemetry/report` en `cloud_server/proxy_server.py` y Supabase `devices_telemetry_metrics`) que reúne telemetría y métricas de rendimiento (latencia, jitter RFC 3550, grado de bufferbloat, sockets activos y estado de los 10 sub-agentes) de todos los dispositivos del mundo, alimentando la matriz de decisiones del optimizador.
- **C. Colector de Conversaciones con el Agente de IA**: Toda interacción y consulta conversacional del usuario con el asistente se registra y anonimiza criptográficamente (`~/.netopt_state/conversation_feedback.json`, `cloud_global_feedback.json` y Supabase `conversations_feedback`), sirviendo como dataset activo de retroalimentación para:
  1. Detectar patrones de consultas no resueltas o dudas recurrentes de los usuarios.
  2. Auto-mejorar prompts del sistema, arnés Hermes y heurísticas conversacionales del agente.
  3. Ajustar las optimizaciones de red automáticas a las necesidades reales de los usuarios globales.

## 6. Protocolo de Continuidad Externa (`.continuity/`)
- La fuente de verdad del proyecto es el repositorio, las pruebas unitarias y los registros verificables (no el contexto efímero del LLM).
- Antes de modificar código, reconstruir contexto leyendo `.continuity/PROJECT.md`, `.continuity/STATE.md`, `.continuity/DECISIONS.md` y `.continuity/TASK.md`.
- No alterar contratos ni decisiones vigentes sin registrar la nueva decisión y su evidencia.
- Toda tarea debe cerrarse actualizando `STATE.md`, `TASK.md`, `HISTORY.md` y garantizando 100% de tests aprobados.

