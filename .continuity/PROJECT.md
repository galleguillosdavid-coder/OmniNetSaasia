# OmniNet — Proyecto e Invariantes Globales

## 1. Propósito y Límites
OmniNet es un optimizador integral de redes y mantenimiento autónomo del sistema operativo para Windows (con soporte complementario Linux). Proporciona optimización L1-L7 del stack TCP/IP/DNS/QUIC, centinela autónomo de 10 subsistemas y arquitectura local-first respaldada por proxy en la nube y base de datos Supabase.

- **Documento canónico de arquitectura:** [`README.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/README.md)
- **Manifiesto operacional:** [`docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md)
- **Directivas del agente:** [`AGENTS.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/AGENTS.md)

## 2. Módulos Principales
- `netopt/`: Núcleo de optimización de red, telemetría empírica in situ, diagnósticos RFC, HAL de Windows/Linux y centinela continuo.
- `subagents/`: 10 subsistemas de mantenimiento del dispositivo (Redes, Antivirus, BleachBit, SDIO Drivers, LibreHardwareMonitor, Autoruns, BCUninstaller, ShutUp10, SFC/DISM, Restic).
- `cloud_server/`: Servidor proxy HTTP y cliente Supabase para licencias SaaS, colector global de métricas y colector de conversaciones.
- `hermes/`: Arnés cognitivo tripartito (`foresee.py`, `executor.py`, `reflect.py`, `cognitive_loop.py`).
- `tests/`: Suite de pruebas unitarias, de integración y anti-alucinación.

## 3. Invariantes Globales Inviolables
1. **Zero NetLoss:** Ninguna optimización o acción de mantenimiento puede degradar la conectividad, estabilidad o rendimiento del sistema anfitrión. Todo cambio debe tener snapshot de respaldo y capacidad de rollback inmediato.
2. **Cero Regresiones (100% Tests Unitarios Aprobados):** Ninguna tarea se considera completa si la suite de pruebas unitarias (`python -m unittest discover -s tests -v`) no aprueba al 100%.
3. **Rol Inicial Supremo Obligatorio (`Hermes Harness²`):** Todo agente IA que acceda al proyecto asume como tarea inicial obligatoria el rol de Orquestador de Auto-Mejora y despliega mediante sub-agentes los roles especializados.
4. **Verificación Empírica In Situ:** La IA no puede asumir estados basándose en suposiciones. Debe contrastar diagnósticos con pruebas reales sobre el hardware del equipo anfitrión.
5. **Comunicación Breve y Concisa:** Respuestas al usuario directas, de máximo 3 a 5 viñetas o líneas cortas.

