# Estado actual

## Archivo por afiliado — 12/10/2026

Preparada estructura Afiliados → nombre/documento → certificado, con cartas y
comprobantes vinculados, incluidos originales históricos. Reorganización de metadatos
idempotente, conservando versiones y permisos. Publicación autorizada en main y V2.
[Detalle](../03-MODULOS/ARCHIVO_POR_AFILIADO.md).

## Impersonación visible — 12/10/2026

Preparada la opción Impersonar usuario en Usuarios, con panel lateral y búsqueda.
Reutiliza identidad, permisos y auditoría existentes. Previene inicio cuando hay
cambio obligatorio de contraseña pendiente. Prueba aislada aprobada; publicación
autorizada en main y V2. [Detalle](../03-MODULOS/IMPERSONACION.md).


## Dashboard comercial — 10/10/2026

Inicio incorpora emisiones, ventas, vigencias y liquidaciones según permisos, gráficos
ligeros con movimiento reducido y períodos de 7/30/90 días. Una petición y agregaciones
SQL; seis formularios comerciales pasan a carga diferida. Sin cambios de datos.
Detalle: [dashboard](../03-MODULOS/DASHBOARD.md).

## Liquidaciones y vouchers históricos — 10/10/2026

Nueva liquidación vuelve a abrir los pendientes en panel lateral. Vouchers históricos
con vista previa y estado de presentación separado de aprobación. Verificados cuatro
originales existentes y cinco emisiones sin voucher; sin alterar estados financieros.
Detalle: [vouchers históricos](../03-MODULOS/VOUCHERS_HISTORICOS.md).

## Alcance comercial y vistas compactas — 10/10/2026

Filtros agrupados y encabezados simplificados en Emisiones, Liquidaciones y Facturación.
Reportes con cobros, depósito pendiente y vencimientos; dependientes pueden liquidar
sus propias ventas sin acceder a partidas ajenas. Archivos y comprobantes conservan
el alcance comercial de su origen. Migración 0016 y ajuste del portal ALP.
Detalle: [alcance comercial y filtros](../03-MODULOS/ALCANCE_COMERCIAL_Y_FILTROS.md).

## Pruebas sin numeración real — 07/10/2026

Modo temporal para emisiones nuevas internas/externas: lote identificable,
documentos locales marcados, sin firma ni cola SUNAT, envíos simulados y exclusión
de liquidaciones/reportes reales. Portal AFOCAT separado y credencial de prueba.
Migración 0015; inventario para limpieza posterior sin reiniciar correlativos.
Ver [operación y acceso externo](../03-MODULOS/PRUEBAS_EMISION.md).

## Documentos y flujo de emisión — 07/10/2026

Plantillas originales Laravel para carta versión 7, A4, ticket y bienvenida HTML,
con Dompdf aislado. Carta archivada compartida por portal, QR, API externa y correo;
condicionado adjunto y envío explícito de comprobantes con control de reintentos.
Migración 0014 agrega vínculo de envío al comprobante sin nuevas tablas.
Ver [implementación y límites](../03-MODULOS/DOCUMENTOS_EMISION.md).

## Liquidaciones de vendedores — 07/10/2026

Abonos parciales, identidad bancaria completa, conciliación administrativa,
compensaciones y pagos de comisión separados del cierre. Estado de cuenta paginado
por vendedor; constancia de cierre archivada automáticamente. Consultas agrupadas,
catálogos reutilizados e históricos de consulta. Migración 0013 amplía constancias
existentes sin crear tablas. Ver [flujo, controles y límites](../03-MODULOS/LIQUIDACIONES_VENDEDORES.md).

## Central documental por carpetas — 07/10/2026

Documentos reúne archivos personales y documentos automáticos de Emisiones,
Facturación, Liquidaciones y Planes. Los artefactos conservan permisos de origen,
versiones y SHA-256; se incorporan al generarse y mediante sincronización histórica
idempotente. Visor local para PDF, imágenes, XML, DOCX y XLSX. Migración 0012.
Ver [Central de documentos](../03-MODULOS/CENTRAL_DOCUMENTOS.md).

## Paridad de emisiones y conector ALP — 07/10/2026

Boleta/factura elegida antes de emitir, correlativos separados, factura a crédito
con vencimiento y consulta RUC automática. Reglas compartidas para emisión interna
y externa: cobertura sin superposición, nombres separados y comisiones del emisor.
Conector técnico aislado por origen y adaptador ALP preparado; ALP aún usa Laravel.
Activación fiscal/corte pendientes de la elección de series. Liquidaciones muestran
comisión y depósito diferenciados y bloquean cambios mientras calculan/guardan.
Ver [comparación, pruebas y pendientes](../03-MODULOS/PARIDAD_E_INTEGRACION_ALP.md).

## Navegación consolidada y consultas — 06/10/2026

Planes y Comunicaciones dejan de ser entradas del menú lateral: se accede desde
Emisiones / Planes y Emisiones / Envíos. Red comercial permanece. Correo y WhatsApp
se configuran en Emisiones / Configuración, exclusivamente por Programador.
Las rutas anteriores redirigen; se mantienen permisos independientes y datos.
Migración 0008 oculta las entradas duplicadas y añade índice de estado META.
Catálogos reutilizados al filtrar/paginar; consultas por sección, red comercial
sin doble listado, liquidaciones sin consultas por emisión y META con resumen
agregado y solo el último intento por fila. Ver `03-MODULOS/NAVEGACION_OPTIMIZADA.md`.

## Seis pestañas de Emisiones y cuatro de Liquidaciones — 06/10/2026

Espacios de trabajo completos con pestañas inferiores. Emisiones incorpora resumen
por vigencia, envíos de afiliados, altas META, vendedores, planes y configuración.
Liquidaciones separa vendedores, META mensual, plataforma e historial; vista previa,
selección y consolidado sin exigir un responsable para META/plataforma.
Excel y carta mensual, envío confirmado con protección de duplicados y depósitos
AFOCAT según Laravel productivo. Se conservan importes y estados históricos.
Configuración comercial con migración 0007; hora de referencia sin activar cron.
Detalle de alcance y comprobaciones: `03-MODULOS/PESTANAS_COMERCIALES.md`.

## Comunicaciones y pestañas — 05/10/2026

Pestañas inferiores en Facturación y Comunicaciones. Correo y WhatsApp separados,
configurables exclusivamente por Programador en UI y API. Parámetros efectivos
del Laravel aplicados en servidor, claves cifradas, copia privada y auditoría.
SMTP conectado y autenticado; Wablas configurado sin enviar mensajes reales.
OTP deshabilitado. Liquidaciones conserva su base funcional.
Ver `03-MODULOS/COMUNICACIONES.md`.

## Boleta automática y configuración exclusiva — 05/10/2026

Pestaña Configuración · Programador, protegida también en GET/PUT/revisión fiscal.
Boleta automática de nuevas emisiones, reparto fiscal cotejado con Laravel,
numeración transaccional exclusiva, XML firmado/ZIP/PDF/QR, envío SOAP y recuperación
de CDR sin duplicar envíos. Cola persistente 0006 y timer systemd cada minuto.
SUNAT Beta aceptó una boleta ficticia (código 0); XSD oficial UBL 2.1 válido.
Consulta real getStatusCdr en producción correcta (histórico aceptado, sin emitir
nuevos documentos). Pestaña publicada verificada en HTTPS, escritorio y móvil.
Ocho pruebas fiscales, seis comerciales y tres de importación aprobadas; esquema
MariaDB sin diferencias. La cola admite el cruce de medianoche sin redatar boletas.
Envío real desactivado hasta decidir serie exclusiva V2 o corte de B001 en Laravel.
No se emitieron boletas reales ni se reprocesaron ventas migradas.
Detalles, pruebas y límites: `03-MODULOS/FACTURACION_SUNAT.md`.

Las secciones siguientes conservan el historial de implementación; las menciones
a facturación limitada a borradores corresponden al estado anterior a este cambio.

## Corrección APIperú y selectores — 05/10/2026

El servidor registraba ResponseValidationError en response.ubigeo: APIperú devuelve
una lista para DNI y el contrato público requiere texto. Se normaliza al código
del distrito, admitiendo también texto, lista vacía y datos ausentes. Se conserva
la consulta automática a ocho dígitos y los permisos de edición. Tres pruebas
aisladas verifican contrato, autorización y fechas sin consultar documentos reales.

Nueva emisión y los demás formularios comerciales usan SearchableSelect, con
búsqueda enfocada al abrir, filtro sin distinción de tildes y validación de campos
obligatorios. El selector de emisiones busca en servidor y conserva su selección.
La regla queda documentada en AGENTS.md para formularios futuros.
TypeScript, lint y pruebas de navegador correctos: foco automático, búsqueda sin
tildes, campos obligatorios, búsqueda remota y valores enviados por FormData.
Pruebas con respuestas y envíos interceptados, sin crear ventas ni comunicaciones.

## Nueva emisión y consulta DNI — 05/10/2026

Formulario dedicado con secciones de programa/emisor, titular y vigencia/pago;
resumen de precio, inicio y fin de cobertura; diseño adaptable y acentos verdes.
DNI consulta automáticamente a los ocho dígitos, sin botón de validación. Reutiliza
el endpoint autenticado smart-forms y APIperú exclusivamente desde el backend.
Nombres en orden nombres + apellido paterno + apellido materno. Cancela/ignora
respuestas de documentos anteriores y conserva una edición manual durante la consulta.
Si el proveedor falla permite completar los datos manualmente; CE/pasaporte manuales.

Inicio precargado en mañana según America/Lima, mínimo mañana en el calendario y
validación al guardar. Backend ya rechaza hoy/fechas pasadas; dos pruebas específicas
verifican mañana/fecha posterior, permisos, DNI incompleto, errores y orden de nombres.
Edge local y piloto HTTPS verificaron consulta automática simulada, respuesta tardía, ingreso manual,
calendario y escritorio/móvil incluso con zona del navegador Asia/Tokyo.
TypeScript/lint correctos. Parámetros privados de APIperú trasladados desde Laravel
al entorno remoto V2 con respaldo, sin copiar secretos al repositorio. Prueba con
DNI real pendiente de autorización específica; las pruebas visuales usan respuestas
simuladas y no registran ventas ni envían identificadores al proveedor.
Publicado en main y v2.abissol.org. Consultas DNI/RUC restringidas a edición de
Emisiones o Facturación; no se puede eludir el permiso enviando otro slug de menú.

## Migración real Laravel — 05/10/2026

Migradas las cuentas y el negocio de app.abissol.org al piloto v2.abissol.org,
incluidos históricos fiscales y archivos originales. Migración 0005, importador
transaccional e idempotente, secretos cifrados y conciliación por registro.
Carga real verificada: 69 usuarios (clave administradora V2 conservada), 64 perfiles,
9 emisiones, 7 liquidaciones, 43 comprobantes y 273 documentos/versiones.
254 archivos cotejados por SHA256 con lectura como usuario del servicio.
Una segunda ejecución con rollback confirma cero filas nuevas; una auditoría de carga.
Ventas activas S/ 840.00 y total histórico S/ 895.00, incluida la anulación.
Cuatro archivos de un comprobante archivado
ya no existen en el origen; se conserva y señala esa ausencia.
27 pruebas backend aprobadas, TypeScript/lint correctos y Alembic sin diferencias.
Detalle y límites: `03-MODULOS/MIGRACION_LARAVEL.md`.
Publicado directamente en main y en HTTPS. Verificadas siete opciones comerciales,
Usuarios (incluida Carmen), Archivos, nueve cartas originales y descargas fiscales
PDF/ticket/XML/ZIP/CDR. Sin errores JavaScript ni HTTP en la navegación probada.
Series A/B compatibles con el editor y protección contra reutilizar depósitos legados.
Configuración fiscal, certificado y credenciales conservados: envío SUNAT en V2
pendiente de habilitación/validación. El conector externo sigue en Laravel; no hay
sincronización continua ni corte de servicio anterior.

## Identidad y permisos comerciales — 05/10/2026

Red comercial distingue entidades, participantes externos y cuentas de acceso.
Origen interno/AFOCAT/aliado, clave externa única e ID de participante único por
origen. Cuenta opcional para externos y vinculación posterior sin duplicar perfil.
Tres roles comerciales mínimos, asignación explícita auditada y conservación de
roles administrativos/excepciones. Origen inactivo bloquea el alcance comercial.
Se conserva PROGRAMAS y su orden. Migración 0004_commercial_identity.

Consulta productiva limitada y de solo lectura en Laravel/La Primera; no se
cambiaron conectores ni datos reales. La recepción externa en V2 queda pendiente
del conector autenticado por entidad. Ver `03-MODULOS/IDENTIDAD_COMERCIAL.md`.

## Corrección de navegación al reorganizar menús — 05/10/2026

El editor recalculaba rutas de negocio como `/medical/medical-plans` al guardar
o mover el módulo. Las pantallas reales están en `/plataforma/medical/*`.
Las rutas implementadas se registran ahora automáticamente desde el catálogo
del backend y se muestran protegidas en el editor. Se pueden cambiar nombres
y posiciones conservando las rutas. Migración 0003_medical_routes repara solo
las siete direcciones, sin alterar PROGRAMAS, orden, padres ni permisos.
Prueba de regresión: renombrar/reordenar módulo, editar nombre de opción y
rechazar cambios de identificador vinculados a pantallas.

## Negocio ABISSOL — 05/10/2026

Siete opciones nuevas y módulo Negocio ABISSOL: planes, red comercial, emisiones,
comunicaciones, liquidaciones, facturación (borradores) y reportes. Migración
aditiva 0002_medical, nueve tablas independientes, 31 menús de plataforma/negocio.
Sin OTP WhatsApp, bandeja de correo ni aprobaciones generales. Conserva revisión
financiera de liquidaciones. SISAP no se modifica.

Planes configurables; emisión transaccional con snapshots, PDF y QR público sin
datos personales; alcance por origen/responsable/emisor además de permisos de
menú; cobros auditados; liquidaciones sin doble inclusión y adjuntos privados;
comunicaciones mediante los conectores existentes. Facturación no envía a SUNAT
y no asigna numeración fiscal hasta implementar/configurar el emisor electrónico.

Alcance detallado y pendientes de paridad: `03-MODULOS/NEGOCIO_ABISSOL.md`.
Verificación local: 19 pruebas backend aprobadas; migración MariaDB aplicada y
Alembic sin diferencias; siete pantallas comprobadas en Edge, escritorio/móvil,
sin errores JavaScript ni HTTP. Ninguna venta real ni comunicación de prueba.
Las notas siguientes conservan el historial de la base anterior.

## Marca en navegación · 05/10/2026 19:08 America/Lima

La cabecera del sidebar usa el símbolo oficial, nombre ABISSOL con acento verde
y lema «Inclusión, salud y solidaridad». Navegación por iconos y superior también
usan el símbolo oficial. Se conservan logos y textos personalizados configurados.
Validada la cabecera en Edge con sesión simulada; trabajo local.

## Cambio obligatorio de clave · 05/10/2026 19:05 America/Lima

Pantalla de primer acceso alineada con el login: tarjeta centrada, logo oficial,
fondo oscuro verde, acciones y focos verdes. Se conservan validaciones, cambio
de contraseña, cierre de sesión y redirección. TypeScript correcto; Edge con
sesión simulada verificó escritorio/móvil, logo y controles, sin tocar cuentas.

## Login con identidad ABISSOL · 05/10/2026 18:59 America/Lima

Tarjeta centrada con fondo oscuro, acentos verdes, logo y favicon originales
descargados de https://abissol.org/images/abissol-logo.png y
https://abissol.org/images/favicon.png. Archivos locales sin transformación.
Se conserva el logo claro personalizado si existe en Configuración.
El formulario mantiene contraseña, recuperación y sesión persistente; no agrega OTP.
Verificado en Edge: escritorio/móvil, logo cargado, mostrar/ocultar contraseña,
sin desbordamiento horizontal ni errores JavaScript; conexión API correcta.
Solo cambios locales, sin commit, push ni despliegue.

05/10/2026, America/Lima. Base local independiente preparada para revisión.

FastAPI y React conservan plataforma, usuarios, Wolverine, auditoría, documentos,
calendario, notificaciones y apariencia. Los cuatro módulos solicitados y sus
integraciones, modelos, rutas y pantallas fueron retirados físicamente.
Se inicia un esquema vacío con Alembic 0001_platform y un catálogo de menús propio.

Verificado: importación API, migración MariaDB desde vacío, Alembic sin diferencias
y ocho pruebas de autenticación, autorización, sesiones, instalación y aislamiento
(26.206 s). Compilación TypeScript/Vite correcta (1 min 4 s), con aviso de bundles
grandes en componentes documentales. Edge verificó acceso React, identidad, CORS y
API/MariaDB en los puertos definitivos 5185/8015 sin errores JavaScript.

Esquema: 46 tablas de plataforma, 23 menús y cero usuarios en la base local inicial.
La cuenta debe crearse mediante seed_core.py. Hay guía de arranque para Windows,
Linux/macOS y Docker opcional; Docker no se ejecutó porque su daemon estaba apagado.

Sin funcionalidad comercial ABISSOL, sin datos heredados y sin despliegue.
Repositorio destino: virtualizate-pe/abissol-v2, inicialmente vacío. Entrega inicial
preparada en main para clonación; no incluye historial Git ni secretos del origen.

Publicación pendiente: commit local `c95b9e0`. La revisión automática rechazó el
push por exigir autorización expresa para exportar código derivado de SIACAT.
GitHub sigue sin recibir esta base; todavía no puede clonarse desde el remoto.
La aclaración documental posterior al rechazo queda en el árbol local.
## GitHub reconfigurado · 05/10/2026 18:56 America/Lima

Repositorio vigente: `Virtual-IA-Technologies/abissol-v2`, solicitado por el usuario tras cambiar el nombre de cuenta. El remoto responde correctamente pero sigue sin ramas: la base inicial todavía no se exportó. Esta reconfiguración no equivale a publicar esa base.

## Refresh y piloto — 05/10/2026

- DevOps simplificado a main → GitHub → servidor: sin ramas personales ni scripts inexistentes, sin consultas periódicas de integración.
- API de producción usa el mismo dominio; configuración local y remota separadas.
- Pruebas ampliadas a consultas de todas las opciones de plataforma y restricciones de main. Build React correcto; migraciones locales sin diferencias.
- Imports frontend sin destinos rotos. Componentes genéricos sin consumidores se conservan como biblioteca para próximos módulos; no son opciones de menú huérfanas.
- Piloto autorizado: `v2.abissol.org`, servidor alp, base nueva `abissol_v2`, servicio independiente, releases y almacenamiento fuera de public_html.
- Publicador en deployment: respaldo de base existente, comprobación de salud y main sincronizado. Secretos excluidos del repositorio.

## Piloto verificado — 05/10/2026 19:30 America/Lima

- Publicado en https://v2.abissol.org/; main enviado a Virtual-IA-Technologies/abissol-v2.
- Base independiente `abissol_v2`: 46 tablas de plataforma y `alembic_version`; una cuenta administradora inicial con la clave local conservada.
- Servicio `abissol-v2` activo; HTTPS 200, HTTP redirige con 301, salud API y conexión MariaDB correctas. Alembic sin diferencias.
- Navegación real autenticada por las 18 rutas del menú: sin errores JavaScript ni respuestas HTTP fallidas. Login con logo oficial y vista móvil sin desbordamiento. Sesión temporal cerrada.
- 13 pruebas backend aprobadas: 8 de plataforma y 5 de main. Lint sin errores y 6 advertencias preexistentes de Fast Refresh. Build correcto; editor y Excel mantienen paquetes grandes cargados bajo demanda.
- Corregido el permiso de lectura de la carpeta releases detectado en el primer intento. Publicador probado sobre el servidor real; evita recompilar si el árbol del frontend y el contenido del build coinciden.
- Conectores externos y funcionalidad de negocio ABISSOL pendientes, fuera del alcance de esta base.


## 2026-10-07 05:30 America/Lima · modo de trabajo obligatorio

Incorporado íntegramente el texto proporcionado por el usuario en 06-GUIAS/MODO_DE_TRABAJO.md; AGENTS.md exige leerlo y aplicarlo en todas las tareas futuras del proyecto. Índice actualizado; cambios limitados a instrucciones y documentación. Se conserva el trabajo previo y el aislamiento del proyecto. Validación: igualdad de contenido con el adjunto, 15 secciones y enlace obligatorio correcto. Sin cambios funcionales, commit, push ni publicación.
