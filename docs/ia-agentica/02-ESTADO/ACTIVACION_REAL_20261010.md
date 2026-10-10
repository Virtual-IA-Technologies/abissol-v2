# Operación real — 10/10/2026

- Autorización expresa del usuario: eliminar todas las pruebas y activar operación real con envío a SUNAT.
- Respaldo previo: `/home/abissol/apps/abissol-v2/backups/close-tests-20261010/before.sql.gz`, inventario y archivos asociados.
- Eliminadas 2 emisiones, 2 comprobantes de prueba, 1 liquidación de prueba, su voucher, despachos y documentos vinculados. Preservadas 10 emisiones reales y todos los correlativos de planes. No se renumeraron registros reales.
- Configuración fiscal: `test_batch=null`, `enabled_in_v2=true`, producción. Series exclusivas V2 **B002 / F002**, próximos correlativos 1; comprobadas libres en V2 y Laravel. Las series B001/F001 continúan reservadas al sistema anterior. Certificado validado, vence 03/07/2029. Activación registrada en auditoría. No se creó un comprobante real solo para probar.
- Integración externa real activa; temporizador fiscal activo. La aceptación de la próxima emisión depende de la respuesta de SUNAT y su CDR.
- El correo de la liquidación de prueba estaba `simulated`: no era un fallo SMTP. Verificación real enviada a contacto@abissol.org con copia a virtualizate.pe@gmail.com. Exim confirmó entrega local y aceptación Gmail 250; esto no garantiza clasificación en bandeja principal. Destinatarios siguen configurables en Emisiones → Configuración.
- Interfaz: selección de pendientes en la página; adjuntar voucher abre el modal lateral. Vista previa, OCR, ajuste de datos, envío y confirmación se completan dentro del modal. Cierre durante OCR/envío bloqueado; permite volver a la selección antes de enviar.
- Validación: TypeScript correcto. La modificación reutiliza endpoints de liquidación y OCR previamente verificados, sin cambiar consultas ni cálculos.
