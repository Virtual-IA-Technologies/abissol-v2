# Central documental por afiliado — 12/10/2026

Estructura: **ABISSOL → Afiliados → NOMBRE · TIPO DOCUMENTO NÚMERO → CERTIFICADO**. La carta se encuentra dentro de la emisión; cada comprobante vinculado tiene una subcarpeta con su numeración y PDF, ticket, XML, ZIP y CDR disponibles.

La identidad de carpeta depende de tipo y número de documento del afiliado, no de su nombre ni del adquirente de una factura. Los homónimos no se mezclan y las renovaciones comparten afiliado, con certificados separados. El RUC de una empresa compradora no cambia la carpeta del titular del programa.

Incluye documentos automáticos y originales importados con relación expresa mediante LegacyRecord. Documentos sin vínculo seguro no se reasignan por coincidencia de nombre. Liquidaciones con varias emisiones y condiciones generales conservan sus carpetas comunes.

`organize_affiliates` modifica solamente folder_id/fecha/revisión del documento. Conserva identidades, vínculos, propietario, comparticiones, versiones, hashes y binarios. No borra ni duplica documentos. Las carpetas de sistema vacías quedan fuera del árbol visible por no contener documentos autorizados.

El sincronizador `scripts/sync_medical_documents.py --expected-database abissol_v2` realiza la reorganización idempotente antes de completar archivos; la publicación habitual ya invoca este comando. La nueva emisión y los nuevos comprobantes usan la misma estructura automáticamente.

Pruebas: separación de homónimos por documento, identidad estable ante corrección de nombre, factura empresarial ubicada bajo afiliado, movimiento de originales históricos sin ampliar permisos ni recrear versiones y segunda ejecución sin cambios. Se conservan las pruebas de archivos privados y restricciones de documentos de sistema.

Publicación autorizada junto con la impersonación en main y V2. El gateway histórico se conserva como trabajo separado.
