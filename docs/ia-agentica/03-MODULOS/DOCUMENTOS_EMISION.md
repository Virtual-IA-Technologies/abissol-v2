# Documentos de emisión — 07/10/2026

Las nuevas cartas de bienvenida, comprobantes A4, tickets de 80 mm y el correo de
bienvenida conservan las plantillas de ABISSOL Laravel (carta versión 7), sus logos,
textos y estilos. Se utiliza el mismo motor Dompdf 3.1.6, aislado como proceso CLI;
FastAPI conserva toda la lógica, permisos, numeración y persistencia. No se ejecuta
Laravel ni se conecta a su base al imprimir. El renderer no admite recursos remotos,
PHP embebido ni JavaScript; los logos y QR se incorporan localmente.

## Flujo

1. La emisión interna o externa archiva su carta. Portal, API externa, QR y correo
   descargan esos mismos bytes. Los originales históricos no se regeneran.
2. El QR de cartas nuevas lleva a la validación de V2 mediante un token opaco. La
   página muestra afiliado, documento enmascarado, programa, fechas y estado, y
   permite descargar carta y condicionado. Distingue vigencia futura, vigente,
   vencida y anulada. No se expone búsqueda pública por DNI. Las cartas anuladas
   dejan de descargarse públicamente. El JSON conserva su respuesta sin nombre/DNI.
3. Emisiones / Envíos permite enviar la bienvenida por correo, con carta y
   condicionado archivado adjuntos, botones de descarga y consulta de membresía.
   La plantilla de texto configurada se conserva como contenido adicional.
4. Facturación / Historial y archivos ofrece PDF A4, ticket y originales fiscales.
   El editor puede enviar los adjuntos disponibles a un destinatario explícito.
   Cada intento queda registrado en Envíos con su número de comprobante; un envío
   previo exige confirmar reenvío. Los estados inciertos no se reintentan solos.
   Esta acción no genera otro comprobante ni lo reenvía a SUNAT. Beta no se envía.

El QR fiscal mantiene el contenido SUNAT del comprobante, distinto del QR de
membresía. Se muestran las condiciones de crédito y vencimiento reales. Se
conservan los importes de los ítems: el renderer no recalcula ni modifica el XML.
La validación web usa el diseño de la tarjeta institucional sin copiar la página
comercial completa. El enlace de consulta cambia deliberadamente a V2; los QR
de documentos históricos siguen en su URL original.

## Instalación y despliegue

Además de Python y Node se requiere PHP CLI >= 8.2 con dom, mbstring y GD, y Composer.
`setup-local.ps1` instala `BackEnd/pdf_renderer/composer.lock`. En Windows el renderer
carga GD para ese proceso; no modifica php.ini. Puede indicarse `ABISSOL_PHP_BIN`
si PHP no está en PATH. `deployment/publish.py` instala y empaqueta vendor según el
lock; el servidor no requiere Composer ni descarga dependencias PHP. Antes de
migrar o activar un release se ejecuta `scripts/check_pdf_runtime.py` con datos
ficticios. La caché de impresión reside en storage privado.

En cPanel se usa explícitamente `/opt/cpanel/ea-php82/root/usr/bin/php` cuando está
instalado, porque el `php` del usuario del servicio puede seleccionar PHP 8.1.
Esto no cambia la versión PHP de Laravel ni de otros sitios del servidor.

Migración 0014 agrega invoice_id a medical_dispatches; no crea tablas nuevas.
Consultas de envíos usan joins, las plantillas y logos se cachean en memoria y las
descargas reutilizan archivos existentes. No se borran tablas ni documentos reales.

## Verificación y límite de activación

Pruebas aisladas: carta archivada = descarga privada = pública = adjunto; correo
simulado con condicionado; estados del QR; dimensiones A4/ticket, montos, crédito,
hash y contenido del QR fiscal; permisos, duplicados e incertidumbre del correo.
Regresión fiscal y de emisiones sin envíos a clientes ni comprobantes reales.

La activación fiscal productiva y el cambio de ALP desde Laravel siguen pendientes
de definir series/corte. Restaurar estos diseños no activa la facturación real ni
cambia la integración productiva de ALP.
