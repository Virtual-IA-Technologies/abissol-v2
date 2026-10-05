# Base de plataforma

Backend: FastAPI, SQLAlchemy, MariaDB y Alembic. Frontend: React, TypeScript, Vite
y componentes compartidos del origen. API `/abissol/api/v1`; puertos locales 8015/5185.

Wolverine aplica permisos en backend y frontend; cookies y claves del navegador
usan identidad ABISSOL. La cuenta inicial tiene rol Programador y cambio obligatorio
de contraseña. Los roles Administrador y Usuario nacen sin datos de negocio.

Una única migración inicial congelada crea los modelos de plataforma. El catálogo
de roles/menús vive en `BackEnd/app/bootstrap.py`; no reescribe personalizaciones al
repetir la inicialización. Los próximos cambios de esquema requieren migraciones nuevas.

Los documentos físicos se guardan bajo `BackEnd/storage`, ignorado por Git. Conectores
externos no tienen cuentas ni secretos iniciales. El planificador conserva solo tareas
documentales internas; no existen workers de negocio ALP, MTC o ABISSOL comercial.

Los módulos nuevos deben separar modelos, esquemas, servicios y rutas; aplicar
Wolverine, auditoría y pruebas. Colecciones reutilizan búsqueda, filtros, orden,
paginación, exportación XLSX y acciones por nivel. El menú permanece visible.

La portada no muestra cifras de negocio ni datos de muestra. Los proveedores analíticos
conservados corresponden únicamente a recursos de plataforma autorizados.
