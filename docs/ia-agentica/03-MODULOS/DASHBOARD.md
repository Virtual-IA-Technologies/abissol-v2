# Dashboard comercial

Inicio muestra un resumen del ámbito autorizado del usuario, con estilo verde, tarjetas y gráficos animados inspirados en Virtual.IA. Se respeta movimiento reducido y tema personal.

- Períodos de 1, 3, 6 y 12 meses: cantidad y venta emitida, gráfico mensual desde el primer día del mes inicial.
- Vigentes al día de hoy y emisiones pendientes de liquidar de todos los períodos.
- Liquidaciones de vendedores: por revisar, liquidadas y en preparación. Un voucher histórico presentado no se considera aprobado.
- Cinco últimas emisiones y accesos a las opciones correspondientes.
- Fechas de negocio según America/Lima. Se excluyen emisiones de prueba y anuladas.

`GET /medical/dashboard?months=3` resuelve permisos de menú y alcance comercial en backend. Cada sección sin permiso retorna null. Respeta contraseña pendiente de cambio. Usa agregaciones SQL y limita el detalle a cinco filas; cuatro consultas de negocio como máximo más resolución de autorización. No genera documentos ni comunica con proveedores. Una sola petición del navegador, deduplicada mientras está en curso; sin caché compartida entre usuarios.

Los listados de Emisiones y Liquidaciones muestran la fecha y hora exactas de registro en America/Lima, tanto en pantalla como en la exportación.

Optimización adicional: EmissionForm, EmissionDelivery, BillingHistory, SellerSettlementForm, SellerSettlementDetail y LiquidationDetail se cargan al abrirlos, manteniendo la tabla visible mientras se descarga el componente. No se añadieron bibliotecas de gráficos, tablas ni migraciones.

Prueba aislada `test_medical_dashboard`: aislamiento de vendedor dependiente, totales por período frente a pendientes históricos, exclusión de prueba, voucher pendiente, denegaciones explícitas, autenticación y rango de fechas. Publicación mediante el flujo habitual con compilación y comprobación HTTPS.

Verificación local: prueba del dashboard aprobada; dos pruebas de `test_seller_scope` aprobadas con renderizador PDF sustituido por fixture. La ejecución adicional con PHP real agotó 30 segundos al generar un PDF; no se cambió ese generador ni se atribuye el timeout al dashboard. TypeScript correcto; ESLint sin errores, con una advertencia sobre la referencia usada deliberadamente para invalidar respuestas al desmontar.
