# Estado actual

## Migración real Laravel — 05/10/2026

Soporte preparado para migrar las cuentas y el negocio de app.abissol.org,
incluidos históricos fiscales y archivos originales. Migración 0005, importador
transaccional e idempotente, secretos cifrados y conciliación por registro.
Simulación remota sin errores: 69 usuarios, 9 emisiones, 7 liquidaciones,
43 comprobantes y 273 documentos. Cuatro archivos de un comprobante archivado
ya no existen en el origen; se conserva y señala esa ausencia.
27 pruebas backend aprobadas, TypeScript/lint correctos y Alembic sin diferencias.
Detalle y límites: `03-MODULOS/MIGRACION_LARAVEL.md`.
Carga definitiva/publicación pendientes de la verificación final de este cambio.

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
