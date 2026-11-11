# Bibliotecas Adoptadas y Matriz de Dependencias Maduras
**Repositorio:** `galleguillosdavid-coder/OmniNetSaasia`  
**Directiva:** Mandato Maestro de Reemplazo por Bibliotecas Probadas (`docs/Auditorias/3.md`)  
**Fecha:** 2026-11-10

---

## 1. Matriz de Bibliotecas Adoptadas e Inventario

| Función Técnica | Biblioteca Madura | Versión Verificada | Licencia | Componente que Reemplaza | Estado de Integración |
|---|---|---|---|---|---|
| **Criptografía Asimétrica & Hashing** | `cryptography` | 50.0.0 | Apache-2.0 / BSD-3 | Criptografía artesanal y firmas HMAC incrustadas | Adoptada / Verificada en entorno |
| **Validación de Esquemas & Modelos** | `pydantic` | 2.13.5 | MIT | Validaciones manuales de diccionarios en handlers | Adoptada / Verificada en entorno |
| **Cliente HTTP Asíncrono / Síncrono** | `httpx` | 0.28.1 | BSD-3 | `urllib.request` artesanal con reintentos manuales | Adoptada / Verificada en entorno |
| **Telemetría e Inspección de Sistema OS** | `psutil` | 7.2.2 | BSD-3 | Wrappers artesanales de procesos y hardware | Adoptada / Verificada en entorno |
| **Framework API REST de Alto Rendimiento** | `fastapi` | 0.142.2 | MIT | `BaseHTTPRequestHandler` artesanal de `http.server` | Adoptada / Verificada en entorno |
| **Servidor ASGI de Producción** | `uvicorn` | 0.54.0 | BSD-3 | `ThreadingHTTPServer` artesanal | Adoptada / Verificada en entorno |
| **Motor de Respaldo Incremental Cifrado** | `Restic` (Binario Externo) | >= 0.16.0 | BSD-2 | Scripts de compresión y copias locales artesanales | Integrado como orquestador externo |
| **Motor de Limpieza Profunda de Sistema** | `BleachBit` (Motor Externo) | >= 4.6.0 | GPL-3.0 | Rutinas artesanales de vaciado de caché y temporales | Integrado como orquestador externo |
| **Inspección de Drivers y Hardware** | `Snappy Driver Installer Origin` (SDIO) | >= 1.12.9 | GPL-2.0 | Modificaciones manuales del registro de controladores | Integrado como orquestador externo |

---

## 2. Dependency Decision Records (DDR)

### DDR-001: Adopción de `cryptography` (v50.0.0)
- **Motivo:** Reemplazo de criptografía artesanal y soporte para firmas Ed25519 asimétricas en licenciamiento.
- **Licencia:** Apache-2.0 / BSD-3 (compatible con distribución comercial SaaS).
- **Riesgo:** Ninguno; estándar de facto en Python, respaldado por la Python Cryptographic Authority (PyCA).

### DDR-002: Adopción de `pydantic` v2 (v2.13.5)
- **Motivo:** Validación estricta y tipada de entradas en endpoints `/api/*` y `/v1/*` para prevenir fallos por payloads malformados.
- **Licencia:** MIT.
- **Riesgo:** Mínimo; alto rendimiento garantizado por el núcleo en Rust (`pydantic-core`).

### DDR-003: Adopción de `httpx` (v0.28.1)
- **Motivo:** Sustitución de `urllib.request` manual por un cliente HTTP con soporte nativo de timeouts, pooling de conexiones y HTTP/2.
- **Licencia:** BSD-3.
- **Riesgo:** Mínimo; API análoga a `requests` con soporte async nativo.

### DDR-004: Adopción de `psutil` (v7.2.2)
- **Motivo:** Obtención precisa de CPU, RAM, interfaces de red, sockets abiertos y PID del sistema operativo multi-OS sin ejecutar comandos CLI externos frágiles.
- **Licencia:** BSD-3.
- **Riesgo:** Ninguno; biblioteca estándar multiplataforma madura y probada.

