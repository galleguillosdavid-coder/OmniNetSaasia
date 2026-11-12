# Estado comprobado

Última actualización: 2026-11-11T15:25:00-03:00
Commit validado: Ciclo 62 validado en suite de 172 tests

## Funciona y tiene evidencia
- Mandato de Auto-Propuesta y Ejecución de Tareas Propias: Documentado en `AGENTS.md`, `docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md` y `README.md`. El agente no se limita a inspeccionar el computador; evalúa proactivamente el repositorio y propone/ejecuta tareas técnicas según la ocasión lo requiera.
- Suite de pruebas unitarias — 172/172 tests aprobados al 100%
- Migración REST API hacia FastAPI y Uvicorn (`netopt/fastapi_app.py` y `main.py`) — Implementación modular con OpenAPI automático, middleware de cuotas/tamaño (413), control de acceso loopback (403), validación tipada estricta Pydantic v2 en todas las rutas y 8 tests dedicados en `tests/test_fastapi_app.py`
- Validación Pydantic v2 en Servidor Proxy Cloud (`cloud_server/proxy_server.py`) — Validación tipada estricta para `/v1/license/activate`, `/v1/chat` (`CloudChatRequest`), y `/v1/telemetry/report` (`TelemetryReport`) con 10 tests dedicados en `tests/test_pydantic_schemas.py`
- Arnés Hermes y Bucle Cognitivo (`hermes/foresee.py` y `hermes/executor.py`) — Integración de la herramienta y estrategia `resource_audit` conectada a `SystemResourceAdapter` (`psutil`) para evaluar presión de CPU/memoria y saturación de sockets de red (5 tests en `tests/test_hermes_cognitive.py`)
- Adaptadores de Bibliotecas Maduras (`netopt/adapters.py`) — `SystemResourceAdapter` (`psutil`: CPU, RAM, packet drops en NICs y procesos top consumidores de sockets de red) y `HttpClientAdapter` (`httpx`: pooling y comunicación HTTP resiliente) integrados en `netopt/llm_gateway.py`, `cloud_server/proxy_server.py` y `netopt/licensing.py` (activación cloud con fallback)
- Modelos Pydantic v2 (`netopt/schemas.py`) — Validación tipada de entradas para `DeviceIdentity`, `HealthResponse`, `SubagentRequest`, `OptimizeRequest`, `ChatRequest`, `CloudChatRequest`, `RollbackRequest`, `RepairRequest`, `SentinelToggleRequest`, `LicenseActivationRequest` y `TelemetryReport`
- Mandato de Adopción de Bibliotecas Maduras (`docs/MIGRACION_BIBLIOTECAS.md`) — Fases de FastAPI, Pydantic, psutil, httpx y uvicorn implementadas al 100% con cero regresiones y contratos de rutas preservados
- Servidor Web UI y API local — Escuchando activamente en `http://127.0.0.1:8877/` bajo FastAPI/Uvicorn (`task-2630`, HTTP 200 OK verificado)
- Seguridad AutoSentinel (OMNI-038) — Nace inactivo (`enabled=False`), HAL forzado a `dry_run=True` por defecto, reparaciones en vivo protegidas por `OMNINET_ALLOW_LIVE_AUTOREPAIR` y arranque automático eliminado de `start_api_server()`
- Política Fail-Closed en Secretos (OMNI-039A) — `get_signing_secret()` en `netopt/licensing.py` no tiene secreto hardcodeado; en producción sin `OMNINET_LICENSE_SECRET` bloquea emisión y verificación, y en desarrollo emite alerta explícita
- Servidor Web UI y API local — Escuchando activamente en `http://127.0.0.1:8877/` (HTTP 200 OK verificado)
- Telemetría empírica in situ del host — Verificada en hardware real (`netopt/telemetry.py`: ping 29.81 ms, jitter 0.37 ms, packet loss 0%)
- Colector global de métricas de dispositivos — Endpoint `/v1/telemetry/report` en `cloud_server/proxy_server.py` comprobado
- Colector de conversaciones y retroalimentación de IA — Almacenamiento local y cloud comprobado
- Telemetría RFC 9743 (BCP 133 Congestion Guidelines) y RFC 9287 (Greasing the QUIC Bit 0x2ab2) — Comprobadas en `check_rfc9743_congestion_bcp133_and_rfc9287_quic_grease_status()`
- Diagnóstico RFC 9293 (Transmission Control Protocol) — Máquina de estados canónica de 11 fases, mitigación RFC 5961 blind RST mediante Challenge ACKs, drenaje 2*MSL TIME-WAIT y protección anti-assassination
- Telemetría RFC 9460 §7 / RFC 9848 (ECH vía DNS HTTPS con SvcParamKey 0x0005) y Certificados Efímeros (RFC 9345) — Comprobadas en `check_rfc9460_ech_https_dns_and_short_lived_certs_status()`
- Diagnósticos RFC avanzados (RFC 9458 §3 OHTTP Keys, RFC 9525 TLS Service Identity, RFC 9220 WebSockets H3, RFC 9204 §5 QPACK Decoder Stream, RFC 9484 CONNECT-IP, RFC 9114 §7 Push Deprecation, RFC 8297 Early Hints, RFC 9205 BCP 56, RFC 9114 §4 H3 Streams, RFC 9457 Problem Details, RFC 9147 DTLS 1.3 CID, RFC 9000 QUIC Migration, RFC 9438 CUBIC, RFC 9330 L4S, RFC 9297/9298/9484 MASQUE, BBRv3, CAKE DiffServ4, RFC 9605 SFrame, RFC 9460 SVCB/HTTPS) — Cobertura y aserciones verificadas
- Centinela autónomo de 10 subsistemas y planificador continuo — Operativo en segundo plano

## Implementado, pero no verificado
- Integración en producción con Supabase real — Requiere credenciales de entorno del usuario (opera correctamente en modo local-first con fallback a JSON)

## Incompleto
- Ningún componente crítico incompleto en el alcance actual

## Deuda y riesgos conocidos
- Dependencia de elevación de privilegios (Administrador) en Windows para modificar configuración TCP global y claves de registro HKLM
- Mitigación: HAL opera en modo seguro con respaldo y opción dry-run cuando no se cuenta con elevación

## Próximo paso recomendado
- Continuar la vigilancia e investigación de nuevas especificaciones y mantener activo el ciclo de auto-mejora de 40 min
