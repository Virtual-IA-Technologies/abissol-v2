# Facturación automática SUNAT — 05/10/2026

## Acceso y operación

Facturación tiene pestañas Comprobantes y Configuración · Programador. La segunda
se monta solo para el rol activo Programador. GET/PUT de configuración y la revisión
de la cola también exigen ese rol en servidor, además del permiso de menú gestor.
Administrador por sí solo no obtiene acceso. Claves SOL y PFX nunca se devuelven;
campos vacíos conservan los secretos cifrados. Cambios auditados sin contraseñas.

Cuando `enabled_in_v2` está activo, registrar una nueva emisión crea una boleta y trabajo
fiscal dentro de la misma transacción. El cobro conserva su estado pendiente o
confirmado y no se considera pagado por generar el comprobante. Confirmar el pago
posteriormente actualiza su estado comercial sin duplicar ni regenerar la boleta. No se emiten comprobantes de históricos
importados ni se hace relleno automático de ventas anteriores a la activación.

Numeración exclusiva V2: configuración bloqueada con SELECT FOR UPDATE, correlativo
monótono, unicidad en la cola por entorno/serie/número y una boleta por emisión.
Las series importadas (incluida B001) siguen reservadas al sistema Laravel activo.
No cambiar RUC, entorno ni serie una vez que existan trabajos. No editar contadores
desde la interfaz. La elección de nueva serie o corte de Laravel requiere decisión
del usuario; inicialmente el envío permanece desactivado, sin serie asignada.

## Distribución cotejada con app.abissol.org

La fábrica Laravel local y la del servidor tienen el mismo SHA-256:
`b1f9a58292be5e94452476fca29aa4c7d97ef3aefb90160ef266a7dfd19537f2`.

| Plan | Meta Assistance | Admisión | Mantenimiento | Total |
| --- | ---: | ---: | ---: | ---: |
| Hampi Esencial | 12.00 | 43.00 | 0.00 | 55.00 |
| Hampi Plus | 199.00 | 43.00 | 13.00 | 255.00 |

Se reproduce el tratamiento configurado por ABISSOL: inafecto, afectación 30,
tributo 9998 / INA / FRE, IGV cero. No confundir distribución fiscal con comisiones:
vendedor 15/25, plataforma 0.50/1.00 y META 10% sobre costo proveedor, según planes
actuales. La implementación conserva esta configuración; no constituye una nueva
determinación tributaria. Precios distintos o planes no reconciliados bloquean la
boleta para impedir que el detalle no cuadre con el importe de venta.

## Envío y conservación

UBL 2.1, personalización 2.0, operación 0101, boleta 03, moneda PEN, domicilio,
documento del titular, contado, leyenda 1000, ítems, totales y firma XMLDSig.
Firma RSA-SHA1/C14N como Laravel y manual, con certificado PFX privado conservado.
Validación de vigencia, clave RSA, integridad del archivo y RUC del certificado.
ZIP con XML firmado, nombre RUC-03-SERIE-NUMERO; PDF con representación impresa,
desglose, monto en letras, hash y QR. Archivos privados con descarga autenticada,
alcance comercial y verificación SHA-256. Beta se identifica sin validez tributaria.

SOAP `sendBill`, HTTPS con verificación TLS y WS-Security UsernameToken. Endpoints
fijos oficiales; no aceptar URLs arbitrarias para enviar credenciales. Worker
`scripts/fiscal_worker.py`, servicio/timer `abissol-v2-fiscal`, cada minuto, instancia
única systemd. `medical_fiscal_jobs` (migración 0006) conserva estado y número.

Antes de contactar SUNAT se confirma en base el intento y se conservan XML/ZIP/PDF.
Después de timeout o reinicio solo se consulta `getStatusCdr`, sin regenerar XML ni
reenviar a ciegas. CDR debe coincidir en RUC y número; código 0 acepta, los demás
rechazan. Un error previo al envío queda bloqueado para revisión del Programador.
Una recepción incierta se consulta cada cinco minutos. La ventana operativa de
primer envío admite hoy y ayer para cubrir colas que crucen medianoche; retrasos
mayores se bloquean para revisión, sin cambiar fecha/número. Es una política
conservadora del piloto, no una declaración del plazo máximo normativo.
No se reenvían rechazados; notas de crédito, débito y bajas nuevas quedan fuera
de este flujo de boletas. Se conserva consulta del historial importado.

## Verificación y fuentes

- Pruebas aisladas: permisos Programador vs Administrador; pago/idempotencia y
  correlativos; firma criptográfica verificable; ZIP, montos, rechazo y CDR de otro
  emisor/número; timeout recuperado sin segundo envío ni modificación del XML.
- XSD Invoice UBL 2.1 oficial OASIS: válido. Descarga del ZIP SUNAT devolvió HTTP 403;
  se usó el esquema original OASIS (14 XSD) solo para validación local.
- SUNAT Beta aceptó una boleta ficticia BV99-1 con código 0, sin observaciones,
  credenciales públicas de prueba y certificado sintético. No se enviaron clientes
  ni credenciales reales ni se emitieron documentos tributarios de producción.
- Certificado ABISSOL cotejado privadamente: integridad y RUC correctos, vigente
  hasta 03/07/2029. Contrato del CDR contrastado con uno aceptado del historial.
- Conexión real de producción verificada mediante `getStatusCdr` de una boleta
  histórica propia: código 0 y coincidencia con el registro original. Solo se
  transmitieron RUC emisor, tipo, serie y número; sin datos del cliente ni nuevos
  comprobantes. Configuración completa excepto elección de serie exclusiva V2.
- TypeScript, lint, pruebas comerciales y navegación local escritorio/móvil.

Manual adjunto del usuario: `D:\TRABAJO\AFOCAT.PE\Manual SUNAT.pdf`, mayo 2021,
54 páginas; referencia técnica, no fuente de autorizaciones operativas.
Contrastado con [Guías y manuales SUNAT](https://cpe.sunat.gob.pe/guias-y-manuales),
[alcance de Beta](https://cpe.sunat.gob.pe/noticias/servicio-beta-para-realizar-pruebas-ubl-21)
y [esquema UBL 2.1](https://docs.oasis-open.org/ubl/os-UBL-2.1/xsd/maindoc/UBL-Invoice-2.1.xsd).
Beta confirma estructura, no homologación fiscal ni aceptación futura en producción.
