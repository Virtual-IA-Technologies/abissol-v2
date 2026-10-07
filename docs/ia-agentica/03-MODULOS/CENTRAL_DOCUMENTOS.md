# Central de documentos ABISSOL

## Uso

En **Documentos → Archivos**, el árbol distingue **Mis archivos** de **Documentos
de ABISSOL**. Esta última ubicación contiene las carpetas automáticas:

- **Emisiones / año / mes / programa**: certificado o carta de bienvenida.
- **Facturación / año / mes / comprobante**: PDF A4, ticket histórico si existe,
  XML firmado, ZIP y CDR disponibles.
- **Liquidaciones / año / mes / liquidación**: constancias de depósito; carta
  mensual META y libro Excel cuando corresponde.
- **Planes y condiciones / plan**: condiciones históricas disponibles.

Las carpetas solo se crean cuando hay un archivo. Los documentos personales e
importados que ya estaban en Archivos conservan sus carpetas, propietarios y
comparticiones. Buscar filtra los documentos autorizados; buscar dentro de una
carpeta incluye sus descendientes. Doble clic abre el visor y el menú permite
consultar detalle, versiones y descargar el original.

PDF e imágenes utilizan el visor existente. XML se presenta como texto, nunca
como HTML ejecutable. DOCX y XLSX tienen vista local en el navegador, sin enviar
los documentos a Microsoft. XLSX muestra hasta diez hojas, 200 filas y 50 columnas
por hoja; descargar conserva el archivo completo. Los ZIP/CDR comprimidos se
descargan para abrir su contenido. No se modifica un comprobante para previsualizarlo.

Los documentos automáticos se administran desde su módulo de origen. No admiten
subidas manuales a sus carpetas, movimientos, renombrado, sustitución, papelera,
copias personales dentro de la central ni nuevos enlaces públicos. Los archivos
personales mantienen sus operaciones habituales.

## Permisos y procedencia

Patrón adaptado del archivo central de Virtual.IA, estudiando su código local y
ADR-0025; no se transfieren archivos, datos ni secretos de ese proyecto.
Lectura exige acceso a Documentos, permiso vigente al módulo de origen y alcance
del registro comercial. El responsable técnico del archivado no otorga acceso.
Revocar el permiso del módulo retira también listado, carpetas y descarga directa.
Las condiciones de planes son legibles con acceso a Planes o Emisiones.
Ningún proceso recorre archivos arbitrarios del servidor para publicarlos.
La lista permitida de artefactos fiscales excluye configuración, claves SOL,
certificados PFX y contraseñas. Los originales históricos se validan por SHA-256.

## Implementación

Migración `0012_document_archive`: `document_folders.system_key`,
`documents.is_system` y `document_bindings`. Identidad única del archivo:
`source_type + source_id + artifact_key`; cada documento tiene versiones
inmutables. Igual hash no crea otra versión. Una versión fiscal nueva se archiva
cuando cambia el contenido; recibir el CDR añade su artefacto sin duplicar XML/PDF.

`medical_documents.py` integra emisiones internas/externas, comprobantes,
constancias y nuevas liquidaciones META en la transacción de origen. Archivo
central y flujo comparten commit; un rollback elimina los nuevos binarios centrales.
La copia usa bloques de 1 MiB o hardlinks del mismo volumen a fuentes inmutables.
La escritura fiscal ya reemplaza sus archivos de forma atómica, conservando los
inodos de versiones anteriores. El historial no depende de conservar una ruta
de origen que pueda ser reemplazada.

Listado, búsqueda y descargas reutilizan la misma consulta de autorización.
El árbol usa CTE recursiva desde los archivos visibles y solo muestra sus ancestros,
sin consultas por archivo ni carpetas de expedientes ajenos. Los documentos
administrados quedan fuera de retención/papelera personal. No se indexa su texto
automáticamente ni se realizan consultas a servicios externos al navegar.

Incorporar históricos desde BackEnd:

```powershell
.\.venv\Scripts\python.exe scripts/sync_medical_documents.py --expected-database abissol_v2_local
```

En servidor se exige `--expected-database abissol_v2`. El despliegue lo ejecuta
después de migrar. Es repetible: no numera, no transmite a SUNAT, no envía mensajes
y no altera ventas/importes históricos. Informa archivos ausentes sin fabricarlos.
Las cartas de emisiones V2 se generan una sola vez con el QR de verificación del
dominio productivo. Las mensuales se obtienen de los ítems fijados en la liquidación.
Respaldar conjuntamente la base y `storage/documents`/almacenamientos originales.

## Verificación de esta entrega

- Seis pruebas de negocio y diez fiscales aprobadas con base/archivos temporales.
- Cinco pruebas específicas: certificado automático, invariantes de carpetas,
  alcance/revocación incluso con URL conocida, versiones por hash, rollback y
  conservación de edición de archivos personales y versiones ante reemplazo del original.
- Migración local y `alembic check` sin diferencias; local no contiene documentos
  de negocio para incorporar (cero vínculos nuevos, sin originales faltantes).
- TypeScript y ESLint de los componentes modificados; prueba de navegador con
  carpetas, XML y XLSX de muestra, incluyendo pantalla móvil. La verificación sobre los originales productivos
  se realiza al publicar; los conteos finales se informan en el cierre.
