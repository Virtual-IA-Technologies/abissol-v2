# Lista unificada y aprobación — 15/10/2026

Vendedores integra emisiones sin liquidación como filas Pendiente. Son virtuales,
con ID negativo e issuance_id explícito, sin crear datos financieros. Unión SQL
paginada con búsqueda, totales y alcance comercial. Excluye anulados y pruebas.
Período mes/año y fechas se obtienen de la emisión real; depósito de vouchers activos,
con rango si hay varias fechas. Filtros Desde/Hasta por fecha de emisión. Excel
con fechas reales y extremos del rango en columnas separadas.

Con voucher se muestra Enviado; al aprobar, Liquidado. Doble clic y Enter abren
detalles, conservando Ver voucher como primera acción del menú. Las filas Pendiente
muestran sus datos y permiten iniciar el registro sin inventar liquidaciones.

Oficina Principal tiene Aprobar y marcar Liquidado en menú y detalle. Backend exige
permiso gestor y administración global, depósito completo, emisiones emitidas y
motivo; verifica vouchers con usuario/fecha y auditoría individual, cierra y actualiza
pagos de emisiones de forma transaccional. No se aprobaron liquidaciones productivas.

Excepción histórica solicitada: /settle permite cerrar vendedores importados en pending
con voucher completo además de nativos submitted/approved. No habilita otras ediciones,
altas/retiradas de vouchers históricos ni reapertura de cierres.

Gabriela B-00002: adjunto nuevo S/ 255 del 22/08, operación 784.465.193.6011,
Scotiabank a BBVA, descripción Gabriela Ortiz. CCI tomado completo del original.
Liquidación 29/voucher 18, presentado sin conciliación. Archivo original, SHA-256,
respaldo previo privado y auditoría; sin enviar comunicaciones.
Queda A-00008 Johselyn por S/ 55 como Pendiente. Nueve vouchers suman S/ 1,095;
lista completa S/ 1,150.

Validación: regresiones de depósitos/cierres/alcance, pruebas de unión paginada,
filtros y fechas de emisión, totales y aprobación histórica con rechazo de usuarios
sin administración. TypeScript/ESLint, lectura XLSX y build; consulta HTTPS posterior.
