# Estado Actual del Proyecto (`PROJECT_STATE.md`)
*Documento vivo de sincronización epistemológica y control de estado de OmniNet.*

**Última actualización:** 2026-11-11 09:25 UTC-3  
**Estado General:** SALUDABLE (`HEALTHY`)  
**Suite de Tests:** 170/170 tests aprobados (100% OK, 0 fallos)  
**Nivel de Calibración:** VERIFICADO (Evidencia directa de ejecución y pruebas)  

---

## 1. Objetivo y Alcance
OmniNet es una plataforma SaaS autónoma de optimización y mantenimiento profundo de sistemas y redes multi-OS (Windows, Linux, macOS), con 10 subsistemas especializados, arquitectura Micro Internet descentralizada (DID, Transportes Multipath, Federación de Gateways) y arnés de auto-evolución Hermes.

---

## 2. Arquitectura y Componentes Principales
- **`netopt/`**: Núcleo de red (HAL, Diagnóstico L1-L7, Optimizador TCP/DNS, Triage y Rollback Zero NetLoss).
- **`netopt/maintenance/`**: 10 subsistemas de ecosistema de mantenimiento (Antivirus, BleachBit, SDIO Drivers, LibreHardwareMonitor, Autoruns, BCUninstaller, O&O ShutUp10, DISM/SFC, Restic Backup).
- **`netopt/micro_internet/`**: 5 pilares de Micro Internet (DID, Identity Resolver, Multipath Transport, Gateway Federation, Cooperative Network).
- **`hermes/`**: Arnés de ejecución segura (`harness.py`), Orquestador (`orchestrator.py`), Motor de Auto-Mejora (`self_improvement.py`) y bucle cognitivo Plan→Ejecutar→Reflexionar (`foresee.py`, `executor.py`, `reflect.py`, `cognitive_loop.py`) bajo estrictos protocolos anti-alucinación (SIMULATED honesto, Zero NetLoss snapshot/rollback y persistencia de estrategias verificadas).
- **`cloud_server/`**: Proxy SaaS con integración Supabase PostgREST, pasarelas Lemon Squeezy / Stripe y control de cuotas con deducción post-éxito verificada.
- **`mcp_server.py`**: Servidor MCP con 15 herramientas estandarizadas en paridad total con `config/tools_manifest.json`.
- **`.agents/skills/`**: Habilidades operativas del agente (`autonomous-net-scheduler`, `deep-network-diagnostics`, `tcp-dns-quic-optimizer`, `ecosystem-subagents-orchestrator`, `hallucination-control`).
- **`memory/`**: Memoria cognitiva persistente (`ERROR_PATTERNS.md`, `SUCCESS_PATTERNS.md`, `COGNITIVE_PARADIGMS.md`, `DECISIONS.md`).

---

## 3. Matriz de Capacidades y Estado

| Capacidad | Estado | Evidencia / Pruebas |
|---|---|---|
| Diagnóstico de red L1-L7 (Bufferbloat, Jitter RFC 3550, MTU) | `VERIFICADO` | `test_doh_nic_and_wifi_telemetry`, `test_discover_pmtu` |
| Afinamiento TCP (BBR2, autotuninglevel=normal, ECN) | `VERIFICADO` | `test_windows_hal_methods_dry_run`, `test_optimizer_plan_generation` |
| Rollback Snapshot Reversible (Zero NetLoss) | `VERIFICADO` | `test_rollback_manager_snapshot`, `test_t13_rollback_verification_gate` |
| 10 Subsistemas de Mantenimiento de Sistema | `VERIFICADO` | `test_10_specialized_ecosystem_subagents`, `test_multi_os_device_maintenance_engine` |
| Micro Internet (5 Pilares: DID, Resolver, Multipath, Federation, Colab) | `VERIFICADO` | `test_pillar_1` a `test_pillar_5`, `test_micro_internet_orchestrator` |
| Multipath QUIC (`draft-ietf-quic-multipath` / Deadline-Aware) | `VERIFICADO` | `test_pillar_3_multipath_transport` (67/67 OK) |
| Arnés y Orquestador Hermes (Sandbox, Paralelo, Auto-Mejora) | `VERIFICADO` | `test_hermes.py` (8/8 tests OK) |
| Bucle Cognitivo Hermes Foresee → Executor → Reflect (re-planificación con aprendizaje) | `VERIFICADO` | `test_hermes_cognitive.py` (4/4 OK) + smoke run real dry-run (`SIMULATED`) |
| Supabase SaaS PostgREST (Licencias, Cuotas, Hardware IDs) | `VERIFICADO` | Conexión en vivo a `zptywckomuewpcshldcg.supabase.co` y `test_global_saas_licensing_and_quota` |
| Mitigación de Vulnerabilidades de Auditoría (OMNI-001 a OMNI-023) | `VERIFICADO` | `test_audit_executive_remediation.py` (22/22 tests OK) |
| Prevención de Alucinaciones y Memoria Persistente (`hallucination-control`) | `VERIFICADO` | Skill en `.agents/skills/hallucination-control/` y estructura `memory/` inicializada |
| Ventana TCP Dinámica y Saturación BDP (RFC 7323) | `VERIFICADO` | `check_tcp_window_scale_bdp_status` (Autotuning normal hasta 1GB) |
| Mitigación Bufferbloat Socket TCP_NOTSENT_LOWAT (RFC 8033/8985) | `VERIFICADO` | `check_tcp_notsent_lowat_stream_bufferbloat_status` (16KB watermark) |
| Control de Congestión Persistente QUIC (RFC 9002) | `VERIFICADO` | `check_quic_persistent_congestion_rfc9002_status` (3x PTO floor 2400B) |
| Capacidad Física Wi-Fi 7 4096-QAM y 320 MHz (802.11be) | `VERIFICADO` | `check_wifi7_4k_qam_320mhz_phy_capacity` (5.76 Gbps / SNR >= 38 dB) |
| Eficiencia Espectral Wi-Fi 7 Multi-RU OFDMA (802.11be) | `VERIFICADO` | `check_wifi7_multi_ru_puncturing_efficiency` (300 MHz / 93.75% espectro) |
| TCP CUBIC (RFC 9438) & Temporizadores RTO Seguros (RFC 8961) | `VERIFICADO` | `check_rfc9438_cubic_and_rfc8961_timer_status` (RTO_MAX >= 60s / Concave-Convex) |
| Arquitectura L4S y Control de Congestión Prague (RFC 9330/9331) | `VERIFICADO` | `check_rfc9330_l4s_prague_architecture_status` (ECT1 / DualPI2 / Sub-ms) |
| HTTP Datagrams & Capsule Protocol (RFC 9297) | `VERIFICADO` | `check_rfc9297_http_datagrams_capsule_protocol_status` (WebTransport/MASQUE) |
| QUIC Multiplexing Demux (RFC 9443) & SCTP Multihoming (RFC 9260) | `VERIFICADO` | `check_rfc9443_quic_multiplexing_and_rfc9260_sctp_status` (HoL prevention / CRC32c) |
| Priorización Extensible HTTP/2 y HTTP/3 (RFC 9218) | `VERIFICADO` | `check_rfc9218_http_extensible_prioritization_status` (Urgencia u=0..7 / Concurrencia i) |
| MASQUE Proxying Suite: CONNECT-UDP (RFC 9298) & CONNECT-IP (RFC 9484) | `VERIFICADO` | `check_rfc9298_connect_udp_and_rfc9484_connect_ip_masque_status` (Cápsulas H3 / Túneles VPN Zero-Trust L3/L4) |
| BBRv3 Congestion (Google Draft) & Oblivious HTTP (RFC 9458) | `VERIFICADO` | `check_bbrv3_congestion_and_rfc9458_ohttp_status` (ECN feedback / HPKE Trust-Split) |
| SFrame WebRTC Media E2EE (RFC 9605) & QUIC Key Update (RFC 9001 §6) | `VERIFICADO` | `check_rfc9605_sframe_and_rfc9001_quic_key_update_status` (SFU Blind Forwarding / Key Phase bit toggle) |
| HTTPS/SVCB DNS (RFC 9460) & Delegated Credentials (RFC 9345) | `VERIFICADO` | `check_rfc9460_svcb_https_and_rfc9345_delegated_credentials_status` (0-RTT H3/ECH Discovery / Edge Short-Lived Keys) |
| HTTP/3 (RFC 9114), QPACK (RFC 9204) & TCP Fast Open (RFC 7413) | `VERIFICADO` | `check_rfc9114_http3_qpack_and_rfc7413_tfo_status` (HoL Header Elimination / 0-RTT SYN TFO Cookies) |
| TLS 1.3 Anti-Replay (RFC 8446 App. E) & Modern TCP (RFC 9293) | `VERIFICADO` | `check_rfc8446_tls13_antireplay_and_rfc9293_tcp_status` (Single-Use Tickets / Cryptographic ISN) |
| WebTransport Priority (RFC 9218 Framework) & Building Protocols with HTTP (RFC 9205 / BCP 56) | `VERIFICADO` | `check_webtransport_prioritization_and_rfc9205_bcp56_status` (Urgency u=0..7 / BCP 56 Idempotency) |
| Telemetría Empírica In Situ & Colector Global de Métricas/Conversaciones | `VERIFICADO` | `test_empirical_device_probes_and_global_telemetry_collector` (`netopt/telemetry.py` y proxy `/v1/telemetry/report`) |
| DTLS 1.3 (RFC 9147) & Migración de Conexión QUIC (RFC 9000 §9) | `VERIFICADO` | `test_rfc9147_dtls13_and_rfc9000_connection_migration_status` (CID activo, 0-RTT Roaming Wi-Fi <-> Celular) |
| Problem Details HTTP APIs (RFC 9457) & JavaScript Media Types (RFC 9239) | `VERIFICADO` | `check_rfc9457_problem_details_and_rfc9239_mimetype_status` (application/problem+json / text/javascript canónico) |
| QUIC Applicability (RFC 9308) & Zero-Trust Network Routing | `VERIFICADO` | `check_rfc9308_quic_applicability_and_ztna_routing_status` (UDP Fallback / DPI Transport Metadata Shielding) |
| HTTP/2 Modern Framing (RFC 9113) & SCTP Multihoming (RFC 9260) | `VERIFICADO` | `check_rfc9113_http2_and_rfc9260_sctp_multistreaming_status` (RST_STREAM DoS Mitigation / CRC32c Independent Streams) |
| HTTP Datagrams (RFC 9297) & QUIC Congestion Governance (RFC 9002) | `VERIFICADO` | `check_rfc9297_datagrams_and_rfc9002_congestion_status` (Unreliable Datagrams / cwnd & PTO Governance) |
| QPACK Static Table Indexing (RFC 9204) & HTTP Caching (RFC 9110/9111) | `VERIFICADO` | `check_rfc9204_qpack_static_table_and_rfc9110_caching_status` (99 Static Entries / Zero HoL Blocking Cache-Control) |
| HTTP/3 GOAWAY (RFC 9114 §5.2) & TFO Cookie Renewal (RFC 7413) | `VERIFICADO` | `check_rfc9114_goaway_and_rfc7413_cookie_renewal_status` (Graceful In-Flight Stream Drain / Zero Fallback Degradation) |
| QUIC ALPN Tokens (RFC 9308 §3.1) & DATAGRAM Extension (RFC 9221) | `VERIFICADO` | `check_rfc9308_alpn_and_rfc9221_quic_datagram_status` (0x30/0x31 Frames / Cross-Protocol Attack Mitigation) |
| MASQUE Fast-Path (RFC 9298 CONNECT-UDP & RFC 9484 CONNECT-IP) | `VERIFICADO` | `check_masque_connect_udp_and_connect_ip_deep_status` (L3/L4 Tunneling over 443 / Dual-Hop Privacy Architecture) |
| QUIC Demux (RFC 9443) & QUIC Version 2 (RFC 9369) | `VERIFICADO` | `check_rfc9443_multiplexing_and_rfc9369_quic_v2_status` (Shared Port Demux / Wire Image Anti-Ossification) |
| SCTP Path Heartbeat (RFC 9260 §8) & Capsule Protocol (RFC 9297 §3) | `VERIFICADO` | `check_sctp_path_heartbeat_and_rfc9297_capsule_status` (Multi-homing Failover / TLV Datagram Stream Encapsulation) |
| BCP 56 Substrate (RFC 9205) & H3 Stream Mapping (RFC 9114 §4) | `VERIFICADO` | `check_rfc9205_substrate_and_rfc9114_stream_mapping_status` (Unidirectional Stream Typing / Credit-Based Flow Control) |
| QPACK Dynamic Table Sync (RFC 9204 §4) & PRIORITY_UPDATE (RFC 9218) | `VERIFICADO` | `check_rfc9204_dynamic_sync_and_rfc9218_priority_update_status` (Section Ack & Stream Cancel / In-Flight Reprioritization) |
| Server Push Deprecation (RFC 9114 §7 / RFC 8297) & TFO Reflection Defense (RFC 7413) | `VERIFICADO` | `check_rfc9114_server_push_and_rfc9208_tfo_security_status` (Early Hints 103 / Prevención Reflexión Amplificada TFO) |
| Códigos de Error H3 (RFC 9114 §8) & MASQUE Capsules (RFC 9298) | `VERIFICADO` | `check_rfc9114_error_codes_and_rfc9298_masque_capsule_status` (Registro 0x0100..0x0110 / Reintentos Seguros H3_REQUEST_REJECTED / Túneles UDP) |
| Push ID Prioritization (RFC 9218/9220) & QUIC Socket Pacing | `VERIFICADO` | `check_rfc9220_push_priority_and_quic_socket_buffer_status` (Tramas 0xF0700/0xF0701 / Urgencia u=0..7 / Anti-Bufferbloat Pacing) |
| QPACK Decoder Stream (RFC 9204 §5) & CONNECT-IP PMTU/ICMP (RFC 9484 §10.1) | `VERIFICADO` | `check_rfc9204_decoder_stream_and_rfc9484_connect_ip_fragmentation_status` (Section Ack / Stream Cancel / ICMP Packet Too Big Anti-Blackhole) |
| Oblivious HTTP (RFC 9458) & Binary HTTP (RFC 9292) | `VERIFICADO` | `check_rfc9458_ohttp_hpke_and_rfc9292_bhttp_status` (Separación Relay/Gateway / Encapsulación HPKE RFC 9180 / Cargas message/bhttp) |
| ECH HTTPS DNS Bootstrapping (RFC 9460/9848) & Short-Lived Certs (RFC 9345) | `VERIFICADO` | `check_rfc9460_ech_https_dns_and_short_lived_certs_status` (SvcParamKey ech 0x0005 / Segregación Outer/Inner SNI / Certificados Efímeros) |
| Modern TCP Specification (RFC 9293) & Challenge ACK RST Mitigation | `VERIFICADO` | `check_rfc9293_tcp_state_machine_and_rst_challenge_ack_status` (Máquina de 11 estados / Blind RST RFC 5961 / 2*MSL TIME-WAIT) |
| Congestión BCP 133 (RFC 9743) & QUIC Bit Greasing (RFC 9287) | `VERIFICADO` | `check_rfc9743_congestion_bcp133_and_rfc9287_quic_grease_status` (Obsoleta RFC 5033 / Convivencia CUBIC-Reno / Parámetro 0x2ab2 Anti-Osificación) |
| Capa de Continuidad Externa MVP (`.continuity/`) | `VERIFICADO` | Estructura `.continuity/` (`PROJECT.md`, `STATE.md`, `DECISIONS.md`, `TASK.md`, `HISTORY.md`, `evidence/`) |

---

## 4. Decisiones Técnicas Vigentes
- **DEC-001:** Doble cadencia operativa (OmniNet continuo en background vs Agente cada 40 min).
- **DEC-002:** Sincronización continua de Git en remotes duales (`origin` y `upstream-operador`).
- **DEC-003:** Arnés Hermes con compuerta de cero regresiones estricta.
- **DEC-004:** Bucle Cognitivo Hermes Foresee → Executor → Reflect con aprendizaje determinista anti-alucinaciones.
- **DEC-005:** Telemetría Empírica In Situ obligatoria en el dispositivo físico anfitrión y Colectores Globales de Métricas de Rendimiento (`/v1/telemetry/report` & Supabase `devices_telemetry_metrics`) y Conversaciones de IA (`cloud_global_feedback.json` & Supabase `conversations_feedback`).
- **DEC-006:** Implantación de la Capa de Continuidad Externa MVP (`.continuity/`) como ancla persistente e independiente del contexto interno del modelo.

---

## 5. Pruebas Ejecutadas y Resultados
- **Comando:** `python -m unittest discover -s tests -v`
- **Resultado:** `Ran 170 tests -> OK` (100% aprobados, 0 fallos, 0 errores).

---

## 6. Última Tarea Realizada
- Ciclo 61: Migración completa de endpoints REST hacia FastAPI/Uvicorn (`netopt/fastapi_app.py` y `main.py`) con validación tipada estricta Pydantic v2 y nueva suite de 8 pruebas en `tests/test_fastapi_app.py`, elevando la suite general a 170 tests aprobados al 100%.

---

## 7. Próxima Tarea Concreta
- Ciclo 62: Preparación de esquema de firmas asimétricas Ed25519 con fallback dual retrocompatible.


