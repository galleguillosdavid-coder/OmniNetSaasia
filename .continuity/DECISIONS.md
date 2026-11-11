# Decisiones vigentes

## DEC-001 — Arquitectura Híbrida Local-First con Invariante Zero NetLoss
- Estado: VIGENTE
- Fecha: 2026-10-15
- Decisión: Todo el procesamiento de red, optimizaciones de registro y mantenimientos de sub-agentes se ejecutan localmente en el dispositivo sin dependencia obligatoria de internet. Se exige respaldo previo (`snapshot`) antes de cualquier mutación del sistema.
- Motivo: Garantizar funcionamiento sin conexión, privacidad de datos y protección absoluta contra cortes de conectividad o desconfiguraciones.
- Alternativas descartadas: Configuración basada 100% en la nube o agentes que requieran conexión constante a internet.
- Componentes afectados: `netopt/optimizer.py`, `netopt/hal.py`, `subagents/`.
- Evidencia o referencia: [`tests/test_netopt_mock.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/tests/test_netopt_mock.py) (`test_zero_netloss_rollback_on_degradation`).

## DEC-002 — Separación Estricta de Cadencias Operativas
- Estado: VIGENTE
- Fecha: 2026-10-25
- Decisión: Separar claramente el ciclo del agente de IA (auto-mejora cada 40 minutos) del software creado OmniNet (centinela continuo y reactivo guiado por eventos y umbrales de telemetría).
- Motivo: Evitar acoplar la vigilancia del sistema al tiempo de contexto del LLM y mantener al agente enfocado en investigación tecnológica, optimización de código y expansión de capacidades.
- Alternativas descartadas: Que el software OmniNet espere al agente para aplicar correcciones automáticas urgentes.
- Componentes afectados: `AGENTS.md`, `docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md`, `main.py`.
- Evidencia o referencia: [`main.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/main.py) (`--sentinel`).

## DEC-003 — Protocolo de Comunicación Breve y Concisa hacia el Usuario
- Estado: VIGENTE
- Fecha: 2026-11-01
- Decisión: Todas las respuestas del agente al usuario deben ser directas y breves (máximo 3-5 viñetas o líneas cortas), reportando únicamente métricas exactas, acciones ejecutadas y estado de temporizadores.
- Motivo: Evitar sobrecarga cognitiva en el usuario y consumo innecesario de tokens de contexto.
- Alternativas descartadas: Reportes explicativos extensos por defecto en el chat.
- Componentes afectados: `AGENTS.md`, prompts del sistema.
- Evidencia o referencia: Directiva 1 de [`AGENTS.md`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/AGENTS.md).

## DEC-004 — Rol Inicial Supremo Obligatorio: Hermes Harness²
- Estado: VIGENTE
- Fecha: 2026-11-05
- Decisión: Toda IA que inicie sesión o acceda al proyecto debe asumir obligatoriamente el rol de Orquestador de Auto-Mejora (Hermes Harness²), verificando salud con tests al 100% e inspeccionando memoria antes de desplegar sub-agentes especializados.
- Motivo: Mantener disciplina arquitectónica, asegurar cero regresiones y evitar desorientación contextual.
- Alternativas descartadas: Asumir roles ad-hoc o improvisados según la pregunta del usuario.
- Componentes afectados: `README.md`, `AGENTS.md`, `hermes/`.
- Evidencia o referencia: [`tests/test_hermes_cognitive.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/tests/test_hermes_cognitive.py).

## DEC-005 — Telemetría Empírica In Situ, Colector Global de Métricas y Retroalimentación de IA
- Estado: VIGENTE
- Fecha: 2026-11-10
- Decisión: Implementar y ejecutar pruebas empíricas reales sobre el hardware del host (`netopt/telemetry.py`), conectar con el colector global anónimo de telemetría de dispositivos en el mundo (`/v1/telemetry/report`) y registrar anonimizadamente las conversaciones con el asistente de IA para alimentar la matriz de auto-mejora.
- Motivo: Eliminar alucinaciones basadas en mocks, recopilar telemetría de rendimiento a nivel global y auto-afinar los prompts y heurísticas del agente basándose en necesidades de usuarios reales.
- Alternativas descartadas: Depender exclusivamente de diagnósticos simulados o mocks.
- Componentes afectados: `netopt/telemetry.py`, `cloud_server/proxy_server.py`, `cloud_server/supabase_client.py`.
- Evidencia o referencia: [`tests/test_netopt_mock.py`](file:///c:/Users/Frondabrick/Desktop/dvd/Optimizador%20de%20redes/tests/test_netopt_mock.py) (`test_empirical_device_probes_and_global_telemetry_collector`).

