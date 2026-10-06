# Negocio ABISSOL V2

## Alcance

Implementación propia en FastAPI/React basada en la revisión estática de
`LARAVEL+ANGULAR/abissol`. No se importan usuarios, ventas, secretos ni archivos
del sistema anterior. SISAP conserva su estructura base independiente.

No se incorporan OTP WhatsApp, bandeja IMAP ni aprobaciones generales.
WhatsApp permanece como canal de comunicación saliente. La conciliación y
revisión de liquidaciones es parte del flujo financiero, no una bandeja general.

## Menús y uso

1. **Planes de asistencia:** precios, costos, comisiones, porcentaje META,
   vigencia, condicionado HTTPS y activación. Hampi Esencial y Hampi Plus son
   valores iniciales editables; repetir el inicializador no modifica precios.
2. **Red comercial:** crear orígenes y vincular usuarios existentes como
   administrador de origen, responsable o emisor dependiente. Asignar también
   permisos de menú desde Accesos; un perfil comercial no otorga permisos.
3. **Emisiones:** titular, documento, plan, emisor, vigencia y cobro completo.
   El inicio mínimo es mañana (America/Lima). Serie bloqueada transaccionalmente,
   importes/condicionado guardados como snapshot, referencia externa única,
   carta PDF y QR verificable sin datos personales públicos.
4. **Comunicaciones:** envío explícito de carta por SMTP o texto por WhatsApp,
   historial de intentos y reintento manual de fallidos. `sent` significa
   aceptado por el proveedor, no leído por el destinatario. Un timeout requiere
   revisar el proveedor antes de reintentar. No hay envío automático al emitir.
5. **Liquidaciones:** períodos por responsable y tipo vendedor/META/plataforma,
   selección de ventas cobradas, importes congelados, depósito íntegro del
   vendedor, comprobantes privados de hasta 5 MB y conciliación exacta.
   Flujo borrador/observado → presentado → aprobado → pagado. Administración
   revisa y cierra. Emisores dependientes no preparan liquidaciones.
   Un comprobante puede retirarse antes de presentar conservando archivo y
   auditoría. Cancelar libera las emisiones y referencias, preservando historial.
6. **Facturación:** preparación y corrección de borradores de boleta/factura
   vinculados a una emisión, sin duplicar documentos ni asignar correlativo fiscal.
   **No emite comprobantes electrónicos todavía.** No hay certificado/SOL,
   firma XML, envío SUNAT/CDR, notas de crédito/débito ni tratamiento tributario
   aprobado. La interfaz muestra esta limitación antes de registrar.
7. **Reportes:** emisiones, ventas, recaudación, por cobrar, comisiones y resumen
   por plan, fechas y alcance comercial. Exportación Excel de la página visible.

## Integridad y seguridad

- Administrador/Programador tienen alcance general; otros usuarios necesitan
  permisos y perfil comercial. Origen: su origen; responsable: su equipo;
  emisor: solo sus emisiones. Sin perfil no se devuelven ventas.
- Confirmar dinero recibido por ABISSOL exige administración. No se permite
  cobrar dos veces ni anular una venta cobrada sin conciliar la devolución.
- Cada emisión participa una sola vez en una liquidación activa de cada tipo.
  El vendedor deposita lo cobrado sin descontar la comisión. META calcula
  costo proveedor × porcentaje de plan, redondeado a dos decimales al emitir.
- Registro de auditoría en la misma transacción, sin secretos de proveedores.
- Comprobantes fuera de public_html, acceso autenticado y por ámbito.
- QR público mediante token aleatorio, sin búsqueda pública por DNI ni exposición
  de nombre/documento/contacto. La carta privada sí contiene los datos del titular.

## Instalación

Migración aditiva `0002_medical`: nueve tablas `medical_*`. Ejecutar Alembic
upgrade y `seed_platform` (el publicador ya lo hace). Dependencia nueva: qrcode
8.2, generación local; no se envían datos a servicios externos de QR.

## Pendientes de paridad con Laravel

Integración fiscal completa, consulta automática DNI/RUC, OCR de comprobantes,
remesas mensuales y envío consolidado a META, importación histórica,
conciliación de devoluciones/pagos parciales y reportes avanzados por vendedor.
No se simulan resultados de estas integraciones. El piloto ofrece los módulos
y operaciones descritos arriba; no equivale a paridad completa con Laravel.
