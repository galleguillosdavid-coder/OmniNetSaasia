Para optimizar la velocidad y estabilidad de internet en Windows 10 y Windows 11, lo más efectivo es desactivar los servicios que consumen ancho de banda en segundo plano y asegurar que los servicios esenciales de red estén activos.
Puedes gestionar todos estos elementos presionando Windows + R, escribiendo services.msc y pulsando Enter.

Servicios que debes APAGAR (para liberar ancho de banda)

Desactivar o cambiar a inicio "Manual" estos servicios evita que Windows o programas de terceros usen tu conexión sin avisar:
• Optimización de distribución (Delivery Optimization). Este servicio usa tu conexión para subir y compartir actualizaciones de Windows con otras computadoras en tu red local o en internet. Cambiarlo a Manual o desactivarlo desde Configuración > Windows Update > Opciones avanzadas libera mucha velocidad de subida.
• Experiencias del usuario y telemetría asociadas. Este servicio recopila datos de diagnóstico y uso del sistema para enviarlos de forma constante a los servidores de Microsoft. Puedes ponerlo en Deshabilitado sin afectar el funcionamiento del equipo.
• Servicio de transferencia inteligente en segundo plano (BITS). Se encarga de descargar actualizaciones de aplicaciones y del sistema usando el ancho de banda libre. Si notas picos de latencia o lentitud, puedes detenerlo temporalmente o pasarlo a Manual.
• Servicios de actualización de terceros (Google, Adobe, Steam, etc.). Programas como navegadores o lanzadores de juegos instalan servicios propios que buscan actualizaciones en segundo plano. Puedes cambiarlos a Manual para que solo se ejecuten cuando abras la aplicación correspondiente.
• Servicio de informe de errores de Windows. Envía registros de fallos por internet cada vez que un programa deja de responder. Cambiarlo a Manual o Deshabilitado evita envíos de datos innecesarios.

Servicios que deben estar ENCENDIDOS (para estabilidad y rapidez)

Nunca desactives los siguientes servicios, ya que son vitales para que la conexión funcione con normalidad y baja latencia:
• Cliente DNS. Guarda en caché las direcciones web que visitas para que carguen mucho más rápido la próxima vez que entres. Debe estar siempre en Automático.
• Cliente DHCP. Gestiona y renueva automáticamente tu dirección IP local con el router. Si se apaga, perderás el acceso a internet.
• Conexiones de red y Reconocimiento de ubicación de red. Administran tus adaptadores Wi-Fi o Ethernet y detectan el estado de tu conexión. Ambos deben permanecer activos para evitar desconexiones.
• Configuración automática de WLAN. Es indispensable si te conectas mediante Wi-Fi, ya que gestiona las redes inalámbricas disponibles y la estabilidad de la señal.

Ajuste extra recomendado (Ancho de banda reservado)

Además de los servicios, Windows reserva por defecto un porcentaje del ancho de banda para tareas del sistema. Si tienes Windows Pro, puedes liberar el 100% de tu conexión siguiendo esta guía de optimización de red:
1. Presiona Windows + R, escribe gpedit.msc y pulsa Enter.
2. Ve a Configuración del equipo > Plantillas administrativas > Red > Programador de paquetes QoS.
3. Haz doble clic en Limitar ancho de banda reservable, selecciona Habilitada y cambia el límite de 80 a 0.