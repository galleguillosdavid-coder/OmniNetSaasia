# 📋 Pendientes, Alternativas Seleccionables y Guía Operativa (`OmniNet AI Agent Pro`)

> Documento vivo de continuidad para alinear qué le falta al programa, qué decisiones o recursos necesita el agente de tu parte, y cómo hacerlo **más operativo, usable y sencillo**.
>
> **Estado base verificado:** `227/227` tests unitarios aprobados (`OK`), API FastAPI/Uvicorn en `http://127.0.0.1:8877`, Cloud SaaS en `:9988`, motor cognitivo Hermes y telemetría empírica in situ activos.

---

## 1. ¿Qué le falta actualmente al programa?
te otorgo el privilegio y la autoridad para que lo hagas tu mismo
| Área | Brecha / Pendiente Real | Impacto Actual |
| :--- | :--- | :--- |
| **1. Secretos y Cloud SaaS** | Faltan `OMNINET_LICENSE_SECRET`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_ANON_KEY` y `OMNINET_WEBHOOK_SECRET`. | En desarrollo emite `RuntimeWarning` con clave efímera; en producción bloquea emisión/verificación (`fail-closed`). Supabase opera en fallback JSON local. |
| **2. Privilegios y Reparación en Vivo** | Por seguridad (`OMNI-038` Zero NetLoss), `AutoSentinel` nace inactivo (`enabled=False`) y HAL en `dry_run=True` sin `OMNINET_ALLOW_LIVE_AUTOREPAIR=1` ni elevación Admin. | Diagnostica y simula planes, pero no aplica cambios reales en `netsh`/Registro `HKLM` hasta que autorices elevación y modo vivo. |
| **3. Software Externo (Sub-Agentes)** | En este equipo `drivers` (`SDIO`) figura como `No Instalado`; herramientas portables opcionales (`BleachBit`, `Restic`, `LibreHardwareMonitor`, `ShutUp10++`, `BCUninstaller`) amplían los 10 sub-agentes. | Los sub-agentes nativos (`network`, `antivirus` Defender, `os_repair` SFC/DISM, `startup_boost`) funcionan ya; los externos requieren descarga/ruta local. |
| **4. Usabilidad y Sencillez (1-Clic)** | Hoy requiere abrir consola y ejecutar `python main.py serve`. Falta un lanzador directo/System Tray o ejecutable `.exe` único con perfil preconfigurado. | Fricción para usuarios no técnicos al iniciar, ver alertas en bandeja o actualizar. |
| **5. Deuda Técnica Cloud (`docs/Auditorias/3.md`)** | `cloud_server/proxy_server.py` aún usa `http.server` estándar (mientras la API local ya migró a FastAPI/Uvicorn). | Funciona y pasa `15/15` tests, pero migrarlo a FastAPI simplificará mantenimiento y despliegue en la nube. |
| **6. Asistente IA Conversacional** | Falta configurar `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` o un servidor `Ollama` local en el equipo. | Sin clave o Ollama, el chat opera solo con respuestas deterministas/heurísticas locales. |
| **7. Hardware Wi-Fi 7 / L4S (Opcional)** | El adaptador actual opera en `Wi-Fi 5 GHz` (`is_wifi7: false`). | No impide operar, pero impide validar en hardware real MLO (6 GHz) o colas L4S del router. |

---

## 2. Alternativas Seleccionables (Marca tus preferencias)

Edita este archivo marcando `[x]` en las opciones que prefieras para que el agente ejecute tu hoja de ruta:

### A. Modelo de Despliegue y Datos
- [ ] **Opción A1 (Recomendada para uso personal):** **100% Local-First** — Sin nube ni Supabase; historial, métricas y snapshots locales en `~/.netopt_state/`.
- [x] **Opción A2 (Modo SaaS Multi-Dispositivo):** **Cloud + Supabase** — Proyecto Supabase `OmniNet` (`zptywckomuewpcshldcg`) restaurado y conectado en `.env` (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `OMNINET_LICENSE_SECRET`). *(Solo falta pegar `SUPABASE_SERVICE_ROLE_KEY` en `.env` para escrituras privilegiadas).*

### B. Nivel de Autonomía sobre Windows (Zero NetLoss)
- [ ] **Opción B1 (Solo Observación / Seguro):** Mantener `dry_run=True` por defecto y aplicar optimizaciones solo cuando tú hagas clic en **Aplicar** o ejecutes `--apply`.
- [x] **Opción B2 (Auto-Reparación Activa):** Habilitado `OMNINET_ALLOW_LIVE_AUTOREPAIR=1` en `.env` y flag `--live-autorepair` en `main.py serve`/`tray` y `OmniNet.bat --admin`/`--tray`.

### C. Simplicidad y Experiencia de Uso (UX)
- [x] **Opción C1 (Ligera):** Lanzador 1-clic [`OmniNet.bat`](../OmniNet.bat) (`--admin`, `--tray`) implementado.
- [x] **Opción C2 (App de Escritorio):** System Tray [`netopt/tray.py`](../netopt/tray.py) + empaquetador PyInstaller [`scripts/build_exe.py`](../scripts/build_exe.py) implementados (`pystray`, `pillow`, `pyinstaller` instalados).
- [x] **Opción C3 (Minimalista CLI):** Comando rápido **`python main.py status`** (`--json`) implementado sin dependencias externas.

### D. Inteligencia Artificial del Asistente
- [ ] **Opción D1 (Privada y Gratis):** Instalar **Ollama** localmente (`ollama pull llama3.2` o `qwen2.5`).
- [x] **Opción D2 (Cloud Rápida):** Listo para activar pegando `DEEPSEEK_API_KEY` u `OPENAI_API_KEY` en `.env` (o desde `⚙️` en el Dashboard).
- [ ] **Opción D3 (Sin LLM):** Usar solo el motor determinista local (`Hermes Foresee` + diagnóstico guiado).

---

## 3. Instrucciones Rápidas para Hacerlo Más Operativo y Sencillo Hoy

### Paso 1: Arrancar y usar en 1 comando (sin complicarse)
```powershell
python main.py serve
```
Luego abre **`http://127.0.0.1:8877`** en tu navegador (o usa `python main.py` sin argumentos para que lo abra solo).

### Paso 2: Pasar de simulación (`dry-run`) a optimización real de red en Windows
Ejecuta una terminal **como Administrador** y corre:
```powershell
python main.py diagnose
python main.py optimize --apply
```
*(Si algo empeora en < 5s, OmniNet revierte automáticamente al snapshot previo; también puedes revertir manual con `python main.py rollback --list`).*

### Paso 3: Activar entorno de producción / nube (solo si eliges Opción A2)
te otorgo el privilegio y la autoridad para que lo hagas tu mismo
Crea un archivo `.env` en la raíz del proyecto (no se sube a Git) con:
```env
OMNINET_ENV=production
OMNINET_LICENSE_SECRET=<clave-aleatoria-larga-de-64-chars>
OMNINET_WEBHOOK_SECRET=<tu-secreto-webhook>
SUPABASE_URL=https://<tu-proyecto>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<tu-service-role-key>
SUPABASE_ANON_KEY=<tu-anon-key>
```

---

## 4. Todo lo que el Agente Necesita de Ti (Checklist Continuo)

Cuando el agente requiera intervención humana, consulta esta tabla:

| Categoría | Qué necesito de ti | Cuándo se necesita | Cómo entregarlo / confirmarlo |
| :--- | :--- | :--- | :--- |
| **Privilegios** | Ejecutar terminal como **Administrador** (aceptar UAC). | Al aplicar ajustes reales TCP/L4S/QoS/DNS o reparar servicios Windows (`--apply` / `--elevate`). | Confirmar UAC en Windows o lanzar `Start-Process powershell -Verb RunAs`. |
| **Confirmaciones** | Aprobar cambios de alcance o arquitectura (ej. elegir Opciones `A/B/C/D` arriba). | Antes de empaquetar `.exe`, cambiar puertos/rutas públicas o activar auto-reparación en vivo 24/7. | Marcar `[x]` en la Sección 2 o indicarlo en el chat. |
| **Comandos** | Ejecutar `python main.py serve` (o el futuro lanzador 1-clic) si reinicias el PC. | Tras reiniciar Windows si no está registrado como servicio/tarea programada. | Ejecutar en la carpeta del proyecto. |
| **Software** | Instalar herramientas opcionales: **SDIO** (drivers), **Ollama** (IA local), **BleachBit** / **Restic** / **PyInstaller**. | Si quieres usar actualización real de drivers, chat IA local sin costo o generar `.exe`. | Indicar *"instala/integra X"* o colocar binarios portables en `tools/`. |
| **Recursos / Claves** | Claves en `.env` (`SUPABASE_*`, `OMNINET_LICENSE_SECRET`, `DEEPSEEK_API_KEY` / `OPENAI_API_KEY`). | Solo si activas nube SaaS, licencias en producción o IA en la nube. | Guardar en `.env` local (nunca pegar secretos públicos en commits). |
| **Hardware (Opcional)** | Adaptador/Router **Wi-Fi 7 (6 GHz / MLO)** o router compatible con **L4S/SQM CAKE**. | Solo si deseas pruebas empíricas in situ de MLO/6 GHz o L4S real en tu red física. | Conectar el equipo al router/adaptador compatible. |

---

## 5. Continuidad del Proyecto
- Este documento complementa a [`AGENTS.md`](../AGENTS.md), [`README.md`](../README.md), [`.continuity/STATE.md`](../.continuity/STATE.md) y [`.continuity/TASK.md`](../.continuity/TASK.md).
- Cada vez que el usuario marque una alternativa o entregue un recurso de esta lista, el agente actualizará `.continuity/STATE.md` y `.continuity/TASK.md` para ejecutarlo de forma autónoma.
