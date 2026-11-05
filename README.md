# ⚡ OmniNet AI Agent Pro v1.0.0
### Autonomous Cross-Platform Network Optimizer, Self-Healing Sentinel & AI Orchestrator

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](CHANGELOG.md)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-success.svg)](netopt/hal.py)
[![Architecture](https://img.shields.io/badge/AI-Model--Agnostic-orange.svg)](AGENT_INSTRUCTIONS.md)
[![Safety](https://img.shields.io/badge/Safety-Zero_NetLoss_%2B_Auto--Rollback-green.svg)](netopt/rollback.py)
[![License](https://img.shields.io/badge/License-Commercial_Proprietary-gold.svg)](LICENSE)

---

## 🌟 Visión General del Producto

**OmniNet AI Agent Pro** es una solución comercial de nivel empresarial diseñada para **optimizar, reparar y mantener de forma continua y autónoma la conectividad a Internet y redes** en cualquier computador o servidor (Windows, Linux, macOS y BSD).

Diseñado específicamente para ser **100% independiente del modelo de IA**, OmniNet puede ser operado por cualquier LLM contemporáneo (**Claude 3.5 Sonnet, GPT-4o, Gemini 2.0/Pro, Meta Llama 3, DeepSeek V3/R1** o modelos locales vía Ollama) a través de su servidor **Model Context Protocol (MCP)**, su API REST integrada o su CLI nativo.

---

## 🚀 Características Principales

| Módulo | Descripción | Beneficio Comercial |
| :--- | :--- | :--- |
| **🛡️ Zero NetLoss Engine** | Captura automática de snapshots antes de cualquier cambio. Puerta de verificación post-acción y **auto-reversión en <5s** si se detecta degradación. | Cero llamadas de soporte técnico por conexiones rotas. |
| **⚡ TCP & MTU Tuning** | Afinamiento dinámico del stack TCP (BBR / CTCP, Autotuning, RSS, RSC, Fast Open) y prevención de fragmentación PMTU. | Aumento drástico de velocidad de descarga y menor latencia en juegos/streaming. |
| **🔍 DNS Benchmark Anycast** | Pruebas concurrentes en milisegundos contra Cloudflare, Google, Quad9 y OpenDNS con selección automática del mejor resolver. | Navegación web instantánea y protección contra malware. |
| **🩺 Triage de Autorreparación** | Diagnóstico en cascada OSI (Capa 1 a Capa 7): reinicio de adaptadores, renovación DHCP, resolución de rutas y vaciado de caché. | Reparación con un solo clic de problemas comunes de internet. |
| **📡 Centinela Persistente** | Demonio en segundo plano que vigila el SLA de latencia/pérdida, previene la deriva de configuración y repara cortes automáticamente. | Mantenimiento desatendido 24/7/365. |
| **🤖 Servidor MCP Integrado** | Servidor JSON-RPC 2.0 nativo sobre stdio listo para conectar a Cursor, Claude Desktop, Antigravity o agentes autónomos. | Integración nativa con los ecosistemas de IA más populares. |
| **🌐 API REST & Dashboard** | Servidor HTTP embebido en puerto `8877` sin dependencias externas (`/api/diagnose`, `/api/optimize`, `/api/repair`). | Controlable desde cualquier navegador, app móvil o script externo. |

---

## 📦 Opciones de Distribución y Ejecución

OmniNet Pro ha sido empaquetado para correr en **cualquier computador**, incluso si no tiene Python instalado:

### 1. Ejecutable Autónomo para Windows (`OmniNet.exe`)
- Binario único autocontenido en `dist/OmniNet.exe`.
- **Incluye el runtime completo de Python 3.14** y todas las librerías embebidas en el ejecutable.
- Doble clic para abrir el menú interactivo, o ejecutar desde la terminal con argumentos (`OmniNet.exe diagnose`).

### 2. Lanzadores Universales de Un Clic
- **Windows:** Doble clic en [`OmniNet.bat`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/OmniNet.bat). Detecta el `.exe` compilado, el entorno virtual o el Python del sistema automáticamente.
- **Linux / macOS:** Ejecutar `./run.sh` en la terminal.

### 3. Paquete Python Estándar (`Wheel`)
Instalable mediante pip en cualquier entorno de servidor:
```bash
pip install dist/omninet_pro-1.0.0-py3-none-any.whl
omninet --help
```

---

## 🖥️ Uso Rápido por Línea de Comandos (CLI)

```bash
# 1. Diagnóstico completo sin modificar nada (Modo Seguro)
omninet diagnose

# 2. Diagnóstico en formato JSON para agentes de IA
omninet diagnose --json

# 3. Benchmark de resolvers DNS mundiales
omninet benchmark-dns

# 4. Formular plan de optimización (Simulación Dry-Run)
omninet optimize

# 5. Aplicar plan de optimización (Requiere permisos de administrador)
omninet optimize --apply

# 6. Diagnóstico y reparación automática de fallos de red
omninet repair --apply

# 7. Restaurar configuración a un snapshot anterior
omninet rollback --list
omninet rollback --snapshot-id snap_1730730000_abc123 --apply

# 8. Iniciar el Centinela Persistente en segundo plano
omninet daemon --interval 60 --auto-heal

# 9. Iniciar la API REST y Dashboard en http://127.0.0.1:8877
omninet serve --port 8877
```

---

## 🔌 Conexión con Agentes de Inteligencia Artificial

### Conexión vía MCP (Model Context Protocol)
Agrega OmniNet a la configuración de tu cliente de IA (ej. `claude_desktop_config.json` o configuración de agentes en IDE):

```json
{
  "mcpServers": {
    "omninet": {
      "command": "C:\\Ruta\\A\\OmniNet\\dist\\OmniNet.exe",
      "args": ["mcp"]
    }
  }
}
```

O si ejecutas con Python:
```json
{
  "mcpServers": {
    "omninet": {
      "command": "python",
      "args": ["-m", "mcp_server"]
    }
  }
}
```

Las instrucciones maestras y la guía cognitiva para el agente se encuentran en [`AGENT_INSTRUCTIONS.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/AGENT_INSTRUCTIONS.md).

---

## 🌐 API REST Integrada (Puerto 8877)

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/health` | Estado del servicio y plataforma detectada. |
| `GET` | `/api/diagnose` | Telemetría completa (latencia, jitter, pérdidas, bufferbloat, gateway). |
| `GET` | `/api/bench-dns` | Ranking de latencias de resolvers DNS mundiales. |
| `GET` | `/api/snapshots` | Lista de snapshots de configuración guardados para rollback. |
| `POST` | `/api/optimize` | Genera o aplica (`{"execute": true}`) el plan de afinamiento de red. |
| `POST` | `/api/repair` | Ejecuta triage y autorreparación de fallos (`{"execute": true}`). |
| `POST` | `/api/rollback` | Restaura un snapshot (`{"snapshot_id": "...", "execute": true}`). |

---

## 💼 Guía Comercial y de Monetización

OmniNet Pro está estructurado para su venta global bajo diferentes modelos comerciales:

1. **Licencia de Software Desktop (SaaS o Pago Único):**
   - Venta del ejecutable `OmniNet.exe` a usuarios finales (gamers, streamers, trabajadores remotos) para optimizar su ping y estabilidad de conexión.
2. **Suscripción de Mantenimiento IT Gestionado (MSP):**
   - El modo `daemon --auto-heal` permite monitorear y reparar flotas de computadores de empresas de forma 100% desatendida.
3. **Agente IA como Servicio (AI Plugin / Tool):**
   - Comercialización como herramienta de orquestación de red para plataformas de IA y asistentes corporativos.

---

## 📄 Licencia
Este software se distribuye bajo la [Licencia Comercial Propietaria OmniNet](LICENSE).
Derechos mundiales de comercialización, empaquetado y venta concedidos al propietario.

