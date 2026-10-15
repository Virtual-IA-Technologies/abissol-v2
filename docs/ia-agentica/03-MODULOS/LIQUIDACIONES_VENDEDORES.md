# Liquidaciones y estado de cuenta — 07/10/2026

## Operación

Liquidaciones tiene cinco pestañas: vendedores, **Estado de cuenta**, META mensual,
plataforma e historial. Desde **Detalle y conciliación**:

1. Preparar el período y seleccionar emisiones como antes. Los importes quedan fijados.
2. Registrar abonos parciales con banco, cuenta receptora completa, fecha, operación,
   importe, detalle y PDF/PNG/JPEG (hasta 5 MB).
3. Presentar aunque exista saldo. Administración puede aprobar la revisión sin
   certificar todavía que el dinero esté recibido.
4. Administración **concilia cada movimiento contra banco**. Adjuntar una imagen
   no confirma dinero. No existe conexión automática con bancos.
5. Cerrar solo con saldo de depósito cero y todos los movimientos verificados.
   Se genera una constancia PDF en la central documental, conservada al cierre.
6. Registrar y conciliar el pago de comisión por separado, incluso después del
   cierre. La constancia anterior informa la comisión pendiente en ese momento.

Una compensación de comisión requiere permiso administrativo, acuerdo adjunto y
conciliación explícita. Reduce tanto el saldo a depositar como la comisión pendiente.
Nunca se descuenta automáticamente: se conserva la regla de depósito directo/AFOCAT.
No admite importes que superen el depósito o la comisión disponible; los movimientos
pendientes de verificar también reservan saldo para evitar duplicados simultáneos.

El vendedor prepara, presenta y carga depósitos de su ámbito. Solo administración
con permiso gestor verifica, registra pagos/compensaciones, aprueba y cierra.
Retirar un movimiento verificado requiere administración y motivo; se conservan
su archivo y auditoría. Antes de cancelar deben retirarse los movimientos activos.
Un cierre no se reabre ni modifica sus depósitos. Una comisión ya pagada y verificada
tras el cierre también queda protegida; los ajustes posteriores requieren un flujo
específico futuro, no editar importes cerrados.

## Saldos e históricos

Estado de cuenta distingue ventas emitidas, cobros pendientes del cliente,
depósitos/comisiones sin liquidación, saldo de liquidaciones V2, depósitos conciliados,
comisiones pagadas/compensadas y movimientos por verificar. Es acumulado, paginado y
buscable por vendedor. Los estados de cuenta incluyen únicamente su ámbito comercial.

Las liquidaciones importadas se mantienen en consulta, incluidos adjuntos y estados.
No se deduce una conciliación bancaria a partir de una migración. Se informa su
cantidad aparte y se excluyen de los saldos de liquidaciones nuevas. Las ventas
disponibles no vinculadas a una liquidación conservan las reglas comerciales existentes.
AFOCAT continúa apuntando al Laravel: estos saldos no sustituyen el corte y conciliación
de históricos pendiente. No se cambiaron configuración fiscal, series ni conectores.

## Datos, integridad y consultas

Migración 0013 agrega campos a `medical_vouchers`: propósito, banco/cuenta, detalle,
fecha y usuario de verificación. **No crea tablas** ni otro libro de pagos.
`active_reference` conserva su índice único, ahora con SHA-256 de banco normalizado,
cuenta sin separadores, fecha y operación. El archivo conserva deduplicación SHA-256.
Una referencia antigua sin datos bancarios sigue siendo ambigua y bloquea reutilización.
Las compensaciones tienen identidad propia por liquidación y referencia del acuerdo.

Todas las mutaciones bloquean primero la liquidación. Límites incluyen movimientos
activos verificados y pendientes; índices únicos resuelven carreras entre liquidaciones.
Las rutas históricas rechazan también altas y retiradas de constancias.
En errores de escritura se elimina únicamente el archivo nuevo; los originales y
constancias retiradas permanecen referenciados para auditoría.

El listado agrega los movimientos de la página en una consulta agrupada. El detalle
reutiliza los movimientos ya cargados para calcular saldos. Estado de cuenta agrega
ventas y liquidaciones por vendedor, limitado a la página, sin consultas por fila.
La prueba de consultas confirma que aumentar liquidaciones no aumenta su número.
El navegador conserva catálogos al registrar/conciliar y recarga solo detalle/listado;
estado de cuenta se consulta al abrir su pestaña y permite actualizar explícitamente.

## Comprobación de publicación

Preflight remoto: 7 liquidaciones históricas, 0 nativas, 0 partidas/constancias
huérfanas, 0 archivos de constancias sin referencia y 0 faltantes. No se eliminan
tablas o archivos históricos por suposición de desuso.

Pruebas aisladas cubren abonos, banco/cuenta/fecha/operación, límites, duplicados,
compensaciones, comisiones posteriores al cierre, constancia, permisos, históricos
y consultas constantes. La prueba de navegador local simula movimientos: no genera
depósitos, ventas ni mensajes reales. Verificación productiva de consulta y salud
tras publicar; nunca se concilia dinero real como parte de las pruebas.

## Actualización 15/10/2026

Por solicitud expresa, Oficina Principal puede aprobar y cerrar también liquidaciones históricas de vendedor con voucher completo mediante /settle y motivo auditado. La edición histórica sigue bloqueada. [Lista unificada, períodos y fechas](LISTA_Y_APROBACION_LIQUIDACIONES_20261015.md).
