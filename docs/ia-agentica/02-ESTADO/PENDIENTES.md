# Pendientes

## Corte definitivo: revisión vigente del 09/10/2026

La [revisión por opción](../03-MODULOS/REVISION_CORTE_20261009.md) reemplaza
las listas iniciales siguientes como diagnóstico de preparación. **No retirar
Laravel todavía:** faltan operaciones fiscales (notas/anulación/CDR histórico),
continuidad de seis liquidaciones importadas abiertas, corrección de emisiones,
numeración definitiva y habilitación productiva posterior a las pruebas ALP.
Navegación y 21 pruebas focalizadas aprobadas; servicios externos reales y
aceptación SUNAT no se ejecutaron en esta auditoría. V2 sigue en modo pruebas.

Actualización posterior: consulta oficial por código/DNI y QR implementada y
probada. ALP `/abissol/` y `/emitir/` ya apuntan a V2 con lote de pruebas activo;
correo y WhatsApp de prueba aceptados por sus proveedores para los destinatarios
autorizados. SUNAT continúa desactivado. Ver [entrega del flujo oficial](../03-MODULOS/FLUJO_WEB_ALP_20261009.md).

- Aceptación del piloto por el usuario: https://v2.abissol.org/.
- Definir e implementar la funcionalidad ABISSOL en una etapa posterior.
- Configurar y probar únicamente las integraciones externas que ABISSOL necesite.
- Cargar un catálogo UBIGEO verificado cuando se requiera ubicación territorial.
- Probar Docker si se adopta esa alternativa; la publicación nativa es la verificada.

## Resuelto el 05/10/2026
Publicación en GitHub autorizada y realizada directamente en main. Piloto desplegado en alp, dominio v2.abissol.org, con base independiente abissol_v2 y una cuenta administradora inicial. Login, cambio de clave y menú usan la marca oficial. Las 18 rutas del menú cargaron sin errores en navegador. Entornos privados excluidos de Git.

No activar módulos del origen ni conectar bases anteriores por similitud de nombres.


## 2026-10-07 05:30 America/Lima · modo de trabajo obligatorio

Incorporado íntegramente el texto proporcionado por el usuario en 06-GUIAS/MODO_DE_TRABAJO.md; AGENTS.md exige leerlo y aplicarlo en todas las tareas futuras del proyecto. Índice actualizado; cambios limitados a instrucciones y documentación. Se conserva el trabajo previo y el aislamiento del proyecto. Validación: igualdad de contenido con el adjunto, 15 secciones y enlace obligatorio correcto. Sin cambios funcionales, commit, push ni publicación.

## Chat ABISSOL conectado - resuelto el 14/10/2026

Publicacion autorizada y completada; conector exclusivo, credencial, migracion y
directorios productivos verificados. Se comprobo conectado/desconectado sin
mensajes reales. Solo falta QA visual del usuario; MariaDB local sigue detenida,
pero la migracion y el upsert se ejecutaron correctamente en produccion.
