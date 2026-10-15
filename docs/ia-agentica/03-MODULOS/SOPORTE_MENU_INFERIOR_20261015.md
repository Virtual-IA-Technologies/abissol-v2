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
