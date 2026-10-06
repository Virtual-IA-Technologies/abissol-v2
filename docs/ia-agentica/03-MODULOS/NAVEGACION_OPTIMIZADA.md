# Navegación y consultas — 6 de octubre de 2026

## Organización

- Se conserva Red comercial en el menú lateral.
- Planes y Comunicaciones se integran en las pestañas Planes y Envíos de Emisiones.
- Emisiones mantiene seis pestañas y Liquidaciones cuatro.
- Configuración de emisiones agrupa Parámetros, Correo y WhatsApp con pestañas inferiores.
- Canales y configuración fiscal siguen exclusivos de Programador en UI y backend.
- Configuración de plataforma conserva apariencia y plantillas de cuentas, que tienen otra finalidad.
- Las rutas antiguas redirigen a sus pestañas. La migración no elimina menús, permisos ni datos.
- Un usuario con permiso exclusivo de Planes o Envíos conserva acceso a su pestaña mediante
  la entrada Emisiones. Este acceso de navegación no concede permisos para consultar emisiones.

## Consultas

Los catálogos se conservan durante filtros y paginación de cada pantalla. Actualizar,
guardar o cambiar de usuario vuelve a cargarlos. Planes y Red comercial filtran localmente.
Red comercial reutiliza los perfiles de referencias en lugar de pedir dos listados.
El backend carga únicamente las referencias que usa cada sección y precarga roles.
Las credenciales fiscales se leen solamente para Facturación.

Envíos obtiene el código de certificado/liquidación con un join; ya no carga las últimas
200 emisiones para resolver sus nombres. El selector consulta su endpoint de búsqueda.
Liquidaciones consulta en bloque los orígenes AFOCAT de las emisiones y conserva los
criterios de cálculo. Las consultas no crecen por cada emisión incluida en la vista previa.
META obtiene los contadores en una agregación y el último intento por emisión de la página.
El índice `ix_medical_dispatch_meta_state` apoya la búsqueda por emisión, tipo y estado.

## Verificación

Pruebas SQLite de negocio, navegación, permisos y comunicaciones simuladas; regresiones
para usuario con Planes solamente, resumen META con intentos anteriores y último estado,
códigos de envíos y número constante de consultas de liquidaciones.
TypeScript y ESLint de componentes modificados. Navegador: seis pestañas de Emisiones,
cuatro de Liquidaciones, vista previa, selector de responsable y ancho móvil.
Las pruebas no envían mensajes ni emiten comprobantes reales.

No se cambia la habilitación fiscal de producción ni se borran registros históricos.
