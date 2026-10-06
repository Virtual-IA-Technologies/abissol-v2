# Pestañas comerciales — 06/10/2026

Referencia: Laravel productivo `/home/abissol/public_html/api.abissol.org`, cotejado
por SSH. El controlador de emisiones y el servicio de liquidaciones diferían de
la copia local; se usaron las versiones del servidor. No se modificó Laravel.

## Emisiones

1. **Emisiones:** alta, consulta, cartas, cobro, anulación y resumen de afiliaciones
   con filtros de vigencia calculados en Lima, dentro del alcance autorizado.
2. **Envíos:** comunicaciones de afiliados, historial y reintentos individuales.
3. **Envíos META:** pendientes, enviadas, fallidas y recepción por confirmar;
   búsqueda/fechas de venta, selección paginada, Excel y envío confirmado.
4. **Vendedores:** red comercial, responsables/emisores, orígenes y vínculo con
   cuentas reales de Usuarios. Reutiliza el módulo existente, sin duplicar fichas.
5. **Planes:** importes, comisiones, vigencia y condicionado del catálogo existente.
6. **Configuración:** correo META, hora diaria de referencia y plantillas de
   afiliados. Solo Programador; SMTP/Wablas conservan sus pestañas en Comunicaciones.

Las plantillas aceptan `{nombre}`, `{plan}`, `{certificado}`, `{inicio}`, `{fin}`,
`{enlace}` y `{condicionado}`. Una plantilla vacía usa la bienvenida predeterminada.
La hora se conserva de Laravel, pero **no se activa un envío programado**: enviar
requiere confirmación en la interfaz. No se habilita OTP ni se reenvía la historia
migrada automáticamente.

## Liquidaciones

- **Liquidaciones:** vendedor responsable, período, vista previa, selección de
  emisiones, comprobantes y conciliación existentes.
- **Liquidaciones mensuales:** consolidado META de todos los vendedores; incluye
  altas pendientes de cobro como Laravel. Vista previa/selección, Excel y carta
  PDF; envío a los destinatarios META configurados con confirmación.
- **Liquidación plataforma:** consolidado de todos los vendedores y comisiones
  de plataforma, con vista previa/selección y conciliación.
- **Historial:** consulta conjunta, búsqueda y fechas, detalle y archivos; sin
  acciones de generación ni cambio de estados.

El depósito de vendedores directos es el importe cobrado. Para responsables de
origen AFOCAT es el costo proveedor, según `isAfocatManaged` del servidor. Los
pagos directos a ABISSOL no vuelven a exigirse al vendedor. Comisiones informativas
se conservan separadas; META usa la comisión META y plataforma su comisión propia.
Los importes históricos importados no se recalculan. Las emisiones se bloquean al
generar y `active_key` impide incluirlas dos veces en el mismo tipo de liquidación.

## Integridad y permisos

Pestañas con línea inferior, teclado y URL `?tab=...`; visibilidad según permisos.
META y consolidados requieren acceso global además del permiso del módulo. Las
consultas de vendedores conservan su alcance. No basta ocultar la pestaña: la API
valida perfil/rol, selección, período y pertenencia de los registros.

Los intentos META se guardan **antes** de SMTP. Un intento incierto se registra
sin reintento automático; duplicados o reenvíos requieren `force` confirmado.
Un envío en curso bloquea el segundo intento. El reintento individual de afiliados
no puede convertir un reporte META en una bienvenida. El XLSX usa celdas de texto
para preservar ceros del documento y evitar ejecutar fórmulas.

Migración `0007_business_settings`: solo tabla de ajustes comerciales. Importador
`scripts/import_legacy_business_settings.py` lee cuatro claves autorizadas del
Laravel, crea respaldo privado y auditoría, sin transportar secretos al repositorio.

## Verificación

Pruebas aisladas: vista previa sin escritura, selección/duplicados, tipos, depósito
AFOCAT, altas no cobradas, formatos XLSX/PDF, plantillas, permisos y SMTP simulado.
Regresión del flujo comercial existente y conciliación de comprobantes.
Comprobación de esquema local mediante Alembic. La revisión de navegador recorre
las seis/cuatro pestañas, vista previa sin generar, selector buscable y móvil.
Durante estas verificaciones no se envían mensajes ni se crean liquidaciones reales.
