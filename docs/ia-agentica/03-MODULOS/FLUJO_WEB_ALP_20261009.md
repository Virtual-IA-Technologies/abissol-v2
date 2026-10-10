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
