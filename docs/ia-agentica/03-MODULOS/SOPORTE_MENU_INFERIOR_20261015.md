# Soporte en menú inferior — 15/10/2026

El acceso Chat pasa al pie del menú lateral como Soporte, encima del usuario.
Reutiliza SystemsChat: directorio con búsqueda, conectados, no leídos, canal general,
conversaciones personales y adjuntos. El popover abre junto al menú; la conversación
conserva su modal. Sin cambios de API, permisos, presencia ni cadencias de consulta.

En móvil se accede desde el menú lateral. Los diseños alternativos de escritorio
(iconos/superior), que no montan AppSidebar, conservan acceso en cabecera renombrado
Soporte. Se evita duplicar instancias y consultas. Restricciones de impersonación
y cambio obligatorio de contraseña conservadas.

Validación: TypeScript/ESLint y build; comprobación de bundle publicado por HTTPS.
No se enviaron mensajes ni se modificaron conectores externos.
## Ajuste del cuadro y conexión — 15/10/2026

Soporte abre hacia arriba, alineado al inicio y con el ancho del botón del menú;
la altura se limita al espacio disponible y los contactos mantienen scroll.

Reporte del usuario: servicio de soporte no disponible. Se consultó la ruta efectiva
/bridge/people desde ABISSOL: HTTP 200; historial general HTTP 200. Cuatro GET
/abissol/api/v1/support-chat/contacts autenticados con la cuenta del titular dieron
200 y tres operadores; POST presencia 200. Sesión temporal eliminada, sin mensajes.
No se reprodujo el error ni se determinó su causa; no se cambiaron credenciales,
conectores ni el servidor de Virtual IA. Se conservan reintento manual y automático.

Validación: ESLint/build y comprobación autenticada posterior a la publicación.
