---
name: ecosystem-subagents-orchestrator
description: >-
  Use this skill to inspect, execute, or manage the 10 specialized open-source
  sub-agents of OmniNet (Redes, Antivirus, BleachBit, SDIO Drivers, LibreHardwareMonitor,
  Autoruns Startup, BCUninstaller, Anti-Telemetría ShutUp10, SFC/DISM Reparación, y Restic Backup).
---

# 🛡️ 10 Specialized Sub-Agents Orchestrator (OmniNet Ecosystem)

Coordinates 10 open-source and native OS engines to deliver comprehensive PC health, security, privacy, and connectivity maintenance.

## The 10 Sub-Agents Catalog

| ID | Emoji | Sub-Agente | Motor Open-Source / Nativo | Misión Principal |
| :--- | :---: | :--- | :--- | :--- |
| `network` | 🌐 | **Redes y Conexión** | `netopt` (DoH, L4S/ECN, Wi-Fi 7 MLO, DoQ, Ping, Bloat) | Cero cortes, ultra-baja latencia y máxima velocidad. |
| `antivirus` | 🛡️ | **Antivirus y Seguridad** | ClamAV + Microsoft Defender (`MpCmdRun.exe`) + YARA | Escaneo silencioso, protección en tiempo real y cuarentena. |
| `cleaner` | 🧹 | **Limpieza Profunda** | BleachBit (CleanerML con 2,000+ reglas) | Liberar gigabytes de basura sin borrar fotos ni contraseñas. |
| `drivers` | ⚡ | **Drivers al Día** | SDIO (Snappy Driver Installer Origin) | Detectar hardware antiguo y actualizar adaptadores y periféricos. |
| `hardware_thermal` | 🌡️ | **Hardware, Temp & Batería** | LibreHardwareMonitor / WMI / CIM / sysfs | Prevenir sobrecalentamiento y vigilar salud de la batería. |
| `startup_boost` | 🚀 | **Acelerador de Inicio** | Lógica de Autoruns (`Win32_StartupCommand` / psutil) | Desactivar programas rebeldes que ralentizan el encendido. |
| `uninstaller` | 🗑️ | **Desinstalador Limpio** | BCUninstaller (Bulk Crap Uninstaller) | Eliminar programas y borrar rastros ocultos en el registro. |
| `privacy_shield` | 🔒 | **Anti-Rastreo / Privacidad** | O&O ShutUp10 rules / StevenBlack Hosts | Bloquear telemetría intrusiva de Windows y anuncios. |
| `os_repair` | 🩺 | **Salud y Reparación OS** | DISM (`/CheckHealth`) + SFC (`/scannow`) + chkdsk | Reparar archivos protegidos corruptos de Windows/Linux. |
| `backup` | 💾 | **Respaldo Inteligente** | Restic / Duplicati / Smart Snapshot Zip | Proteger configuraciones y documentos ante ransomware o fallas. |

---

## Modos de Ejecución

### 1. Ejecución vía Python Directo
```powershell
# Obtener catálogo de los 10 sub-agentes con estados
python -c "from netopt.ecosystem_subagents import get_ecosystem_orchestrator; import json; print(json.dumps(get_ecosystem_orchestrator().get_all_subagents_status(), indent=2, ensure_ascii=False))"

# Ejecutar un sub-agente específico (ej. 'antivirus', 'cleaner', 'privacy_shield')
python -c "from netopt.ecosystem_subagents import get_ecosystem_orchestrator; import json; print(json.dumps(get_ecosystem_orchestrator().execute_subagent_by_id('cleaner', execute=True), indent=2, ensure_ascii=False))"
```

### 2. Ejecución vía API REST (`http://127.0.0.1:8877`)
- **Listar estados**: `GET /api/subagents`
- **Ejecutar sub-agente**: `POST /api/subagents/run` con JSON `{"id": "antivirus", "execute": true}`

### 3. Ejecución Conversacional (Lenguaje 100% Simple)
En el chat del Dashboard o mediante `LLMGateway`:
- *"Revisa si tengo virus"* ➔ Activa `subagent_antivirus`.
- *"Qué temperatura tiene mi procesador"* ➔ Activa `subagent_hardware_thermal`.
- *"Acelera el arranque de mi PC"* ➔ Activa `subagent_startup_boost`.
- *"Activa el anti-rastreo y privacidad"* ➔ Activa `subagent_privacy_shield`.
- *"Limpia la basura y repara mi computador"* ➔ Ejecuta BleachBit + SDIO + DISM.
