# Revisión para reemplazar Laravel · 09/10/2026

**Resultado: todavía no apto para retirar Laravel sin perder funcionalidad.**
La navegación V2 funciona, pero existen diferencias funcionales y operaciones
históricas abiertas. Esta revisión no activa facturación ni cambia AFOCAT.

## Evidencia y límites

- Inventario de rutas obtenido del Laravel productivo mediante `route:list`.
- Contraste de controladores del original y rutas, servicios e interfaz de V2.
- Navegador autenticado sobre HTTPS V2: recorrido de páginas, pestañas,
  redirecciones, vista previa mensual, carta/QR y documentos. No se emitieron
  ventas ni se enviaron mensajes, archivos a META o comprobantes a SUNAT.
- El original se contrastó por rutas y controladores; no se reprodujeron todas
  sus acciones con una sesión de navegador. Una página que carga no demuestra
  que una operación externa termine correctamente.
- Datos sincronizados puntualmente el 09/10: 10 emisiones, 44 comprobantes,
  7 liquidaciones originales. No existe sincronización continua.
- Los intentos iniciales de pruebas locales sufrieron falta de memoria y
  restricciones de temporales. No se cuentan como pruebas aprobadas.
- Reejecución focalizada completada: **21 pruebas aprobadas** de identidad
  comercial, liquidaciones, facturación y documentos/información (108 s), con
  SQLite y proveedores simulados. Los errores de auditoría inyectados forman
  parte de las pruebas de rollback, no son fallos del resultado final.
- Pestaña fiscal productiva verificada: carga diferida, secretos en blanco,
  selector buscable, vista móvil y cero cambios de configuración.
- Conector AFOCAT: validación productiva de prueba con rollback aprobada;
  cantidades y correlativos sin cambios, cero trabajos fiscales y cero mensajes.
  Alembic sin diferencias y endpoint de disponibilidad correcto.
- Sesiones temporales de auditoría revocadas y cookie privada eliminada.

## Recorrido de opciones de negocio

| Opción V2 | Revisión | Paridad / pendiente |
| --- | --- | --- |
| [Emisiones](https://v2.abissol.org/plataforma/medical/emissions) | Lista y filtros cargan; cambiar filtro no repite lookups. | Falta edición de datos de una emisión sin comprobante, disponible en Laravel. |
| Nueva emisión | Backend compartido para portal/conector, vigencia desde mañana y tarifas por participante. | Prueba final de negocio interna/externa pendiente antes del corte; no crear ventas reales durante esta auditoría. |
| Carta y QR | Descarga privada y pública devuelven el mismo PDF; logos y vista móvil correctos. | No sustituye una aprobación visual de todos los diseños y casos. |
| Consulta pública | Verificador por token y descargas disponibles. | Falta equivalente de `medical/public/search` por código/DNI del original. |
| [Envíos](https://v2.abissol.org/plataforma/medical/emissions?tab=dispatches) | Pestaña e historial cargan. | Envío real correo/WhatsApp no ejecutado en esta revisión. Históricos no admiten reintento directo. |
| [Envíos META](https://v2.abissol.org/plataforma/medical/emissions?tab=meta) | Pestaña carga; existen exportación y envío. | Validación final del destinatario y archivo con negocio pendiente; no enviar por probar. |
| [Vendedores](https://v2.abissol.org/plataforma/medical/emissions?tab=network) | Carga, comparte Red comercial. | Carmen responsable e Inés emisora dependiente ya configuradas. |
| [Planes](https://v2.abissol.org/plataforma/medical/emissions?tab=plans) | Pestaña y catálogo cargan. | No duplicar opción independiente; prefijos/correlativos requieren decisión de corte. |
| [Configuración general](https://v2.abissol.org/plataforma/medical/emissions?tab=settings) | Carga y acceso Programador. | Mantener restricción por backend. |
| [Correo](https://v2.abissol.org/plataforma/medical/emissions?tab=settings&channel=email) | Enlace antiguo redirige al panel correcto. | Recepción real con destinatario autorizado pendiente de ensayo final. |
| [WhatsApp](https://v2.abissol.org/plataforma/medical/emissions?tab=settings&channel=whatsapp) | Enlace antiguo redirige al panel correcto. | Confirmación real del proveedor pendiente; OTP sigue excluido por decisión del usuario. |
| [Red comercial](https://v2.abissol.org/plataforma/medical/network) | Carga; cuentas y perfiles diferenciados. | La dependencia no es una entidad sucursal con domicilio propio: es responsable → emisor. |
| [Liquidaciones](https://v2.abissol.org/plataforma/medical/liquidations) | Lista, formulario, selector buscable y permisos disponibles. | Seis históricas abiertas no pueden continuar su flujo en V2. |
| [Estado de cuenta](https://v2.abissol.org/plataforma/medical/liquidations?tab=accounts) | Pestaña adicional y lectura verificadas. | Mejora sobre las cuatro pestañas originales. |
| [Liquidaciones mensuales](https://v2.abissol.org/plataforma/medical/liquidations?tab=meta) | Formulario y vista previa sin persistencia correctos. | Revisar equivalencia de carta/Excel META y cierre de pendientes originales. |
| [Liquidación plataforma](https://v2.abissol.org/plataforma/medical/liquidations?tab=platform) | Pestaña carga. | No se confirmó un pago real ni cambio de estado durante la auditoría. |
| [Historial](https://v2.abissol.org/plataforma/medical/liquidations?tab=history) | Carga y no muestra alta de liquidación. | La consulta histórica no equivale a continuidad operativa. |
| [Comprobantes](https://v2.abissol.org/plataforma/medical/billing) | Lista, detalle, archivos e interfaz de correo cargan. | Notas 07/08, anulación fiscal, CDR histórico y otras operaciones originales pendientes. |
| Configuración fiscal · Programador | Implementada con claves ocultas, series V2 y modo de pruebas. | No hay series productivas V2 definidas. Falta carga/renovación de certificado y logo fiscal equivalente al original. |
| [Reportes](https://v2.abissol.org/plataforma/medical/reports) | Página carga. | No certificar equivalencia de todos los indicadores/exportaciones originales solo por esta lectura. Exportación genérica V2 es de la página visible. |
| [Archivos](https://v2.abissol.org/documentos/archivos) | Carpetas Emisiones/Facturación/Liquidaciones; PDF, XML y XLSX visualizados en producción; vista móvil correcta. | Cuatro archivos ausentes del comprobante histórico archivado 29 tampoco existen en origen. |

## Plataforma y enlaces

Recorrido autenticado sin errores JavaScript ni HTTP fallidos: Usuarios, Roles,
Accesos, Menús, Auditoría, Calendario, Notificaciones, Documentación, DevOps,
AVI, Apariencia, Configuración general y Plantillas, además de Red comercial,
Facturación, Reportes y Archivos. No se ejecutaron acciones administrativas
destructivas ni pruebas reales de proveedores.

Redirecciones verificadas: `/plataforma/medical/plans`,
`/plataforma/medical/dispatches`, `/plataforma/sistema/configuracion/smtp` y
`/plataforma/sistema/configuracion/whatsapp`, hacia sus pestañas actuales.
Resultado del recorrido: 17 páginas adicionales, 4 redirecciones, cero errores.
Pestañas de negocio verificadas: 6 de emisiones y 5 de liquidaciones.

## Brechas concretas respecto al original

1. **Facturación:** Laravel expone `credit-note`, `debit-note`, `cancel`,
   `query-cdr`, alta independiente de comprobantes, administración de series y
   carga de certificado/logo. V2 conserva históricos y genera boleta/factura
   asociada a emisión, pero no implementa toda esa operación. Su revisión SUNAT
   depende de una cola V2: el comprobante importado B001-00000022 no tiene esa
   cola y no puede recuperarse desde el botón de revisión actual.
2. **Liquidaciones abiertas:** producción contiene cuatro `pending`, dos `sent`
   y una `cancelled` importadas. El backend rechaza transiciones para
   `legacy_id`. Hay que habilitar una continuidad conciliada o cerrar las seis
   en Laravel antes del corte. Laravel también permite modificar ítems de una
   liquidación existente; no hay acción equivalente V2 posterior al alta.
3. **Corrección de emisiones:** Laravel permite editar titular/contacto,
   vigencia y pago antes de asociar comprobante. V2 permite confirmar cobro,
   pero no esa edición. La anulación V2 se bloquea si hay comprobante o cobro;
   necesita un flujo coherente con nota fiscal y devolución, no quitar el bloqueo.
4. **Consulta pública:** preservar QR existentes y añadir equivalencia segura
   de la búsqueda original por código/DNI; no publicar información adicional.
5. **Integración externa:** ALP productivo sigue en Laravel. La API V2 y el
   adaptador están preparados, pero `/abissol-pruebas/` es únicamente el canal
   de ensayo. No basta cambiar la URL: exige selección fiscal previa, token por
   origen, identidad de vendedores e idempotencia.
6. **Numeración y cierre:** V2 está en pruebas, envío SUNAT desactivado y sin
   series boleta/factura configuradas. Definir series propias, o implementar un
   corte exclusivo para continuar anteriores. No compartir correlativos entre
   dos sistemas ni retrocederlos. Conciliar también prefijos de programas.
7. **Datos finales:** repetir conciliación incremental justo antes del corte,
   preservando cuentas nativas V2, Inés, permisos y documentos. El snapshot
   del 09/10 no incorpora automáticamente operaciones posteriores.

## Orden recomendado para el corte

1. Resolver brechas funcionales y seis liquidaciones históricas abiertas.
2. Validar boleta/factura y correcciones fiscales, PDF A4/ticket, carta/QR,
   correo/WhatsApp y entregables META con datos controlados y destinatarios
   autorizados. Aprobación visual de formatos por el usuario.
3. Definir series/prefijos y preparar respaldo, conciliación final, cambio ALP
   y retorno seguro de configuración. Mantener verificadores antiguos activos.
4. Finalizar pruebas, activar fiscal cuando SUNAT permita comprobar el flujo y
   verificar CDR de una operación autorizada. La auditoría no realizó envíos.
5. Dejar Laravel en consulta después del corte, evitando emisión simultánea.

No se debe anunciar paridad completa ni cierre de migración antes de resolver
estas diferencias y comprobar los flujos externos de extremo a extremo.
