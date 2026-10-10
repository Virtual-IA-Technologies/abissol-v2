# Alcance comercial y filtros — 10/10/2026

- Emisiones, Liquidaciones, Facturación y Reportes: cabeceras compactas, búsqueda y fechas en una barra, menos texto repetido. Liquidación conserva selección seguida de voucher en panel lateral.
- Vendedor dependiente: emisiones propias; prepara liquidaciones con sus emisiones y el responsable comercial original. No accede a liquidaciones con partidas ajenas, sus vouchers ni documentos. Responsable: ventas propias y de sus dependientes. Coordinadores mantienen alcance de origen y administradores el global.
- Estado de cuenta, reportes, comprobantes y Archivos reutilizan el alcance del backend. Los importes agregados no incluyen ventas de hermanos o del responsable cuando consulta un dependiente.
- Reportes por plan: ventas, por cobrar, por liquidar, comisiones y vencimientos en 30 días. Excluyen anulaciones y pruebas. Los filtros y exportación respetan el mismo alcance.
- Migración 0016 agrega permisos comerciales faltantes de Liquidaciones, consulta de Facturación y Archivos; conserva permisos explícitos existentes, incluidas denegaciones. No cambia vínculos, numeración ni ventas.
- ALP: `deployment/alp/apply_business_scope.py` unifica la guardia del portal con `alp_int_user_can_access`, habilita consulta de liquidaciones para dependientes y rechaza roles desconocidos. Respaldo remoto `/root/codex-backups/alp-abissol-scope-20261010`.
- Pruebas: suite aislada de liquidaciones/documentos y nueva prueba de jerarquía, acceso directo, facturas, agregados y liquidaciones mixtas. Migración probada dos veces conservando denegaciones. Ocho casos de acceso comprobados con las funciones PHP reales de ALP.

Los archivos comerciales son administrados desde su origen: no se copian ni comparten manualmente para eludir permisos. La sincronización documental reutiliza originales y hashes, sin emitir comprobantes ni enviar comunicaciones.
