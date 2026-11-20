---
trigger: always_on
---

# OmniNet Antigravity Workspace Rules (`omninet-cycles`)

- **Arquitectura de Ciclos y Sub-Ciclos (`AGENTS.md §2A`)**:
  - *Periódicos (Regla Anti-Relleno y Diseño Ameno)*: Ciclo Macro cada 40m (`schedule` `DurationSeconds=2400`) con rotación multimódulo (`netopt/`, `hermes/`, `cloud_server/`, `config/`+`main.py`+`mcp_server.py`, `tests/`, `docs/`+`.continuity/`). **Cada ciclo debe entregar al menos 1 mejora concreta de producto/código/seguridad/UX/diseño + su test de regresión** (fricciones de `conversation_feedback.json`, deuda de `docs/Auditorias/3.md`, RFC/AI Defense aplicable y **refinamiento continuo del diseño visual/UI/Matrix para hacerlo más ameno**), nunca solo tests pasivos + búsqueda web. Sub-Ciclo de Vigilancia Antigravity cada 3er ciclo o diario.
  - *Por Necesidad*: Contención inmediata ante fallo de tests, degradación física (`bufferbloat_grade >= C`, pérdida > 0%, anomalía ARP) o error de arranque; Auditoría de Seguridad/Persistencia al tocar HTTP, Pydantic, HMAC/Ed25519, locks o `execute is True`.
  - *Ocasionales*: Suite completa (`python -m unittest discover -s tests -v`), `git diff --check`, armonización `.continuity/` y migración progresiva a bibliotecas maduras (`docs/Auditorias/3.md`).
  - *Por Voluntad*: Investigación web RFC/Kernel (L4S, DoQ/DoH3, ECH, PQC, Wi-Fi 7 MLO, eBPF/NetAdapterCx) e implementación de alto impacto.
- **Invariante Zero NetLoss**: Ninguna mutación del sistema operativo sin `execute is True` explícito, snapshot previo y auto-rollback ante pérdida de conectividad.
- **Verificación Empírica Real**: Ejecutar `run_real_device_empirical_probes()` de `netopt/telemetry.py` en cada ciclo y mantener respuestas breves (3-5 viñetas).
