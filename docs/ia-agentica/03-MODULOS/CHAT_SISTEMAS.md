# Chat de ABISSOL con Sistemas de Virtual IA

Publicado y conectado en producción el 14/10/2026; ver evidencia al final.

## Uso e identidad

Chat en la cabecera, disponible en las tres distribuciones de navegación. El
directorio muestra Sistemas general y los operadores autorizados de Virtual IA;
elegir uno abre su conversación personal. Incluye historial paginado, no leídos,
texto e imágenes de hasta 5 MiB, pegado y captura con permiso del navegador.
Un canal desconectado sigue permitiendo escribir. Los errores conservan el borrador.

Se reutiliza el contrato de Capital sin modificar sus archivos ni Virtual IA.
El backend fija identificador y nombre del usuario de ABISSOL. No acepta la
identidad enviada por el navegador. Chat y presencia se rechazan durante la
impersonación o mientras exista cambio obligatorio de contraseña pendiente.
Cada conector aísla participantes, historial y permisos del departamento destino.

## Presencia y actualización

El navegador autenticado envía presencia cada 20 segundos mientras está visible,
independientemente de abrir Chat. La tabla nueva `support_chat_presence` vincula
el pulso a su sesión de dispositivo; no modifica la sesión ni controla jornada.
El publicador de backend envía cada cinco segundos el directorio de usuarios
activos/no eliminados. Sólo comparte ID, nombre y conectado/desconectado.
Un pulso vence a los 60 segundos; sesiones vencidas o revocadas no dan conexión.
La copia de Virtual IA conserva su propia caducidad de 90 segundos si el servidor
de ABISSOL deja de publicar. No incluye correos, claves ni datos comerciales.

Sistemas se consulta cada tres segundos con el directorio abierto y cada veinte
al cerrarlo para los avisos. Mensajes visibles: cada tres segundos. No hay consultas
del navegador con la pestaña oculta. Recuperar foco/visibilidad refresca el estado;
se evitan solicitudes superpuestas. Fallar el directorio mantiene los nombres y
reemplaza los estados por «Sin actualizar». Es actualización por intervalos cortos,
no WebSocket ni garantía de entrega instantánea; red y caducidad limitan la latencia.

## Configuración y activación

- Aplicar `0017_support_chat_presence` en la base exclusiva de ABISSOL.
- En Virtual IA verificar cliente ABISSOL y departamento Sistemas; crear un
  conector exclusivo con nombre **ABISSOL**, activo y token nuevo. La etiqueta
  existente `company=connector.name` permite reconocer a sus usuarios en Contactos.
  No asumir IDs de cliente/departamento ni reutilizar la credencial de Capital.
- Guardar exclusivamente en el entorno privado backend de ABISSOL:
  `SUPPORT_CHAT_URL=https://v2.virtualizate.pe/api/siacat/api/v1/support-chat` y
  `SUPPORT_CHAT_TOKEN` con la credencial nueva. No configurar local contra producción:
  el publicador reemplaza el directorio del conector con los usuarios de su ambiente.
  Desarrollo debe usar conector propio y Virtual IA local.
- Publicar por el flujo autorizado de ABISSOL con respaldo, migración y salud.
  No requiere cambiar código ni permisos de Virtual IA si el contrato está vigente.
- Verificar directorio autenticado en ambos lados, etiqueta ABISSOL, presencia,
  cierre de sesión y caducidad. Los mensajes a personas reales requieren destinatarios
  autorizados; las pruebas de esta implementación sólo usan respuestas ficticias.

URL HTTPS obligatoria; HTTP sólo se admite en localhost/127.0.0.1. Credencial
exclusivamente backend, respuestas autenticadas `private, no-store`. Un canal sin
configurar devuelve 503 legible. Fallos remotos no detienen el planificador documental.

## Verificación de esta entrega

Pruebas aisladas de identidad, impersonación, secreto, envío/idempotencia, presencia,
caducidad, sesiones revocadas, directorio sin bajas y publicador autónomo. TypeScript
sin emisión correcto. MariaDB local no acepta conexiones; la migración y el upsert
MySQL permanecen sin ejecutar contra MariaDB. Sin conector real, mensajes reales,
commit, push ni publicación productiva durante esta tarea.

Verificación final: ESLint de ambos componentes aprobado y SQL MySQL de la migración
0017 generado correctamente sin conectar ni modificar bases. Diff sin errores de espacios.

## 14/10/2026 19:14 America/Lima - Chat publicado y conectado

Publicado el codigo de main `4f48e722159f84ba33d942f50b7987a5cbadb2f8` por el
publicador oficial, con respaldo SQL verificado, migracion 0017 aplicada y salud
HTTPS 200. Bundle publico y chunk de Chat cotejados por SHA-256 con la release.
Conector productivo exclusivo ABISSOL: cliente 20 y departamento 3 verificados en
Virtual IA; credencial nueva solo en backend ABISSOL y hash en Virtual IA.
Directorio productivo: 71 personas activas, etiqueta ABISSOL confirmada en la
consulta de Contactos de Sistemas. GET contactos y POST presencia HTTPS 200,
tres operadores; sesion temporal cerrada (204) y revocacion comprobada.
Propagacion de conectado/desconectado comprobada entre ambos servidores; no se
enviaron mensajes. Cadencias: publicador 5 s, directorios/mensajes abiertos 3 s,
pulso visible 20 s, caducidad 60 s. Son consultas periodicas, no WebSocket.
Ocho pruebas focalizadas, TypeScript, ESLint y build productivo aprobados.
Virtual IA ya tenia presencia y directorio cada 3 s; no se desplego ni reinicio
su aplicacion. Respaldos privados de conectores y entorno guardados en servidor.
Pendiente solo comprobacion visual del usuario tras recargar ambas plataformas.
