# Changelog - OmniNet AI Agent Pro

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - 2026-11-04

### Added
- **Auto-Elevation de privilegios en arranque** (`netopt/elevation.py`):
  - Windows: dispara UAC automáticamente via `ShellExecuteW` con verbo `runas`. El proceso no elevado se cierra y el nuevo proceso elevado toma el control.
  - Linux / macOS: re-ejecuta con `sudo` via `os.execvp` (reemplaza el proceso, sin zombies). Fallback a `pkexec` si `sudo` no está disponible.
  - PyInstaller EXE: lógica idéntica — el ejecutable standalone se auto-eleva.
- **Flag `--no-elevate`**: consumido antes de que argparse lo vea; permite saltarse la elevación en modo MCP stdio o cuando el launcher ya elevó.
- **Launcher `OmniNet.bat` actualizado**: comprueba `net session` y relanza con `Start-Process -Verb RunAs` si no tiene admin.
- **Launcher `run.sh` actualizado**: comprueba `$EUID` y relanza con `sudo bash "$0"` si no es root.
- **Endpoint `/api/status`**: retorna `admin_elevated`, `elevation_status`, `sentinel_active`, `version`, `platform`, `port`.
- **Badge de privilegios en UI**: el header del dashboard muestra `[Admin/root ACTIVO]` (verde) o `[Sin Admin]` (rojo), actualizado via `loadSystemStatus()` al cargar la página.

### Changed
- `main.py` VERSION bump: `1.0.0` → `1.2.0`
- `from __future__ import annotations` movido al tope correcto (antes del bloque de elevación).

---

## [1.1.0] - 2026-11-04

### Added
- Real tool execution antes del LLM call en `llm_gateway.py` — el agente tiene datos reales, no simulados.
- Backend trace visible en chat como bloque `<details>` colapsable.
- Protección anti-wipe de API key: gateway preserva la key existente si nueva config llega vacía.
- Intent routing contextual: palabras clave Y selección numérica ("1", "si", "aplicar").
- Sentinel auto-start al arrancar el servidor.
- UI de 3 pestañas: Chat, Informes, Telemetría.

---

## [1.0.0] - 2026-11-04

### Added
- **Model-Agnostic AI Architecture**: Compatible con Claude, GPT-4, Gemini, Llama 3, DeepSeek, y LLMs locales.
- **Cross-Platform HAL**: Abstracción para Windows (`netsh`/PowerShell), Linux (`sysctl`/`iproute2`/`nmcli`), macOS (`networksetup`/`scutil`), y BSD.
- **Zero NetLoss Safety Engine**: Snapshots, gates de verificación y rollback determinista en < 5 segundos.
- **Non-Destructive Telemetry**: Latencia, jitter RFC 3550, pérdida de paquetes, Path MTU, bufferbloat.
- **DNS Resolver Benchmark**: Cloudflare, Google, Quad9, OpenDNS, ISP local.
- **Hierarchical Auto-Repair**: Cobertura L1→L7 OSI.
- **Persistent Sentinel Daemon**: Watcher 24/7 con SLA compliance y auto-healing.
- **MCP Server**: JSON-RPC 2.0 stdio para integración con IDEs y agentes.
- **REST API**: 12+ endpoints, Zero-dep HTTP server embebido.
- **Standalone EXE**: PyInstaller bundle para Windows x64 (Python embebido).


### Added
- **Model-Agnostic AI Architecture**: Native instructions and tool calling specifications compatible with Claude, GPT-4, Gemini, Llama 3, DeepSeek, and local LLMs.
- **Cross-Platform HAL**: Hardware & Operating System Abstraction Layer with full driver support for Windows (`netsh`/PowerShell), Linux (`sysctl`/`iproute2`/`nmcli`), macOS (`networksetup`/`scutil`), and BSD.
- **Zero NetLoss Safety Engine**: Pre-action configuration snapshots, automated verification gates, and deterministic sub-5-second rollbacks upon degradation.
- **Non-Destructive Telemetry**: Fast socket probes for latency, RFC 3550 jitter, packet loss percentage, Path MTU discovery, and bufferbloat grading (A+ to F).
- **DNS Resolver Benchmark**: Concurrent benchmarking for Cloudflare, Google, Quad9, OpenDNS, and local ISP resolvers.
- **Hierarchical Auto-Repair (Triage)**: Multi-layer healing covering physical adapter (L1), DHCP/gateway (L2/L3), routing/MTU (L3), DNS (L4), and TCP sockets (L4/L7).
- **Persistent Sentinel Daemon**: Background watcher with SLA compliance tracking, configuration drift defense, and auto-healing capabilities.
- **Model Context Protocol (MCP) Server**: JSON-RPC 2.0 stdio server for plug-and-play AI IDE and agent integration.
- **Embedded REST API & Web UI**: Zero-dependency HTTP server on port 8877 exposing `/api/diagnose`, `/api/optimize`, `/api/repair`, and `/api/rollback`.
- **Standalone Distribution**: PyInstaller single-file binary builder (`OmniNet.exe`) bundling the entire Python runtime so it runs anywhere without prerequisites.
- **Universal Launchers**: `OmniNet.bat` for Windows and `run.sh` for Linux/macOS.

