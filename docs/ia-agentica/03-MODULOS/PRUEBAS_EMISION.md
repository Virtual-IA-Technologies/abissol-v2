# Pruebas internas y externas sin numeración real

El Programador puede activar/finalizar el modo en Facturación / Configuración.
Activar crea un lote `PRUEBA-…` y desactiva el envío fiscal. Finalizar conserva el
envío fiscal desactivado: nunca se reactiva automáticamente.

Durante el modo, todas las emisiones NUEVAS de V2 (portal y API externa) llevan
`medical_issuances.test_batch`, código aleatorio `PRUEBA-…` y comprobante de muestra
`TB00-…` o `TF00-…`. No se incrementa el contador del plan ni los contadores fiscales.
Los identificadores técnicos autoincrementales siguen siendo únicos; no son los
correlativos comerciales y no deben reiniciarse después de borrar pruebas.

Se generan carta/QR, PDF A4, ticket, XML sin firma y ZIP de muestra, conservando la
distribución de montos y las reglas de vigencia. Todos se identifican como prueba.
No se firma, no se crea FiscalJob ni CDR y no se llama a SUNAT (ni Beta). El bloqueo
permanece en cada registro después de cerrar el modo y aunque posteriormente se
active la facturación real. No convertir muestras en comprobantes fiscales.

El QR indica que no acredita cobertura real. Envíos a correo/WhatsApp se registran
como `simulated`, sin contactar clientes. Se excluyen pruebas de liquidaciones,
META, reportes comerciales y estados de cuenta. Las emisiones de prueba del mismo
lote sí validan superposición entre ellas; no bloquean cobertura de registros reales.

## Prueba externa AFOCAT

Acceso independiente: `https://app.afocatlaprimera.com/abissol-pruebas/`.
Reutiliza sesión y permisos de AFOCAT; PHP reenvía únicamente operaciones permitidas
a la API V2, con token fuera de public_html. No modifica la integración productiva
de `emitir/` ni de `abissol/`, que sigue en Laravel. Probar desde las rutas antiguas
no constituye una prueba V2 y podría generar registros reales en Laravel.

La credencial `test_only` funciona únicamente mientras exista lote activo. Limita
consulta y envío de documentos a pruebas y no permite sincronizar usuarios reales.
La página conserva CSRF, alcance emisor/responsable y una referencia idempotente
por intento. Genera los mismos documentos por el contrato externo de V2.

Código reproducible del portal de pruebas: `deployment/alp/test-portal/`.
No se copian credenciales ni configuración de ALP a GitHub. Su token se provisiona
con `create_medical_connector.py --source externa_alp --test-only --output …` y
se conserva como `/home/alp/.abissol-v2-test-token`, propietario alp, permiso 0600.

## Mapeo y eliminación posterior

Migración 0015: índice de lote en emisiones y indicador en credenciales; ninguna
tabla nueva. Facturas, envíos y documentos se enlazan por sus claves existentes;
el comprobante conserva además `details.test_batch`. Los originales reales no se
reetiquetan ni cambian. No se elimina nada al finalizar el modo.

`BackEnd/scripts/medical_test_inventory.py --batch PRUEBA-… --output /ruta/privada.json`
enumera emisiones, comprobantes, envíos, documentos/versiones y rutas fiscales para
la limpieza posterior solicitada. Es una operación de lectura. Antes de eliminar
se revisará este inventario, dependencias y auditoría. Nunca reiniciar contadores
reales ni borrar cuentas, planes, condicionados o documentos compartidos.

Validación: pruebas aisladas de ambos canales, idempotencia, invariancia de
correlativos, ausencia de firma y cola, simulación de correo, persistencia del
bloqueo y cierre de credencial de prueba; regresión fiscal y de integración.
