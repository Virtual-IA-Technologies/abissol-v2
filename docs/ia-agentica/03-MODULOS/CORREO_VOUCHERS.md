# Correo de vouchers — 16/10/2026

El envío de Liquidaciones usa el asunto «ENVIO DE COMPROBANTE DE PAGO», saludo,
programa, cliente, documento, vigencia DD/MM/AAAA resaltada en amarillo y solicitud
de conformidad. Firma el responsable de la liquidación. Si hay varios asegurados,
se incluyen todos. Adjunta los vouchers activos y comprueba su SHA-256.

Conserva los destinos configurados y agrega siempre abbisol.hampi@gmail.com.
No modifica estados financieros ni confirma depósitos por enviar correo.

Reenvío explícito autorizado por el usuario: scripts/resend_settlement_vouchers.py
--expected-database abissol_v2 --expected-count 10; sin --send solo valida.
Con --send registra un intento settlement_office_format_v2 por liquidación,
conserva su resultado y nunca repite un intento existente, incluso incierto.
Selección: vendedores no cancelados, sin pruebas y con voucher activo disponible.
Validación de formato, destinatarios, adjunto y protección de duplicados en
la prueba existente de envío de liquidaciones, usando SMTP simulado.

## Reversión de liquidación — 16/10/2026

Oficina Principal y administradores (rol Administrador o superusuario y permiso
gestor de Liquidaciones) pueden usar «Revertir a Enviado» desde el menú o detalle.
POST /medical/liquidations/{id}/reopen exige motivo y una liquidación nativa de
vendedor en estado paid. Devuelve submitted, retira la conciliación de depósitos
y compensaciones, y devuelve las emisiones liquidadas al estado de cobro según
el depósito de su partida. Conserva archivos, pagos de comisión y correos.
Audita voucher, emisión y liquidación en una sola transacción. Los históricos
permanecen de consulta. Vendedores no pueden aprobar ni revertir, incluso con
un permiso gestor individual sin rol administrativo. Prueba de ida y vuelta,
rechazo de doble reversión y permisos verificados con SQLite y SMTP simulado.

La liquidación 000027 estuvo incluida en los diez correos del formato nuevo
(intento 108, enviado); la reversión no duplica ese envío.

## Búsqueda por período — 16/10/2026

Liquidaciones reconoce los doce meses en español, sin distinguir mayúsculas,
con año opcional («agosto», «agosto 2026», «agosto de 2026»). Filtra por fecha
de emisión de las partidas, también para emisiones pendientes sin liquidación.
No depende de notas ni de la fecha de depósito. Conserva filtros de fecha,
permisos, paginación, totales y exportación. Prueba aislada verifica mes, año,
pendientes, liquidaciones, total de ventas, paginación y alcance de usuario.
Incidencia reproducida en producción: cinco emisiones de agosto, solo dos
encontradas anteriormente por coincidencias textuales.
