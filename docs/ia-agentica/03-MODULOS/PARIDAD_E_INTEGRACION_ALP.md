# Revisión Laravel / V2 e integración ALP — 07/10/2026

## Resultado y alcance

Se compararon controladores y servicios productivos de Laravel, el cliente ALP
(`emitir/integraciones.php`, `abissol/bootstrap.php`, `abissol/nueva_emision.php`)
y los flujos V2. El recuento consultado sigue siendo 9 emisiones, 7 liquidaciones
y 43 comprobantes en Laravel, iguales a los totales migrados. No se generaron
ventas ni comunicaciones de prueba con clientes reales.

| Flujo | Resultado V2 |
| --- | --- |
| Emisión interna | Misma regla de costos; nombres/apellidos separados y bloqueo de coberturas superpuestas. |
| Emisión externa | API técnica por origen, referencia idempotente y responsable/emisor validados. Preparada; ALP sigue apuntando a Laravel. |
| Vigencia | Mañana por defecto, permite una fecha posterior por instrucción del usuario; Laravel fuerza mañana. |
| Comisiones | Tarifa del emisor, luego responsable/plan; oficina AFOCAT que emite directamente tiene comisión cero. |
| Comprobante | Boleta 03 o factura 01 elegida ANTES de numerar. Series/correlativos independientes, sin renumerar ni reenviar históricos. |
| Factura | RUC, razón social, dirección y ubigeo propios del adquirente, independiente del asegurado. Crédito requiere vencimiento explícito; una cuota por el total pendiente. |
| Envíos | Canales existentes; conector reserva el intento y evita reenvíos inadvertidos. Reenvío explícito exige `force` después de revisar el intento anterior. |
| Liquidaciones | Depósito y comisión separados en vista previa; deshabilita cambios durante cálculo/guardado. Mantiene los cuatro espacios operativos. |
| Documentos | Históricos preservados, carta V2 con su diseño propio, PDF A4 fiscal. Ticket térmico y emisión de notas 07/08 no están implementados en este cambio. |

No declarar equivalencia completa ni integración productiva activa mientras los
pendientes de corte sigan abiertos. La validación XSD no sustituye aceptación
fiscal por SUNAT; las pruebas de envío del conector utilizan un proveedor simulado.

## Contrato de integración

Base: `/abissol/api/v1/integrations/medical`. Bearer técnico aleatorio almacenado
como SHA-256, vinculado a un único origen y una cuenta técnica sin roles de portal.
No usar contraseñas personales ni JWT de usuario como credencial de integración.
`scripts/create_medical_connector.py` escribe el secreto exclusivamente al archivo
privado indicado. Sincronizar perfiles externos no crea accesos al portal.

Emisiones: `GET plans`, `GET/POST emissions`, `POST emissions/validate` (rollback),
`GET emissions/{id}`, `GET emissions/{id}/letter`, `POST emissions/{id}/resend`.
Usuarios: `POST external-users/sync`, `GET sellers`.
Liquidaciones: `GET liquidations/pending-issuances` (máximo 1000 resultados).
Documentos: `POST lookup/dni`, `POST billing/lookup-document`; catálogos de ubigeo.
Fiscal: `POST billing/from-issuance/{id}` devuelve el comprobante ya reservado;
`GET billing/{id}`, `POST billing/{id}/generate`, `POST billing/{id}/send-sunat`,
`GET billing/{id}/file/{PDF|XML|CDR|ZIP}`. Todas las lecturas/descargas se limitan
al origen autenticado. Consulta CDR después de respuestas inciertas; sin reenvío
automático de un XML cuyo intento de envío ya fue registrado.

`billing` es obligatorio en la emisión externa, incluso para boleta. El cliente
anterior elegía el tipo después de crear la emisión: apuntarlo a V2 sin adaptar
es incorrecto. Idempotencia exige conservar referencia y datos fiscales; rechaza
reutilizar la referencia para otro plan, documento, emisor o adquirente.
Históricos exponen su ID Laravel; nuevos registros usan 1 000 000 000 + ID V2,
evitando colisiones con IDs guardados en ALP. No reutilizar esos IDs como IDs del
portal V2. Fechas del listado se filtran por venta, con paginación explícita.
Perfiles y comprobantes se cargan en lote al listar, sin consultas por fila.

## Adaptador ALP preparado, sin activar

`deployment/alp/prepare_adapter.py` genera cinco archivos en un directorio nuevo
a partir de una instantánea de los tres archivos ALP citados. Comprueba cada punto
de inserción y falla si el origen cambió. No modifica el origen ni configura URLs.
Incluye selección fiscal previa, normalización de respuestas, paginación y fechas
de venta. `archivo_v2.php` exige sesión ALP y visibilidad del emisor/responsable;
obtiene el archivo con token servidor a servidor, sin entregarlo al navegador.
Se validó sintaxis PHP de los cinco archivos generados sobre la copia productiva.

Antes del corte, confirmar la decisión pendiente del usuario: series exclusivas
V2 con Laravel disponible, o corte definitivo continuando series anteriores.
La implementación actual exige series exclusivas; reutilizar antiguas requiere
un procedimiento explícito de cierre y conciliación, no basta editar un campo.
También separar prefijos de certificados A/B si ambos sistemas emitirán a la vez.
Después: actualizar comparación de totales/históricos, respaldar, generar token
por origen, instalar adaptador revisado, configurar URL/token privado, validar
sin persistir ventas, activar fiscal y cambiar ALP durante el corte coordinado.
Conservar rollback de configuración y archivos; nunca restaurar correlativos a
un valor anterior después de emitir un comprobante real.

## Validación

- 10 pruebas fiscales: distribución, firma, CDR, recuperación, series separadas,
  crédito con vencimiento y rollback antes de reservar números.
- Pruebas del conector: aislamiento, idempotencia, cobertura, tarifas, sincronización,
  reserva de envíos y generación/descarga fiscal con proveedor simulado.
- Factura contado/crédito firmada: validación con XSD UBL Invoice 2.1.
- SUNAT Beta aceptó ambas facturas sintéticas (CDR código 0), sin ventas reales.
- TypeScript y ESLint de los componentes modificados; navegador con DNI/RUC
  simulados, respuestas tardías, fechas Lima y diseño móvil, sin guardar ventas.
- Migraciones 0009/0010 y comprobación Alembic local sin diferencias pendientes.
- Verificación productiva detectó históricos sin `external_source` y catálogo
  geográfico vacío: el conector obtiene el origen de su fuente autorizada (con
  canal interno/externo separado); migración 0011 incorpora el CSV público existente
  sin sobrescribir catálogos cargados. Pestañas 6+4 verificadas por HTTPS.

Referencias oficiales: [SUNAT, preguntas frecuentes sobre crédito y cuotas](https://cpe.sunat.gob.pe/informacion_general/preguntas_frecuentes)
y [guía UBL 2.1 de factura](https://cpe.sunat.gob.pe/sites/default/files/inline-files/guia%2Bxml%2Bfactura%2Bversion%202-1%2B1%2B0%20%282%29_0%20%282%29.pdf).
