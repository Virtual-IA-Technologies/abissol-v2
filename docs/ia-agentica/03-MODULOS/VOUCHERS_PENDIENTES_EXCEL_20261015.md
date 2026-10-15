# Vouchers, pendientes y Excel — 15/10/2026

Registradas por solicitud expresa dos liquidaciones presentadas, sin conciliación bancaria:

| Certificado / asegurado | Voucher BBVA | Importe | Liquidación / voucher |
| --- | --- | --- | --- |
| A-00001 · Gino Nicolas Chayña Chura | 04/09, operación 25, terminal 15874 | S/ 55 | 27 / 16 |
| B-00001 · Adela Quispe Quea | 03/09, operación 24, terminal 18378 | S/ 255 | 28 / 17 |

Cuenta tomada de originales; asociación indicada por el titular. Coinciden fecha,
importe y número de movimiento en captura BBVA. Archivos íntegros, SHA-256,
control de duplicados y auditoría transaccional; respaldo JSON privado previo.
No se modificaron pagos ni se enviaron comunicaciones.

Pendientes sin liquidación: B-00002 Gabriela Araceli Montoya Ortiz (S/ 255,
abono 22/08) y A-00008 Johselyn Dajan Timoteo Zambrano (S/ 55, abono 09/10).
Total S/ 310. Coincidencias por fecha/importe; faltan vouchers. Ocho vouchers
presentados suman S/ 840; diez emisiones activas, S/ 1,150.

Vendedores enlista pendientes con certificado, asegurado, fecha e importe,
excluyendo anulados y pruebas y conservando alcance comercial. Los presentados
siguen sujetos a revisión bancaria. Liquidaciones anuladas se ocultan del listado
operativo y se conservan en Historial.

Totales al pie sobre todo el filtro, independientes de la página y sin anulados.
Excel exporta todo el filtro de Emisiones/Liquidaciones, fechas reales (registro
en hora Lima y vigencias separadas), importes numéricos con dos decimales y total.
Identificadores y documentos permanecen como texto.

Validación: seis regresiones de liquidaciones; prueba adicional de totales,
paginación, anulados y pendientes; TypeScript/ESLint; lectura XLSX con ExcelJS
para comprobar Date, hora Lima, tipos numéricos y total sin anulados.
Publicación expresamente autorizada en main y V2; comprobación HTTPS posterior.
