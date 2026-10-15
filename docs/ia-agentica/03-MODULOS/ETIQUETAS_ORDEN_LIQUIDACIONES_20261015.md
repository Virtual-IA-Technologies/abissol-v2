# Etiquetas y orden de liquidaciones — 15/10/2026

Estado en tabla/detalle de fila: Pendiente rojo, Enviado naranja y Liquidado verde,
con texto visible y colores para tema claro/oscuro. Excel conserva el estado en texto.
Vendedores se ordena por última fecha real de emisión descendente, incluyendo las
filas Pendiente; desempate por ID. La paginación y exportación siguen el mismo orden.

Aprobar y marcar Liquidado no exige comentario ni presenta campo de texto. El menú
conserva la confirmación y el detalle el botón de aprobación. /settle usa un payload
propio con reason opcional (máximo 1000); si se omite registra Aprobación de Oficina
Principal en notas y auditoría. Usuario, fecha, permisos, depósito completo, protección
contra doble cierre y auditoría de cada voucher se conservan. Otros motivos de edición,
conciliación y anulación siguen siendo obligatorios. No se aprobaron registros reales.

Validación focalizada: aprobación histórica con cuerpo vacío y rechazo sin permisos;
orden por emisión distinto al orden de registro, pendientes, filtros y paginación.
ESLint/TypeScript y build del publicador; comprobación HTTPS posterior.
