# Plan y Estado de Migración de Bibliotecas Maduras
**Repositorio:** `galleguillosdavid-coder/OmniNetSaasia`  
**Directiva:** Mandato Maestro de Reemplazo por Bibliotecas Probadas (`docs/Auditorias/3.md`)  
**Fecha:** 2026-11-10

---

## 1. Componentes Eliminados (Código Artesanal Redundante)
- **Secreto HMAC hardcodeado por defecto:** Eliminado en `netopt/licensing.py`.
- **Wildcard CORS `*` indiscriminado:** Eliminado en `cloud_server/proxy_server.py`.
- **Arranque no supervisado de AutoSentinel:** Eliminado en `main.py` (`start_api_server()`).
- **Afirmación errónea de pruebas históricas (93):** Eliminada en `README.md`.

---

## 2. Componentes Sustituidos Progresivamente
- **Gestión de Secretos:** Sustituido por `get_signing_secret()` con política estricta Fail-Closed y advertencia runtime en `DEV_MODE`.
- **CORS de Servidor Proxy:** Sustituido por resolución dinámica contra lista de orígenes permitidos (`ALLOWED_ORIGINS`).

---

## 3. Componentes Conservados como Lógica Diferencial Propia
- **Diagnóstico L1-L7 Especializado:** Evaluaciones de RFC 9293 (TCP State Machine), RFC 9330 (L4S/Prague), RFC 9460 (SVCB/HTTPS), RFC 9458 (OHTTP Keys), etc.
- **Rollback Manager Zero NetLoss:** Captura de snapshot previa a modificaciones de configuración del sistema operativo y verificación de reversibilidad.
- **Triage Jerárquico de Reparación de Red:** Diagnóstico ordenado por capas OSI (L1 Interfaz -> L2 DHCP -> L3 Routing -> L4 DNS -> L7 Congestión).

---

## 4. Adaptadores Creados (Adapter Pattern)
- **`AutoSentinel` Safety Adapter:** Protege el motor HAL contra ejecuciones no autorizadas forzando `dry_run=True` cuando falta la variable de entorno de autorización `OMNINET_ALLOW_LIVE_AUTOREPAIR`.
- **`LicensingSecretAdapter`:** Desacopla la lógica de verificación de licencias del origen de los secretos, aislando los modos de prueba y producción.

---

## 5. Dependencias Nuevas Auditadas y Compatibles
- `pydantic` (2.13.5 - MIT)
- `httpx` (0.28.1 - BSD-3)
- `psutil` (7.2.2 - BSD-3)
- `cryptography` (50.0.0 - Apache-2.0 / BSD-3)
- `fastapi` (0.142.2 - MIT)
- `uvicorn` (0.54.0 - BSD-3)

---

## 6. Riesgos Identificados y Mitigaciones
- **Riesgo:** Ruptura de clientes HTTP existentes que consumen endpoints `/api/*`.
  - **Mitigación:** Preservación 100% estricta de las rutas y formatos JSON existentes mediante adaptadores de compatibilidad.
- **Riesgo:** Rechazo de licencias activas legítimas durante la transición asimétrica Ed25519.
  - **Mitigación:** Capa de migración dual (verificación de firmas Ed25519 con fallback de lectura para tokens HMAC previos ya registrados).

---

## 7. Estado de Pruebas Unitarias y Regresión
- **Suite de Pruebas:** 175/175 pruebas aprobadas (100% OK, 0 regresiones).
- **Cero Regresiones:** Ninguna prueba existente fue eliminada o degradada.
- **Compilación Limpia:** `python -m compileall -q .` finalizado con éxito sin errores de sintaxis.

---

## 8. Tareas en la Hoja de Ruta
- [x] Modelos de datos Pydantic v2 en `netopt/schemas.py` y validación de endpoints.
- [x] Adaptadores maduros en `netopt/adapters.py` (`psutil` y `httpx`).
- [x] Sustitución de `urllib.request` en `netopt/llm_gateway.py`, `cloud_server/proxy_server.py` y `netopt/licensing.py` por llamadas con `HttpClientAdapter` (`httpx`).
- [x] Integración de `resource_audit` en el bucle cognitivo Hermes (`hermes/foresee.py` y `hermes/executor.py`) mediante `psutil`.
- [x] Migración de endpoints REST hacia FastAPI/Pydantic/Uvicorn (`netopt/fastapi_app.py` y `main.py`) preservando 100% de los contratos HTTP existentes.
- [ ] Despliegue de firma asimétrica Ed25519 en `cloud_server/proxy_server.py` y `netopt/licensing.py` una vez autorizada la entrega de claves.

