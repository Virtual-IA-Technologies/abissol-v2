# Liquidaciones de vendedores: flujo simplificado

- Pendientes se cargan al elegir responsable, sin preparar fechas. Solo emisiones
  reales cobradas y aún no incluidas en otra liquidación. Conserva ámbito comercial
  y cálculo original (AFOCAT deposita costo proveedor; vendedor directo el cobrado).
- Selección calcula depósito exacto con céntimos. Voucher PDF/PNG/JPEG hasta 5 MB:
  OCR local con recursos existentes; PDF hasta tres páginas. Se extraen monto,
  operación, banco, fecha y cuenta cuando están disponibles. El usuario revisa
  y confirma; si OCR falla puede completar manualmente. Cuenta opcional porque
  hay vouchers enmascarados. OCR no acredita autenticidad ni verifica el banco.
- Un envío crea liquidación y voucher en la misma transacción, valida el total
  en backend, evita reutilizar operación/archivo y reserva emisiones con bloqueo.
  Estado interno `submitted`, visible **Enviado**. Vendedores no pueden modificar
  voucher enviado mientras Oficina lo revisa.
- Oficina verifica voucher y banco; **Confirmar y marcar Liquidado** concilia y
  cierra en una sola acción (`paid`), guarda comentario sin borrar el del vendedor,
  actualiza emisiones y conserva constancia de cierre en Central de documentos.
- Correo a `contacto@abissol.org`, CC `virtualizate.pe@gmail.com`, con voucher y
  comentarios. Destinatarios editables por Programador en Emisiones / Configuración;
  añadir copias separadas por coma. Se guardan destinatarios del envío en la cola.
  Cola en MedicalDispatch, procesada al enviar y recuperada por trabajador si quedó
  pendiente. Un resultado incierto exige revisar recepción: no reintenta ciegamente.
- Sin tablas nuevas, sin modificar históricos, sin enviar pruebas a SUNAT/META.
  Liquidaciones mensuales y de plataforma conservan sus flujos.

Referencia Laravel revisada: `MedicalLiquidationController::submit`, validaba
emisiones/importes, guardaba notas y estado `sent`; no enviaba correo allí.
V2 añade la notificación de Oficina y conserva comentarios y verificación humana.

Corrección de texto: plantilla WhatsApp tenía `Verificaci??n` en base de datos;
se corrigió a UTF-8 sin reenviar mensajes. Se revisó código de frontend/backend
y se añadió validación que impide guardar plantillas con caracteres dañados,
conservando tildes, ñ, enlaces y saltos de línea.

Validaciones: depósitos, comisiones, permisos, duplicados, rollback de archivos,
liquidación mensual, flujo simplificado y cabeceras To/CC con SMTP simulado.
