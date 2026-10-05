# ADR-0001: base independiente de ABISSOL V2

Fecha: 05/10/2026. Estado: implementado localmente.

La petición requiere copiar SIACAT V4 y retirar su negocio. Se copia el código de
trabajo actual, incluidos cambios transversales locales, sin historial Git, secretos,
datos ni artefactos de ejecución. SIACAT V4 permanece intacto.

Se eliminan los módulos de negocio y sus integraciones. Como el repositorio destino
estaba vacío y no tiene instalaciones previas, se crea una migración inicial nueva,
sin ejecutar ni copiar la cadena histórica que volvería a crear tablas del origen.
Esta decisión impide usar la base como actualización directa de SIACAT.

Se mantienen FastAPI/React y MariaDB, componentes compartidos y Wolverine.
La migración funcional del ABISSOL anterior pertenece a una etapa posterior.
