# Primeros pasos en ABISSOL V2

Ingresa con el correo o usuario y la contraseña definidos durante la instalación.
El acceso muestra el logo oficial de ABISSOL y una tarjeta con acentos verdes.
El icono del ojo permite mostrar u ocultar la contraseña; la recuperación continúa
disponible mediante «¿Olvidaste tu contraseña?».
La cuenta inicial solicita una contraseña nueva al entrar por primera vez.
La pantalla de primer acceso mantiene la identidad verde y el logo del login;
muestra los requisitos de la clave y permite ver u ocultar ambos campos.

La cabecera del menú muestra el símbolo oficial y el nombre ABISSOL; al pulsarla
vuelves al panel principal.

## Chat con Sistemas

Una vez activado el canal, pulsa **Chat** en la cabecera. En **Sistemas · Virtual IA**
elige **Soporte Sistemas** para atención general o un integrante para una conversación
personal. Puedes enviar texto y adjuntar o pegar imágenes; Capturar solicita permiso
del navegador. Los números indican mensajes sin leer y el historial permite cargar
mensajes anteriores. Cada envío identifica tu usuario de ABISSOL ante Virtual IA.

Los estados se actualizan automáticamente. «Sin actualizar» indica que no se pudo
consultar el estado; puedes reintentar. Puedes escribir aunque Sistemas figure
desconectado. El chat se oculta durante la impersonación: vuelve a tu cuenta para
conversar. La presencia no registra jornada laboral. Esta función está preparada
localmente; falta activar el conector y publicarla en el piloto.

Desde el menú puedes administrar usuarios, roles y accesos, revisar auditoría,
organizar calendario y notificaciones, y trabajar con documentos. Las opciones
disponibles dependen de tus permisos. Configuración permite cambiar apariencia
y preparar los canales de comunicación que necesite la organización.

Esta primera entrega contiene la plataforma. Las funciones comerciales de ABISSOL
se incorporarán después de validar esta base.

## Piloto y actualizaciones

Abre https://v2.abissol.org/ e ingresa con tu cuenta administradora y la misma contraseña local.
El piloto usa su propia base `abissol_v2`; los cambios locales de datos no se replican.

En el entorno local, Sistema → DevOps permite consultar main, descargar cambios y subirlos a GitHub con una descripción. Publicar servidor exige main limpio y sincronizado; crea un respaldo de la base existente antes de migrar y comprueba la salud del servicio.
En el piloto, DevOps muestra el historial; las actualizaciones se ejecutan desde local.
Configuración privada: `BackEnd/.env` y `deployment/.env`, excluidos de Git. El frontend local usa `.env.development.local`; producción usa HTTPS en el dominio del piloto.
