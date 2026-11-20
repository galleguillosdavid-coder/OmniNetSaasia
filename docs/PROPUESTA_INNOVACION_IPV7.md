# 🚀 Propuesta de Capacidades Avanzadas para OmniNet (Análisis de Conceptos)

> Documento de diseño propio e independiente para **OmniNet AI Agent Pro**, inspirado en capacidades de redes soberanas, túneles P2P, criptografía poscuántica y motores de evolución/recuperación.
>
> **Principio de Independencia:** Todas las capacidades aquí propuestas se diseñarán e implementarán de forma 100% nativa dentro de `netopt/` y `hermes/`, sin dependencias ni acoplamientos externos.

---

## 1. Lo que Más Aporta Valor a OmniNet (Priorizado)

### A. Malla Privada Multi-Dispositivo con Túnel Virtual (`Wintun` / `TUN`)
- **Qué resuelve:** Hoy `netopt/micro_internet.py` opera en capa de aplicación. Con un adaptador virtual ligero (`Wintun` en Windows / `TUN` en Linux/macOS), los equipos de un mismo usuario (**Plan Hogar / Pyme 5 PCs**) pueden comunicarse como una red local privada cifrada desde cualquier lugar del mundo.
- **Cómo integrarlo:** Módulo opcional `netopt/virtual_mesh.py` activable bajo demanda, protegido por `Zero NetLoss` (si el túnel falla, la ruta por defecto del sistema nunca se bloquea).

### B. Keystore Soberano y Autenticación Criptográfica P2P (`Ed25519` + PQC)
- **Qué resuelve:** Almacenar de forma cifrada la identidad de cada dispositivo (`DID` local), certificados efímeros y llaves de sesión para que los nodos de la malla se autentiquen sin depender de un servidor central.
- **Cómo integrarlo:** Extender `netopt/micro_internet.py` con un almacén local protegido (`~/.netopt_state/keystore.json` cifrado con `cryptography` / Argon2id) y rotación periódica de llaves.

### C. Failover Multipath Automático (Wi-Fi + Ethernet / Tethering)
- **Qué resuelve:** Si la interfaz principal (ej. Wi-Fi) sufre caída o pérdida > 5%, cambiar o respaldar tráfico crítico automáticamente hacia una interfaz secundaria disponible (Ethernet o USB tethering).
- **Cómo integrarlo:** Regla en `netopt/autonomous_scheduler.py` + `netopt/hal.py` para ajustar métricas de interfaz de forma segura con snapshot previo.

### D. Cuarentena Segura y Deduplicación Pre-Respaldo
- **Qué resuelve:** En mantenimiento de PC (`Antivirus` y `Limpieza`), mover archivos sospechosos o duplicados pesados a una **zona de cuarentena reversible** antes de eliminarlos definitivamente, reduciendo el riesgo a cero.
- **Cómo integrarlo:** Nuevo helper en `netopt/device_maintenance.py` con índice JSON de restauración en 1 clic (`~/.netopt_state/quarantine/`).

### E. Panel Visual "Antes vs. Después" en el Dashboard
- **Qué resuelve:** Que el usuario final vea de forma gráfica e inmediata cuánto bajó su latencia, jitter y bufferbloat tras las optimizaciones de OmniNet.
- **Cómo integrarlo:** Endpoint `/api/metrics/impact` en `netopt/fastapi_app.py` alimentado por `~/.netopt_state/local_empirical_metrics.json` y tarjeta visual simple en el Dashboard.

---

## 2. Selección Rápida (Marca con `[x]` lo que quieras que implemente)

- [x] **1. Túnel Malla Privada (`Wintun`/`TUN`)** para conectar hasta 5 PCs del usuario.
- [x] **2. Keystore Cifrado Local** con `cryptography` para identidades P2P y secretos.
- [x] **3. Failover Multipath** (cambio automático Wi-Fi ↔ Ethernet/USB si hay cortes).
- [x] **4. Cuarentena Reversible + Deduplicación** en limpieza/antivirus.
- [x] **5. Panel Visual "Antes vs. Después"** en el Dashboard (`http://127.0.0.1:8877`).
