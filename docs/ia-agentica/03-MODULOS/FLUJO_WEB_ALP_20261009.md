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
