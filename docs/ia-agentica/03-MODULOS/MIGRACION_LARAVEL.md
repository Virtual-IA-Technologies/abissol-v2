# Migración de ABISSOL Laravel

Autorizada el 05/10/2026: datos reales de app.abissol.org a v2.abissol.org.
Origen exclusivo `abissol_laravel`; destino exclusivo `abissol_v2` en servidor alp.
No altera Laravel, SISAP ni el conector de AFOCAT La Primera.

## Alcance y correspondencias

- Usuarios: todas las cuentas, nombre completo, usuario/correo y hash bcrypt compatible.
  La cuenta ya existente en V2 se enlaza por correo, conservando su contraseña,
  nombre de acceso, estado y permisos. No se envían credenciales ni notificaciones.
- Teléfonos compartidos: se conservan como contacto, sin convertirlos en un
  identificador ambiguo de acceso. Acceso por usuario o correo y contraseña anterior.
- Usuarios se consultan en Usuarios y seguridad → Usuarios. Red comercial conserva
  origen, ID externo, responsable, emisores y estado activo/retirado; no duplica cuentas.
- Roles comerciales mínimos por función; coordinador de origen sin ámbito global.
  Superadmin/Programmers → Programador; Administrador → Administrador. Los restantes
  roles administrativos sin equivalencia conservan su nombre con prefijo Legado y
  acceso básico Usuario, sin inventar permisos sobre módulos distintos.
- Emisiones: certificados, tokens, fechas, responsables/emisores, cobros y snapshots
  monetarios. `pending_payment` de Laravel se normaliza a `issued` en V2 conservando
  `legacy_status` y el estado de cobro independiente; la anulación se conserva.
- Planes: código, series/correlativos, precios, comisiones y vigencia reales. El seed
  reconoce códigos con guion/guion bajo y no vuelve a crear planes de plantilla.
- Liquidaciones, partidas y depósitos históricos conservan cantidades y estados;
  las liquidaciones importadas se consultan sin transiciones del flujo simplificado V2.
  Los ítems activos impiden volver a liquidar una misma emisión/tipo.
- Comprobantes: admite múltiples comprobantes y notas por emisión, además de
  registros independientes/archivados. Conserva números, fechas, clientes, importes,
  estados fiscales y de pago, 96 partidas y logs SUNAT. Historial con archivos
  originales PDF, ticket, XML, ZIP y CDR según disponibilidad.
- Documentos: versiones originales en Archivos, propietarios conservados y acceso
  de consulta explícito al administrador operador. Conserva estado de papelera.
- Comunicaciones: historial de emisiones, liquidaciones y envíos generales. No se
  reenvían comunicaciones importadas.
- Configuración fiscal: datos del emisor, seis series, credenciales y certificado
  conservados privadamente. Facturación muestra solo campos autorizados y existencia
  de secretos. **V2 no envía a SUNAT ni genera numeración fiscal nueva.** La activación
  del emisor electrónico requiere implementación/validación posterior.

## Seguridad y ejecución

`0005_legacy_abissol` amplía el esquema V2 sin modificar datos de origen.
`BackEnd/scripts/import_legacy_abissol.py` opera solo en Linux sobre `abissol_v2`.
La instantánea se obtiene en transacción de lectura consistente, fuera de public_html.
Simulación por defecto y rollback; `--apply` confirma en una transacción y audita
cantidades. No hay envío de correo, WhatsApp ni SUNAT en el importador.

Las filas originales quedan cifradas mediante SECRET_KEY en `legacy_abissol_records`,
con checksum, tabla/ID original e ID de destino. No se exponen por API. Repetir la
misma instantánea no duplica registros ni reescribe contraseñas/perfiles. Una
instantánea modificada falla para exigir conciliación, no sobreescritura silenciosa.

El importador valida cantidades, referencias e importes por registro antes de commit.
Los archivos se copian dentro del servidor, con rutas confinadas, nombre interno y
SHA256. Los certificados y claves no están en public_html ni en GitHub. Las descargas
comerciales aplican permiso de menú y ámbito de emisión/liquidación/comprobante.

Respaldos privados: `/home/abissol/apps/abissol-v2/backups/legacy-import/`:
`laravel.sql.gz`, `laravel-storage.tar.gz`, `v2-before.sql.gz`, `snapshot.json`.
No descargar estos archivos al repositorio. Rollback de datos mediante restauración
controlada del respaldo, nunca downgrade destructivo de tablas históricas.

## Conciliación de la instantánea

69 usuarios, 64 fichas de vendedor, 3 orígenes, 2 planes, 9 emisiones (8 emitidas,
1 anulada), 7 liquidaciones, 12 partidas, 4 depósitos, 27 comunicaciones,
43 comprobantes, 96 partidas fiscales, 50 logs SUNAT y 273 documentos.
Una cuenta coincide con la administradora V2; su clave actual se conserva.

Ventas activas S/ 840.00; emisión anulada S/ 55.00; total histórico S/ 895.00.
Suma de comprobantes S/ 4,965.00 únicamente para cotejar filas: incluye notas de
crédito y archivados, **no representa ingresos netos**.

254 rutas de archivo disponibles; cuatro referencias ausentes pertenecen al
comprobante legado 29, archivado. Tampoco existen en los almacenamientos del origen;
no se regeneran para fingir originales. El detalle fiscal muestra la ausencia.

La importación es una instantánea, no una sincronización continua. La recepción
externa de AFOCAT sigue apuntando a Laravel. Antes del corte definitivo hay que
conciliar movimientos posteriores y activar el conector V2 autenticado por entidad.
Los QR de PDF antiguos conservan su URL original; sus tokens también se reconocen
en el verificador V2. No retirar el verificador anterior durante el piloto.

## Validación

27 pruebas backend: plataforma, permisos comerciales, documentos, facturación,
navegación y tres pruebas de migración con datos sintéticos. Estas últimas verifican
compatibilidad bcrypt `$2y$`, clave administradora preservada, nombres largos,
teléfonos compartidos, importación repetible, conciliación, conflicto de instantánea,
aislamiento fiscal, secretos ocultos y archivos privados sin escapes de ruta.
MariaDB local: migración aplicada y Alembic sin diferencias. Carga remota aplicada:
cantidades e importes conciliados, 254 archivos cotejados por SHA256 y segunda
ejecución con rollback sin nuevas filas. Una auditoría de importación conservada.
Piloto HTTPS verificado: siete opciones comerciales, Usuarios, nueve cartas PDF
originales y archivos fiscales. Series A/B editables; comprobantes bancarios históricos
no pueden reutilizarse en nuevas liquidaciones, aunque sus claves de unicidad sean nulas.
Estado de publicación en ESTADO_ACTUAL.md.
