# Confirmación y consulta oficial (09/10/2026)

La carta nueva y los mensajes enlazan a `https://abissol.org/?consulta=...`.
La API pública consulta por código, token o documento; enmascara el documento,
distingue pruebas, vigencia futura, vencimiento y anulación. Permite descargar
carta y condicionado. No expone correo, teléfono ni importes.

Emisiones incorpora **Enviar al cliente**, protegido por alcance comercial y
permiso de comunicaciones. Correo y WhatsApp reutilizan proveedores existentes,
registran resultados y requieren confirmación explícita para repetir intentos.
En pruebas la recepción real requiere destinatarios autorizados en configuración
privada. Aceptado por proveedor no equivale a recepción confirmada.

El adaptador ALP conserva `/abissol/` y `/emitir/`, boleta/factura y archivos.
Su configuración privada permite volver al origen anterior sin editar secretos
del repositorio. Preparación fail-closed sobre copia del servidor, respaldos
privados y validación PHP antes del corte. No habilita SUNAT ni correlativos
reales: el lote de pruebas continúa activo.

Validación previa: seis pruebas aisladas de documentos, consulta y comunicaciones;
TypeScript correcto. Las pruebas de proveedores usan únicamente los destinatarios
autorizados por el usuario. Las brechas fiscales y liquidaciones históricas del
informe de corte siguen pendientes; esta entrega no autoriza retirar Laravel.

## Resultado publicado

Backend/frontend desplegados en `bd57548`; web y adaptador activados después
de comprobar hashes contra los originales respaldados. Web: QR automático,
recarga conservando código y descargas comprobados en navegador sin errores.
V2: modal y ambos canales comprobados. Dos cartas de prueba actualizadas como
nuevas versiones; ningún original real reescrito. Prueba real autorizada de
correo y WhatsApp registrada como `sent` (aceptación del proveedor, no acuse del
destinatario). Sin variación de correlativos ni trabajos SUNAT.

ALP: catálogo de dos planes, 59 perfiles y cinco emisiones consultados con el
adaptador normal; validación completa de emisión con rollback. No se creó CAT
ni se probó su facturación. `/abissol-pruebas/` permanece como portal auxiliar;
el flujo habitual está en `/abissol/`. El conector regular está limitado al
origen externa_alp; configuración y credenciales permanecen fuera de Git.

Respaldo privado: `/root/abissol-cutover-20261009/`. Para revertir el destino ALP,
retirar su override privado `/home/alp/.abissol-v2-config.php`; los cambios de
adaptador son condicionales. Para revertir la web, restaurar `site/index.before.php`
con propietario abissol. No revertir datos ni correlativos automáticamente.

## Acciones y limpieza de pruebas

Emisiones utiliza el menú compartido vertical con iconos; clic derecho ofrece
las mismas acciones autorizadas. Doble clic o Enter abre la carta dentro de un
visor, sin ejecutar cobros, anulaciones ni envíos. El aviso enlaza ahora al
portal habitual ALP y explica la excepción de destinatarios de prueba.

Por autorización expresa se retiraron exclusivamente las emisiones de prueba
32 y 33, sus dos comprobantes, diez documentos con versiones y envíos asociados.
Respaldo privado SQL/archivos/inventario en `backups/remove-two-tests-20261009`.
Sin liquidaciones ni trabajos fiscales relacionados; numeradores conservados.
Lote de pruebas y bloqueo SUNAT permanecen activos. Los mensajes ya aceptados
por proveedores externos no se pueden retirar desde esta limpieza.

Después de limpiar, el adaptador normal ALP consultó correctamente sus cuatro
emisiones restantes y validó una emisión con rollback sin crear CAT ni venta.

Plantilla WhatsApp actualizada en configuración productiva: saludo, bienvenida,
programa/certificado, vigencia y enlaces separados por saltos de línea. Ajuste
auditado y renderizado con datos ficticios; sin reenvíos ni cambios al correo.

## Paneles laterales y documentos

Formularios y detalles médicos usan el panel lateral derecho compartido (Sheet),
incluidos envío, facturación y liquidaciones. Emisiones añade ver comprobante,
condicionado y validar en la web oficial. El comprobante se obtiene bajo alcance
de la emisión y sin generar documentos nuevos. Solo se consulta al abrir.
Planes, red comercial, envíos, facturación, liquidaciones y reportes reutilizan
acciones de fila para menú vertical, clic derecho y doble clic de consulta.
Las operaciones de cobro, anulación y envío conservan permisos y confirmaciones.
El detalle genérico de tablas de plataforma también abre lateralmente; los
paneles existentes de usuarios, roles y auditoría conservan su comportamiento.

## Consulta pública: documento y estados

El QR conserva su token en el enlace, sin mostrarlo en el campo de documento.
La API devuelve el documento completo únicamente cuando se consulta con el
token exacto del QR o con ese mismo documento; por código corto sigue enmascarado.
La página rellena el documento recibido y conserva el enlace al recargar.
Vigencia futura y pruebas usan celeste; vigentes, verde; vencidos y no encontrados,
neutro; anulados y errores, rojo. Sin alterar fechas ni declarar cobertura futura
como activa. Se evita enviar consultas simultáneas desde el botón Buscar.

## Envío automático de nuevas emisiones

La configuración privada `automatic_documents_enabled` activa una cola de
comunicaciones dentro de la transacción común de venta interna/externa.
Las validaciones con rollback y los reintentos de la referencia externa no
duplican envíos. No se envían registros históricos al activar la opción.
El trabajador programado cada minuto procesa la cola fuera de la petición:
correo con carta, condicionado disponible y comprobante PDF; WhatsApp con
confirmación, consulta oficial y enlace a la carta. Espera el PDF si está pendiente.
Errores y resultados quedan en Envíos; no se repiten intentos inciertos automáticamente.
Un corte durante un envío puede dejarlo En curso y exige revisar el proveedor.

En pruebas solo se contacta a destinatarios de la lista autorizada; los demás
quedan Simulados. Sin contacto registrado no se crea envío para ese canal.
Conserva lote de pruebas, numeradores reales y bloqueo SUNAT. Activación sin
mensajes retrospectivos ni cambio a operación definitiva.

## SMTP y cortes META

Remitente: contacto@abissol.org, Asociación de Bienestar, Inclusión, Salud y
Solidaridad. SMTP mail.abissol.org:587 con STARTTLS; autenticación verificada,
contraseña cifrada en configuración privada, nunca en repositorio.

META automático a las 11:00 y 21:00 America/Lima, configurable por Programador.
Solo emisiones reales vigentes en registro (estado issued), creadas hasta el corte
y sin intentos previos. Excluye pruebas y anuladas; sin pendientes no envía correo.
MedicalBusinessSetting id=2 conserva actor y último corte, sin crear tablas.
La reserva de envíos se confirma antes de SMTP. Los resultados inciertos requieren
revisión manual; no se reintentan automáticamente. La activación comienza en el
próximo corte, sin disparar un correo inmediato.

Primer envío sin prefijo REENVÍO incluso si se marcó forzar. Se conserva Excel de
altas con 11 columnas y, para liquidación mensual, Excel de 8 columnas y carta PDF,
equivalentes al flujo Laravel. No se envían pruebas a META.

Se retiró la etiqueta PRUEBA añadida a asunto/cuerpo de confirmación; los códigos
y documentos de prueba mantienen su identificación y el bloqueo SUNAT continúa.
Pruebas focalizadas: cortes, exclusión de pruebas, deduplicación, adjuntos diario y
mensual, resultado SMTP incierto y entrega permitida: 4 pruebas correctas.

## Registro de emisión: espacio y datos del adquirente

Encabezado lateral con margen horizontal explícito en escritorio y móvil;
cuerpo con 32 px en escritorio. Nombres, apellidos, razón social y dirección
se convierten a mayúsculas tanto al escribir/consultar como en el backend.
Ubigeo del adquirente se conserva si la consulta RUC devuelve seis dígitos;
ya no se pide el código manualmente ni bloquea el registro si está ausente.
No se inventa un ubigeo ni se sustituye por el del emisor. El XML ya omite
el elemento del adquirente cuando no está disponible; el del emisor conserva
su validación. Referencia: guía oficial SUNAT Factura UBL 2.1, adquirente (18–19).

El formulario no solicita vencimiento ni genera crédito por estar pendiente
de cobro interno. Sin vencimiento explícito, la factura se genera al contado;
se conserva el estado de cobranza y la compatibilidad de integraciones que
envían expresamente un vencimiento válido. Aplica también a documentos de
prueba. Dos pruebas fiscales verifican XML, normalización y contrato externo
con proveedores simulados; sin envíos a SUNAT ni emisiones reales.
