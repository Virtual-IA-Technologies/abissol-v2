# Estado actual

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
