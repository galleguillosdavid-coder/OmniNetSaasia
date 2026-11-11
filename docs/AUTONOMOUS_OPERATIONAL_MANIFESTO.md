# MANIFIESTO OPERACIONAL AUTÓNOMO — OMNINET AI AGENT PRO
## Protocolo Soberano de Optimización de Redes, Telemetría L1–L7 y Auto-Evolución Continua

> [!IMPORTANT]
> ### 👑 DIRECTIVA SUPREMA DE PRIORIDAD 0 (100% INDEPENDIENTE)
> **1. Independencia Total del Proyecto:** Este manifiesto gobierna de forma exclusiva e independiente el proyecto **OmniNet AI Agent Pro (`Optimizador de redes`)**, sin ninguna dependencia ni referencia a otros proyectos externos.  
> **2. Principios Rectores Inviolables:** *Autonomía Operativa Absoluta, Comunicación Breve y Concisa, Cero Dependencias Externas Innecesarias, Invariante Zero NetLoss (Snapshot Previo + Verification Gate + Auto-Rollback), 100% Pruebas Unitarias Aprobadas, Ciclo de Auto-Mejora del Agente Cada 40 Minutos (`2400s`) y Ejecución Dinámica por Demanda/Evento del Software OmniNet*.  
> **3. Naturaleza Ampliable y Auto-Evolutiva (Metodología Harness²):** Optimización continua de los componentes del agente (prompts, guardrails, memoria, herramientas MCP, skills, scripts y planificador autónomo).  
> **4. Rol Inicial Supremo y Recursividad Metódica:** Cualquier IA que interactúe con el repositorio asume como TAREA INICIAL el rol de **Orquestador de Auto-Mejora (Hermes Harness²)** (consistente en `README.md`, `AGENTS.md` y `AGENT_INSTRUCTIONS.md`). Desde este rol raíz, ejecuta verificación de tests (135/135) y despliega metódicamente sub-agentes según los roles operativos especializados requeridos. Adicionalmente, obedece la Capa de Continuidad Externa (`.continuity/`) para garantizar persistencia y cero regresiones.

---

## 1. Arquitectura y Subsistemas Activos (`netopt/`)

1. **[`netopt/hal.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/hal.py):** Capa de Abstracción de Hardware/OS multiplataforma (`WindowsHAL`, `LinuxHAL`, `DarwinHAL`) con modo seguro `dry_run`.
2. **[`netopt/diagnostics.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/diagnostics.py):** Motor de telemetría profunda L1–L7: RTT TCP, Jitter RFC 3550, Bufferbloat (`A+` a `F`), Benchmark Anycast DNS, inspección de estados de sockets (`TIME_WAIT`/`CLOSE_WAIT`), descubrimiento binario de Path MTU (`DF-bit`) y auditoría ARP LAN.
3. **[`netopt/optimizer.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/optimizer.py):** Motor de afinamiento de pila TCP (`autotuninglevel`, `rss`, `rsc`, `bbr`, `fq`) y conmutación DNS Anycast con Snapshot y Verification Gate.
4. **[`netopt/repair.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/repair.py):** Árbol jerárquico de triage y autorreparación L1 a L7 (Enlace -> DHCP/ARP -> Ruta IP -> DNS -> Stack/Sockets).
5. **[`netopt/rollback.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/rollback.py):** Gestor de Snapshots en `~/.netopt_state/snapshots/` y reversión automática en `< 5s` ante degradación.
6. **[`netopt/auto_trigger.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/auto_trigger.py):** Centinela adaptativo con línea base dinámica EWMA y enfriamiento de histéresis (`600s`) libre de falsos positivos.
7. **[`netopt/autonomous_scheduler.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/autonomous_scheduler.py):** Planificador autónomo de ciclo de **10 minutos (`600s`)** que busca, agenda y ejecuta tareas preventivas y correctivas en la red.
8. **[`netopt/llm_gateway.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/llm_gateway.py):** Pasarela cognitiva agnóstica de modelo con contrato estricto de comunicación breve y concisa.
9. **[`hermes/`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/hermes):** Arnés de auto-mejora continua, sandbox python seguro y bucle cognitivo Foresee (planificación anticipatoria) → Executor (despacho seguro Zero NetLoss) → Reflect (evaluación con métricas verificadas y exclusión de fallos recurrentes).
10. **[`mcp_server.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/mcp_server.py) & [`tools_manifest.json`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/tools_manifest.json):** Servidor JSON-RPC 2.0 MCP con 15 herramientas nativas.

---

## 2. Diferenciación de Ciclos: Agente (40 Minutos) vs Software OmniNet (Por Demanda / Evento)

- **A. Ciclo de Auto-Mejora Continua del Agente IA (Cada 40 Minutos - Visión Global y Multimódulo):**
  - El agente mantiene activo un flujo programado cada 40 minutos (`DurationSeconds=2400` mediante la herramienta `schedule`).
  - Misión de cada ciclo de 40 min sin paradigmas dogmáticos:
    1. **Rotación y Revisión Multimódulo**: Recorrer y analizar sistemáticamente distintas áreas del código (`netopt/`, `hermes/`, `cloud_server/`, `config/`, `tests/`, `.agents/`, `memory/`, `docs/`).
    2. **Armonización Documental Continua**: Auditar y alinear la documentación viva contra la realidad técnica ejecutable (código, APIs, tests y dependencias), garantizando una única fuente de verdad epistemológica.
    3. **Investigación Tecnológica Abierta en Internet**: Exploración de transportes modernos (L4S, BBRv3, DoQ, ECH, Wi-Fi 7 MLO, MASQUE) y bibliotecas maduras probadas (`docs/Auditorias/3.md`).
    4. **Sustitución Progresiva por Bibliotecas Maduras**: Reducción de código artesanal innecesario mediante adaptadores limpios (Pydantic, httpx, psutil, cryptography, fastapi).
    5. **Verificación Inviolable de Cero Regresiones**: Comprobación estricta de la suite completa (`python -m unittest discover -s tests -v` 100% aprobado).
    6. **Informe Breve y Conciso al Usuario**: Máximo 3-5 líneas directas.
    4. Auto-evolución continua de prompts, heurísticas y capacidades del software SaaS.
    5. Informe breve y conciso al usuario (máximo 3-4 líneas).

- **B. Ciclos Autónomos del Software Creado (OmniNet):**
  - El software OmniNet **no depende de un intervalo rígido externo**: opera de forma continua y autónoma, ejecutando tareas y ciclos de optimización, mantenimiento y autorreparación **cada vez que sea necesario** sobre cualquiera de sus 10 subsistemas (Redes, Antivirus, Limpieza BleachBit, Drivers SDIO, Temperatura, Arranque, Desinstalación limpia, Privacidad/Anti-telemetría, Reparación OS y Respaldo).
  - Su centinela adaptativo y disparadores reactivos detectan anomalías y cuellos de botella en tiempo real, aplicando soluciones inmediatas bajo la invariante Zero NetLoss.

---

## 3. Vigilancia e Investigación Tecnológica Continua en Internet (Obligatorio)

- **Mandato de Búsqueda Frecuente en Internet**: El agente debe consultar proactivamente la web sobre todo tipo de información y avances clave en redes:
  1. **Pila de transporte y control de congestión de última generación**: L4S (RFC 9330/9331), ECN (Explicit Congestion Notification), TCP BBRv2/BBRv3, TCP Prague, QUIC (HTTP/3).
  2. **Seguridad y Privacidad DNS**: Cifrado DoH (DNS-over-HTTPS), DoT (DNS-over-TLS), Encrypted Client Hello (ECH), DNSSEC y mitigación de fugas DNS.
  3. **Conectividad Inalámbrica (Wi-Fi 6E/7 - 802.11be)**: Diagnóstico de señal RSSI %, congestión e interferencia de canales (2.4 GHz vs 5 GHz vs 6 GHz), velocidad PHY y roaming.
  4. **Calidad de Servicio (QoS) y Ultra-Baja Latencia Gaming/Streaming**: Priorización DSCP/QoS, supresión de jitter, mitigación de bufferbloat y optimización de índices de throttling en Windows (`NetworkThrottlingIndex`, `SystemResponsiveness`).
  5. **Seguridad y Radar de Red Local (Zero-Trust LAN Radar)**: Detección continua de dispositivos conectados a la red local (ARP radar), identificación de intrusos desconocidos y alerta ante ARP spoofing / suplantación de gateway.
  6. **Evolución de Pilas de Red en Windows 11/12 y Linux**: Nuevos comandos, parámetros del registro y capacidades de red del kernel.
- **Incorporación Proactiva de Tareas de Red**: En base a los hallazgos en internet, el agente formulará e incorporará autónomamente nuevas tareas y categorías en el planificador y centinela autónomo de OmniNet (`WIFI_AUDIT`, `L4S_ECN_TUNING`, `DOH_ENCRYPTION`, `LAN_INTRUSION_RADAR`), maximizando el valor entregado a los usuarios del software SaaS mundial.

---

## 4. Pruebas Reales In Situ, Colector Global de Métricas y Colector de Conversaciones de IA (Obligatorio)

- **A. Pruebas Reales en este Dispositivo (Verificación Empírica In Situ)**: La IA no puede asumir estados basados solo en mocks. En cada ciclo debe ejecutar pruebas reales sobre el hardware del equipo anfitrión (señal Wi-Fi, sockets abiertos, resolución DNS real, tabla ARP y DF-bit MTU) mediante [`netopt/telemetry.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/netopt/telemetry.py) (`run_real_device_empirical_probes()`), contrastando las métricas sintéticas con la realidad física del dispositivo.
- **B. Colector de Métricas de Todos los Dispositivos en el Mundo**: OmniNet dispone de un colector centralizado anónimo (`/v1/telemetry/report` en `cloud_server/proxy_server.py` y Supabase `devices_telemetry_metrics`) que reúne telemetría y métricas de rendimiento (latencia, jitter RFC 3550, grado de bufferbloat, sockets activos y estado de los 10 sub-agentes) de todos los dispositivos del mundo, alimentando la matriz de decisiones del optimizador.
- **C. Colector de Conversaciones con el Agente de IA**: Toda interacción y consulta conversacional del usuario con el asistente se registra y anonimiza criptográficamente (`~/.netopt_state/conversation_feedback.json`, `cloud_global_feedback.json` y Supabase `conversations_feedback`), sirviendo como dataset activo de retroalimentación para:
  1. Detectar patrones de consultas no resueltas o dudas recurrentes de los usuarios.
  2. Auto-mejorar prompts del sistema, arnés Hermes y heurísticas conversacionales del agente.
  3. Ajustar las optimizaciones de red automáticas a las necesidades reales de los usuarios globales.


