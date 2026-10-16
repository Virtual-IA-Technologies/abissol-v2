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
