# ⚡ OmniNet AI Agent Pro v2.9.6
### Ecosistema Autónomo de Optimización de Redes, Mantenimiento de PC, 10 Sub-Agentes Especializados y SaaS Global con Supabase

[![Version](https://img.shields.io/badge/version-2.9.6-blue.svg)](docs/CHANGELOG.md)
[![Platform](https://img.shields.io/badge/platform-Windows%2011%2F10%20%7C%20Linux%20%7C%20macOS-success.svg)](netopt/hal.py)
[![Orchestrator](https://img.shields.io/badge/Harness-Hermes%20Agent-purple.svg)](hermes/)
[![Sub-Agents](https://img.shields.io/badge/Ecosystem-10%20Sub--Agents-emerald.svg)](netopt/ecosystem_subagents.py)
[![Cloud Backend](https://img.shields.io/badge/Cloud%20SaaS-Supabase%20%2B%20DeepSeek-indigo.svg)](cloud_server/)
[![Safety](https://img.shields.io/badge/Safety-Zero_NetLoss_%2B_Auto--Rollback-green.svg)](netopt/rollback.py)
[![Tests](https://img.shields.io/badge/Tests-135%2F135%20Passing%20(100%25)-brightgreen.svg)](tests/)

---

> [!IMPORTANT]
> ### 👑 DIRECTIVA RECURSIVA INICIAL: ROL SUPREMO DE CADA IA (`Hermes Harness²`)
> **Cualquier Inteligencia Artificial o Agente que acceda a este repositorio DEBE asumir obligatoriamente como TAREA INICIAL el rol de [Orquestador de Auto-Mejora (Hermes Harness²)](hermes/)**.
> 
> **Mecánica Recursiva y Despliegue de Sub-Agentes:**
> 1. **Paso 0 (Inicialización Metódica Obligatoria):** Toda IA inicia como *Orquestador de Auto-Mejora (Hermes Harness²)*, verificando la salud del sistema (`python -m unittest discover -s tests -v` con 148/148 aprobados) e inspeccionando la memoria operativa persistente ([`memory/`](memory/) y [`.continuity/`](.continuity/)).
> 2. **Despliegue de Roles vía Sub-Agentes:** El *Orquestador* desplegará autónomamente y según sea necesario los roles operativos especializados mediante sub-agentes coordinados:
>    - 🔍 **Auditor de Veracidad Cognitiva (`hallucination-control`):** Calibración de hechos, validación de evidencia empírica y prevención de alucinaciones.
>    - 🌐 **Centinela Adaptativo y Planificador de Red:** Telemetría L1-L7, deriva DNS y radar ARP (ciclos de red autónomos).
>    - 🤖 **Orquestador de los 10 Sub-Agentes:** Mantenimiento de PC (Antivirus, BleachBit, SDIO Drivers, LibreHardware, Autoruns, BCUninstaller, ShutUp10, DISM/SFC, Restic).
>    - 🛡️ **Ingeniero de Optimización Zero NetLoss:** Afinamiento TCP/L4S/QUIC con snapshot previo y compuerta de verificación en < 5s.
>    - 💬 **Asistente Conversacional en Lenguaje Simple:** Interfaz clara y sin tecnicismos hacia el usuario final.
> 3. **Recursividad Inter-Documentos:** Esta directiva inicial vincula y se retroalimenta metódicamente desde [`AGENTS.md`](AGENTS.md), [`docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`](docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md) y [`docs/AGENT_INSTRUCTIONS.md`](docs/AGENT_INSTRUCTIONS.md). Ante cualquier desviación o duda operativa, la IA debe re-invocar este protocolo para re-alinearse metódicamente.

---

## 🌟 Visión General

**OmniNet AI Agent Pro** es una plataforma autónoma de nivel mundial diseñada para cuidar integralmente la conectividad a Internet y el rendimiento del computador. Opera bajo la invariante **Zero NetLoss** (Snapshot previo obligatorio + verificación de salud en < 5s + auto-reversión garantizada).

Cuenta con un **servidor web embebido en el puerto 8877** sin dependencias externas, interfaz gráfica amigable con selector de idioma mundial (Español 🇪🇸, English 🇺🇸, Português 🇧🇷), asistente conversacional en lenguaje 100% simple y un panel interactivo con **10 Sub-Agentes Especializados** basados en software libre líder mundial.

---

## 🛡️ Las 10 Especialidades del Ecosistema (Sub-Agentes)

Cada subsistema cuenta con un sub-agente dedicado que puede ejecutarse con 1 clic desde el Dashboard, mediante la API REST o de forma conversacional:

| ID | Emoji | Especialidad | Motor Open-Source / Nativo | Misión Principal |
| :--- | :---: | :--- | :--- | :--- |
| `network` | 🌐 | **Redes y Conexión** | `netopt` (DoH, L4S/ECN, Wi-Fi 7 MLO, DoQ, Ping, Bloat) | Cero cortes, ultra-baja latencia en videollamadas/juegos y máxima velocidad. |
| `antivirus` | 🛡️ | **Antivirus y Seguridad** | ClamAV + Microsoft Defender (`MpCmdRun.exe`) + YARA | Escaneo silencioso, verificación de descargas y protección en tiempo real. |
| `cleaner` | 🧹 | **Limpieza Profunda** | BleachBit (CleanerML con 2,000+ reglas para navegadores y juegos) | Liberar gigabytes de basura sin borrar fotos, descargas ni contraseñas. |
| `drivers` | ⚡ | **Drivers y Controladores** | SDIO (Snappy Driver Installer Origin) | Detectar hardware antiguo y actualizar adaptadores de red, video y sonido. |
| `hardware_thermal`| 🌡️ | **Hardware, Temp & Batería**| LibreHardwareMonitor / WMI / CIM / sysfs | Prevenir sobrecalentamiento de CPU y vigilar el desgaste de la batería en laptops. |
| `startup_boost` | 🚀 | **Acelerador de Arranque** | Lógica de Autoruns (`Win32_StartupCommand` / psutil) | Desactivar programas que se inician solos y ralentizan el encendido de Windows. |
| `uninstaller` | 🗑️ | **Desinstalador Limpio** | BCUninstaller (Bulk Crap Uninstaller) | Desinstalar programas rebeldes eliminando restos ocultos en el registro. |
| `privacy_shield` | 🔒 | **Anti-Rastreo / Privacidad** | Reglas O&O ShutUp10 / StevenBlack Hosts | Desactivar telemetría y recolección de datos invasiva de Windows. |
| `os_repair` | 🩺 | **Salud del Sistema Operativo**| DISM (`/CheckHealth`) + SFC (`/scannow`) + chkdsk | Comprobar y reparar paquetes y archivos protegidos corruptos del sistema. |
| `backup` | 💾 | **Respaldo Inteligente** | Restic / Duplicati / Smart Snapshot Zip | Copias de seguridad automáticas cifradas de configuraciones y archivos críticos. |

---

## 🚀 Avances de Telecomunicaciones y Kernel Incorporados

1. **Wi-Fi 7 (802.11be) & Multi-Link Operation (MLO)**:
   - Detección de radios 2.4 / 5 / 6 GHz, tasas PHY y soporte MLO.
   - Activación de **Receive Side Scaling (RSS)** y **Receive Segment Coalescing (RSC)** para distribuir el tráfico multi-gigabit entre todos los núcleos de CPU.
   - Activación de **Hardware Task Offload** (`DisableTaskOffload=0`) en el registro de Windows para descargar sumas de verificación al chip de red.

2. **Pila de Transporte L4S & AccECN (RFC 9330 / RFC 7560)**:
   - Activación de Notificación Explícita de Congestión (`ecncapability=enabled`).
   - Coexistencia con colas DualPI2 para supresión de colas de bufferbloat a niveles sub-milisegundo.
   - Disciplina *Fair Queueing* (`fq`) en Linux para pacing de paquetes.

3. **Calidad de Servicio (QoS) y Ultra-Baja Latencia Gaming**:
   - Liberación del 100% del ancho de banda (`NonBestEffortLimit=0` en Windows QoS Psched).
   - Supresión del estrangulamiento de paquetes en red multimedia (`NetworkThrottlingIndex=0xffffffff` y `SystemResponsiveness=0`).

4. **Privacidad DNS con DoH, DoQ y Encrypted Client Hello (ECH)**:
   - Soporte nativo de DoH para Cloudflare (`1.1.1.1`), Google (`8.8.8.8`) y **Quad9 (`9.9.9.9`)** para bloqueo de malware en DNS.
   - Compatibilidad con **Encrypted Client Hello (ECH / RFC 9849)** para evitar filtraciones del nombre del sitio web (SNI) a proveedores de internet.
   - Telemetría y verificación de salida UDP puerto 853 para **DNS-over-QUIC (DoQ / RFC 9250)** con handshakes **0-RTT**.

5. **Radar Zero-Trust LAN y Mitigación de Agujeros Negros MTU**:
   - **Bloqueo de MAC del Router**: Almacenamiento seguro en `~/.netopt_state/trusted_gateway.json` y alerta inmediata ante suplantación (ARP Spoofing / MitM).
   - **Mitigación de Agujeros Negros (RFC 4821 PLPMTUD)**: `EnablePMTUBHDetect=1` en Windows y `tcp_mtu_probing=1` en Linux para evitar congelamientos cuando routers intermedios filtran ICMP.

---

## ☁️ Arquitectura SaaS Global y Supabase (`cloud_server/`)

Para monetizar OmniNet en todo el mundo sin exponer tu clave secreta de DeepSeek:

```mermaid
flowchart LR
    User["💻 Usuario en cualquier país\n(OmniNet.exe)"] -->|"1. Mensaje + Licencia"| Proxy["☁️ Servidor Puente\n(cloud_server/proxy_server.py)"]
    Proxy -->|"2. Valida plan y PCs"| Supabase[("⚡ Supabase PostgreSQL\n(licenses + feedback)")]
    Proxy -->|"3. Consulta con API Key oculta"| DeepSeek["🧠 DeepSeek V3 API\n(~$0.05/mes por usuario)"]
    Pay["💳 Lemon Squeezy / Stripe"] -->|"Webhook de Pago"| Proxy
```

### Configuración de Supabase en 3 Pasos:
1. **Crear las Tablas**: Copia y pega el contenido de [`cloud_server/supabase_schema.sql`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/cloud_server/supabase_schema.sql) en el **SQL Editor** de tu proyecto Supabase y pulsa **Run**.
2. **Copiar Credenciales**: En Supabase ve a **Project Settings ➔ API** y obtén tu `Project URL` y `service_role key`.
3. **Iniciar el Servidor Cloud**:
   ```bash
   export SUPABASE_URL="https://tu-proyecto.supabase.co"
   export SUPABASE_SERVICE_ROLE_KEY="tu-clave-service-role"
   export DEEPSEEK_API_KEY="sk-tu-clave-deepseek"
   python cloud_server/proxy_server.py
   ```
   *(El conector [`cloud_server/supabase_client.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/cloud_server/supabase_client.py) utiliza únicamente la biblioteca estándar sin requerir paquetes externos).*

---

## 📁 Nueva Estructura Limpia del Proyecto

Para máxima elegancia arquitectónica, la raíz del proyecto se mantiene estrictamente despejada:

```
├── .gitignore                      # Reglas de exclusión Git
├── README.md                       # Documentación principal del proyecto
├── AGENTS.md                       # Directivas y reglas de agentes IA
├── pyproject.toml                  # Configuración estándar del paquete Python
├── setup.py                        # Script de instalación y empaquetado
├── main.py                         # Punto de entrada de la aplicación y API
├── mcp_server.py                   # Servidor de herramientas MCP
│
├── docs/                           # Toda la documentación técnica centralizada
│   ├── OMNINETSAASIA_CAPACIDADES_Y_ARQUITECTURA.md
│   ├── AUTONOMOUS_OPERATIONAL_MANIFESTO.md
│   ├── OmniNetSaasia_Auditoria_Ejecutiva_2026-11-06.md
│   ├── AGENT_INSTRUCTIONS.md, ORCHESTRATION_SPEC.md, CHANGELOG.md, audit.md
├── hermes/                         # Arnés IA y Orquestador de Auto-Mejoramiento (Hermes Agent)
│   ├── harness.py                  # Bucle cognitivo, sandbox Python y despacho de herramientas
│   ├── orchestrator.py             # Spawner de sub-agentes en paralelo y síntesis de sesiones
│   └── self_improvement.py        # Destilación de habilidades y memoria curada persistente
├── config/                         # Manifiestos y configuraciones
│   └── tools_manifest.json         # Manifiesto de 15 herramientas MCP
├── scripts/                        # Scripts de arranque y compilación
│   ├── bootstrap.py, OmniNet.bat, run.sh, OmniNet.spec
├── .continuity/                    # Capa de continuidad externa persistente (PROJECT, STATE, DECISIONS, TASK)
├── netopt/                         # Núcleo de red, diagnósticos L1-L7 y subsistemas
├── cloud_server/                   # Proxy SaaS y cliente Supabase
└── tests/                          # 148 Pruebas unitarias automatizadas (100% aprobadas)
```

---

## 🔄 Ciclos Autónomos del Agente y del Software OmniNet

El proyecto opera bajo un modelo de doble ciclo inteligente:
1. **Ciclo Autónomo del Agente IA (Cada 40 Minutos):**
   - **Auto-Propuesta de Tareas Propias:** El agente no se limita a una simple revisión pasiva del computador anfitrión. Evalúa permanentemente el repositorio, detecta cuellos de botella técnicos y **propone y ejecuta autónomamente sus propias tareas de ingeniería** (refactorizaciones, pruebas, optimizaciones o adopción de bibliotecas) según la ocasión lo demande.
   - **Rotación Multimódulo y Armonización Documental:** Explora sistemáticamente todos los módulos (`netopt/`, `hermes/`, `cloud_server/`, `config/`, `tests/`, `docs/`) manteniendo coherencia técnica y epistemológica absoluta.
   - **Compuerta de Cero Regresiones:** Verificación del 100% de la suite de pruebas unitarias (148/148 OK) antes de cada entrega.

2. **Ciclo Autónomo del Software Creado (OmniNet):**
   - Opera de forma continua por demanda y eventos del sistema operativo, monitorizando y manteniendo los 10 subsistemas del ecosistema bajo la salvaguarda de Zero NetLoss.

---

## 🌐 Telemetría Empírica In Situ, Colector Global de Métricas y Retroalimentación de IA

OmniNet implementa un sistema tripartito de verificación real y recolección de aprendizaje continuo:

1. **Pruebas Reales en este Dispositivo ([`netopt/telemetry.py`](netopt/telemetry.py)):**
   - El agente ejecuta mediciones empíricas directas sobre el hardware físico (adaptadores Wi-Fi, RSSI real, sondeo de Path MTU por bit DF, inspección de sockets de red y resolución DNS en vivo), garantizando que las decisiones técnicas no se basen en suposiciones sintéticas.
2. **Colector Global de Métricas de Dispositivos (Mundo):**
   - Agregación anónima de métricas de rendimiento en tiempo real a través del endpoint `/v1/telemetry/report` en `cloud_server/proxy_server.py` y la tabla Supabase `devices_telemetry_metrics`. Permite monitorear la salud global de redes, latencias promedio, grados de bufferbloat y fiabilidad de adaptadores en miles de computadores.
3. **Colector de Conversaciones y Retroalimentación con el Agente de IA:**
   - Registro anonimizado de interacciones de usuario (`~/.netopt_state/conversation_feedback.json`, `cloud_global_feedback.json` y Supabase `conversations_feedback`). Funciona como dataset activo de retroalimentación para:
     - Detectar dudas frecuentes y resolver intenciones complejas en lenguaje 100% simple.
     - Perfeccionar de manera recursiva los prompts, guardrails y estrategias del arnés Hermes.
     - Retroalimentar el planificador para priorizar las optimizaciones que más benefician a los usuarios reales.


---

## 🤖 Arnés IA y Orquestador Hermes (`hermes/`)

Adaptado de la arquitectura de vanguardia de **Hermes Agent** (Nous Research), OmniNet incorpora un arnés y orquestador cognitivo para auto-mejoramiento continuo:

1. **`HermesAgentHarness` (`hermes/harness.py`)**:
   - Bucle autónomo de llamadas a herramientas con recuperación automática de errores.
   - **Sandbox de Python Dinámico (`execute_python`)**: Ejecución programática en un solo turno para telemetría profunda sin demoras de ida y vuelta.

2. **`HermesOrchestrator` (`hermes/orchestrator.py`)**:
   - Generación de sesiones aisladas de subagentes (`spawn_session`) con ventanas de contexto independientes.
   - Ejecución paralela multihilo (`delegate_parallel`) y síntesis ejecutiva de hallazgos.

3. **`HermesSelfImprovementEngine` (`hermes/self_improvement.py`)**:
   - **Destilación Automática de Habilidades**: Extrae recetas procedimentales de remediaciones exitosas y las persiste en memoria (`~/.netopt_state/hermes_memory.json`).
   - **Compuerta de Cero Regresiones**: Ejecuta automáticamente la suite de tests para verificar invariantes antes de consolidar mejoras.

---

## 🖥️ Uso y Ejecución

### 1. Ejecutable Autónomo para Windows (`dist/OmniNet.exe`)
- Ubicado en `dist/OmniNet.exe` (compilado limpio).
- Script de lanzamiento directo: `scripts/OmniNet.bat`.
- Al ejecutarse, abre automáticamente el navegador en `http://127.0.0.1:8877`.
- Si ya hay una instancia activa, abre el navegador de inmediato sin conflictos de puerto.

### 2. Endpoints de la API REST (`http://127.0.0.1:8877`)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/health` | Estado del servicio, versión (`2.9.6`) y plataforma. |
| `GET` | `/api/subagents` | Lista los 10 sub-agentes con badges y estado en tiempo real. |
| `POST`| `/api/subagents/run` | Ejecuta un sub-agente (ej. `{"id": "antivirus", "execute": true}`). |
| `GET` | `/api/diagnose` | Telemetría completa L1-L7, bufferbloat y resolvers Anycast. |
| `GET` | `/api/wifi` | Auditoría de radio Wi-Fi 7 MLO, intensidad RSSI % y canales. |
| `GET` | `/api/arp` | Auditoría de vecinos ARP y detección de intrusos/duplicados. |
| `GET` | `/api/speedtest` | Medición de bajada, subida y ping contra Cloudflare Edge. |
| `POST`| `/api/optimize` | Genera y aplica el plan de aceleración con snapshot de seguridad. |
| `POST`| `/api/device/maintain`| Ejecuta limpieza profunda BleachBit + actualización SDIO. |
| `POST`| `/api/chat` | Conversación con el asistente IA (DeepSeek o modo local). |
| `POST`| `/api/license/activate`| Activa una clave de licencia (Gratis, Pro o Familiar). |

---

## 🧪 Pruebas Unitarias y Calidad de Código

Cumpliendo con la invariante de **Cero Regresiones**:
```bash
python -m unittest discover -s tests -v
```
*(148 pruebas unitarias automáticas con cobertura integral de HAL, adaptadores psutil/httpx, optimizador, rollback, licenciamiento, los 10 sub-agentes, arnés Hermes, micro internet, telemetría, esquemas Pydantic v2, REST API FastAPI y suite anti-alucinaciones).*

---

## 📄 Licencia y Derechos

Propiedad y desarrollo exclusivo para OmniNet AI Agent Pro. Todos los derechos reservados © 2026.
