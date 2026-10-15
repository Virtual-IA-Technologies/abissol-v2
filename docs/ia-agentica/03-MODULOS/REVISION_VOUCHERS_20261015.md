# Liquidaciones y revisión de vouchers — 15/10/2026

Tabla compacta con número, asegurado(s), responsable, registrada, ventas y estado.
Se retiran tipo, período, comisión/proveedor, depósito, saldo y comisión pendiente
del listado; siguen disponibles en el detalle. Búsqueda por asegurado o certificado,
conservando alcance comercial y consultas agrupadas por página.

Primera opción del menú: **Ver voucher**. Abre directamente la imagen/PDF, permite
cambiar entre varios adjuntos e informa si no existe sustento. El detalle del
vendedor también previsualiza en vez de descargar. Acceso mediante API autenticada.

## Cotejo de los seis adjuntos activos

Originales leídos visualmente y SHA-256 de los seis archivos verificado en servidor.
Referencia: las dos capturas bancarias entregadas en esta conversación, cuenta BBVA
ABISSOL. El ordenante del abono puede diferir del asegurado del certificado.

| Asegurado | Voucher | Importe | Resultado contra capturas |
| --- | --- | --- | --- |
| Lesslie Michelle Rafael Ruiz | 19/08, operación 00871172 | S/ 55 | Fecha fuera del rango visible: no comprobable. |
| Valeria Yiré Gonzales Ysla | 21/08, operación 784.465.197.3495 | S/ 55 | Coincide fecha/importe con abono de Fátima Ysla Roque. Voucher muestra CCI BBVA. |
| Yovana Yampasi Choquehuayta | 18/09, operación 02664206 | S/ 55 | Coincide fecha/importe con abono de Carmen Lastenia Ysla. |
| Isabel Yhessenia Marca Apaza | 29/09, operación 01326669 | S/ 55 | Coincide fecha/importe con abono de Carmen. Registro tenía 05/10; se corrige según imagen original. |
| Carmen Lastenia Ysla Roque | 01/09, operación 02868392 | S/ 55 | Coincide fecha/importe con abono de Carmen. |
| Gloria Manuela Villafranqui Malpartida | 15/10, operación 01832303 | S/ 255 | Coincide fecha/importe con abono de Rosmery en primera captura; segunda captura termina el 09/10. |

Cinco coincidencias por fecha e importe (S/ 475); una sin evidencia bancaria visible
(S/ 55). Las capturas no muestran los números de operación de las transferencias:
el cotejo no prueba identidad bancaria completa ni autoriza marcar Liquidado.
Los vouchers BCP indican banco emisor BCP y receptor BBVA; los registros nativos
conservan BCP y cuenta vacía. No se inventa la cuenta completa a partir de «7147».

Abonos visibles sin uno de estos seis vouchers: 22/08 S/ 255, 03/09 S/ 255,
04/09 S/ 55 y 09/10 S/ 55, total S/ 620. No se atribuyen a certificados por monto.
Retiro S/ 400 y cargos bancarios S/ 2/S/ 15 no son depósitos de liquidaciones.

La corrección de fecha del voucher 12 conserva archivo, referencia, importe y
estado pendiente; respaldo JSON privado previo y evento transaccional en auditoría.
No se aprueba ni concilia dinero real. No se crean ni duplican adjuntos.

Validación: pruebas focalizadas de liquidaciones, búsqueda por asegurado y alcance,
TypeScript/ESLint y build del publicador. Publicación en main y v2.abissol.org
autorizada expresamente por el usuario.
