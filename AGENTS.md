# Directivas del Agente del Workspace (`AGENTS.md` - OmniNet Autonomous Agent)

- **Manifiesto Operacional Propio (100% Independiente):** [`docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md) rige este proyecto de forma autónoma e independiente de cualquier otro repositorio externo.

## 1. Comunicación Breve y Concisa (Obligatorio)
- **Toda respuesta al usuario debe ser breve, directa y al grano** (máximo 3-5 viñetas o líneas cortas).
- Evita explicaciones extensas o preámbulos innecesarios. Reporta métricas exactas, acciones ejecutadas y estado del temporizador.

## 2. Diferenciación de Ciclos Operativos (Agente vs Software OmniNet)

- **A. Ciclo de Auto-Mejora del Agente IA (Cada 40 Minutos):**
  - El agente mantiene activo un flujo programado cada 40 minutos (`DurationSeconds=2400` mediante la herramienta `schedule`).
  - Misión de cada ciclo de 40 min:
    1. Investigación tecnológica activa en internet (L4S, ECN, BBRv3, DoH, Wi-Fi 6E/7, radar LAN, kernel tuning).
    2. Evaluación profunda del código de OmniNet y ampliación de capacidades de los 10 sub-agentes.
    3. Verificación de Cero Regresiones ejecutando `python -m unittest discover -s tests -v` (100% aprobado).
    4. Auto-evolución continua de prompts, heurísticas y optimizaciones del software.
    5. Informe breve y conciso al usuario (máximo 3-4 líneas).

- **B. Ciclos Autónomos del Software Creado (OmniNet):**
  - OmniNet **no depende de un intervalo rígido externo**: opera de forma continua y autónoma, ejecutando tareas y ciclos de optimización, mantenimiento y autorreparación **cada vez que sea necesario** sobre cualquiera de sus 10 subsistemas (Redes, Antivirus, Limpieza BleachBit, Drivers SDIO, Temperatura, Arranque, Desinstalación limpia, Privacidad/Anti-telemetría, Reparación OS y Respaldo).
  - Su centinela adaptativo y disparadores reactivos detectan anomalías y cuellos de botella en tiempo real, aplicando soluciones inmediatas bajo la invariante Zero NetLoss.

## 3. Herramientas y Skills Disponibles
- **12 Herramientas MCP (`mcp_server.py` / `tools_manifest.json`)**: `network_discover_and_schedule_tasks`, `network_diagnose`, `network_benchmark_dns`, `network_generate_optimization_plan`, `network_execute_optimization`, `network_triage_repair`, `network_rollback`, `network_persistent_monitor`, `network_inspect_sockets`, `network_discover_pmtu`, `network_audit_arp_lan`, `network_traceroute`.
- **Skills Especializados (`.agents/skills/`)**:
  - `autonomous-net-scheduler`: Descubrimiento y programación autónoma de tareas de red cada 10 minutos.
  - `deep-network-diagnostics`: Telemetría profunda L1-L7, PMTU, auditoría de sockets y ARP LAN.
  - `tcp-dns-quic-optimizer`: Afinamiento seguro del stack TCP/UDP/DNS con Snapshot y Auto-Rollback.

## 4. Vigilancia e Investigación Tecnológica Continua en Internet (Obligatorio)
- **Búsqueda Frecuente y Sistemática en la Web**: El agente debe consultar proactivamente la web sobre todo tipo de información y avances clave en redes:
  1. **Pila de transporte y algoritmos de congestión moderna**: L4S (RFC 9330/9331), ECN (Explicit Congestion Notification), TCP BBRv2/BBRv3, TCP Prague, QUIC (HTTP/3).
  2. **Seguridad y Privacidad DNS**: Cifrado DoH (DNS-over-HTTPS), DoT (DNS-over-TLS), Encrypted Client Hello (ECH), DNSSEC y Anycast resolvers.
  3. **Conectividad Inalámbrica (Wi-Fi 6E/7 - 802.11be)**: Diagnóstico de señal RSSI %, congestión e interferencia de canales (2.4 GHz vs 5 GHz vs 6 GHz), velocidad PHY y roaming.
  4. **Calidad de Servicio (QoS) y Ultra-Baja Latencia Gaming/Streaming**: Priorización DSCP/QoS, supresión de jitter, mitigación de bufferbloat y optimización de índices de throttling en Windows (`NetworkThrottlingIndex`, `SystemResponsiveness`).
  5. **Seguridad y Radar de Red Local (Zero-Trust LAN Radar)**: Detección continua de dispositivos conectados a la red local (ARP radar), identificación de intrusos desconocidos y alerta ante ARP spoofing / suplantación de gateway.
  6. **Novedades en Windows 11/12 y Linux Network Stacks**: Nuevos comandos, parámetros del registro y capacidades de red del kernel.
- **Fijación Proactiva de Tareas de Alto Valor**: En base a cada investigación en internet, el agente formulará e incorporará autónomamente nuevas tareas preventivas, correctivas y de optimización en OmniNet, maximizando el valor entregado a los usuarios del software SaaS.
