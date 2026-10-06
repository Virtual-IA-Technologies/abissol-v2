# ABISSOL V2

Base FastAPI + React derivada del código local de SIACAT V4 el 05/10/2026.
Proyecto independiente con módulos comerciales ABISSOL en FastAPI y React.

Piloto con datos reales migrados de ABISSOL Laravel: cuentas, red comercial,
emisiones, liquidaciones, documentos e historial fiscal. Consulta de originales
PDF/XML/CDR y configuración fiscal conservada; emisión electrónica nueva en V2
implementada con cola persistente y validada en SUNAT Beta. Activación real pendiente
de definir serie exclusiva V2 para no colisionar con Laravel. Ver
[Facturación SUNAT](docs/ia-agentica/03-MODULOS/FACTURACION_SUNAT.md) y
[Migración Laravel](docs/ia-agentica/03-MODULOS/MIGRACION_LARAVEL.md).

Negocio: planes, red comercial, emisiones con carta/QR, comunicaciones salientes,
liquidaciones, boletas automáticas al registrar programas y reportes. Sin OTP WhatsApp,
bandeja de correo ni aprobaciones generales. Configuración fiscal exclusiva del
Programador; envío productivo inicialmente desactivado hasta definir numeración. El historial
importado conserva sus estados originales. Alcance y configuración
en [Negocio ABISSOL](docs/ia-agentica/03-MODULOS/NEGOCIO_ABISSOL.md).

Conserva sesiones, usuarios, roles, permisos Wolverine, menús, auditoría, apariencia,
calendario, notificaciones, documentos, documentación, búsqueda y componentes reutilizables.
No incluye Emisiones, Control, Siniestros, Contabilidad, facturación CAT, MTC,
sincronización ALP ni la integración comercial ABISSOL del sistema de origen.
No se importaron datos, claves, almacenamiento, cuentas ni historial Git de SIACAT.

## Ejecución local en Windows

Requisitos: Python 3.14, Node.js 24, npm y MariaDB 10.11 o compatible.

1. Desde la raíz, instalar dependencias y generar la configuración local:

   ```powershell
   .\setup-local.ps1
   ```

2. Crear una **base vacía exclusiva** y un usuario con permisos solo sobre ella
   en tu MariaDB local. Ejemplo para ejecutar con tu administrador de MariaDB
   (sustituye la contraseña del ejemplo por una propia):

   ```sql
   CREATE DATABASE abissol_v2_local CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'abissol'@'localhost' IDENTIFIED BY 'SUSTITUIR_POR_UNA_CLAVE_PROPIA';
   GRANT ALL PRIVILEGES ON abissol_v2_local.* TO 'abissol'@'localhost';
   ```

3. Ajustar `BackEnd/.env`: `DB_HOST`, `DB_PORT`, `DB_USER` y `DB_PASSWORD`.
   Conservar `DB_NAME=abissol_v2_local` y `EXPECTED_DB_NAME=abissol_v2_local`.
   `setup-local.ps1` genera una `SECRET_KEY` aleatoria; no compartir ni subir `.env`.

4. Aplicar el esquema nuevo y crear la cuenta inicial:

   ```powershell
   cd BackEnd
   .\.venv\Scripts\python.exe scripts\migrate.py
   .\.venv\Scripts\python.exe seed_core.py
   cd ..
   ```

   El inicializador solicita correo y contraseña (mínimo diez caracteres,
   mayúscula, minúscula y número). Crea `administrador` con rol Programador,
   carga los menús y sincroniza la documentación. Exige cambiar la contraseña
   al primer ingreso. Repetirlo con el mismo correo no cambia claves ni permisos.

5. Abrir dos terminales desde la raíz:

   ```powershell
   .\run-backend.ps1
   ```

   ```powershell
   .\run-frontend.ps1
   ```

Abrir **http://localhost:5185**. API: **http://localhost:8015**;
salud: `/health/ready`; OpenAPI: `/docs`; prefijo: `/abissol/api/v1`.
Estos puertos, base, cookies y almacenamiento del navegador son independientes de SIACAT.

## Linux/macOS

Desde `BackEnd`, crear `.venv` con `python3.14 -m venv .venv`, instalar
tras activarlo con `source .venv/bin/activate` mediante
`pip install -r requirements-core.txt`, copiar `.env.example` a `.env` y completar
la conexión y una clave aleatoria. Ejecutar `python scripts/migrate.py`,
`python seed_core.py` y `uvicorn app.main:app --host 127.0.0.1 --port 8015`.
Desde `FrontEnd/frontend-app`, ejecutar `npm ci` y `npm run dev`.

## Verificación

Desde `BackEnd`: `python -m unittest discover -s tests -v` y `python -m alembic check`.
Desde `FrontEnd/frontend-app`: `npm run build`.
Las pruebas usan SQLite en memoria; las migraciones se verifican además sobre MariaDB local.

## Docker opcional

Copiar `.env.example` de la raíz a `.env` y asignar tres secretos propios distintos.
Ejecutar `docker compose up --build -d` y después
`docker compose exec backend python seed_core.py`. Usa los mismos puertos locales;
detener primero los procesos nativos si están activos. Los volúmenes pertenecen solo
a este proyecto. Esta alternativa no se ejecutó en la sesión de preparación porque
Docker Desktop no estaba iniciado; la ruta nativa es la verificada.

## Alcance de esta base

Los conectores SMTP, WhatsApp, Drive, ONLYOFFICE, consultas de identidad y proveedores
externos requieren configuración propia; no se han activado ni probado con cuentas reales.
El catálogo UBIGEO tiene estructura vacía. El asistente conserva su estructura y
configuración, desactivado inicialmente; sus herramientas específicas de negocio fueron retiradas.
DevOps trabaja exclusivamente en `main`: descargar, subir a GitHub y publicar.
Piloto: `https://v2.abissol.org`, servidor `alp`, base independiente `abissol_v2`.
La configuración privada local está en `deployment/.env` (plantilla `.env.example`).
Después de subir main: `BackEnd/.venv/Scripts/python.exe deployment/publish.py`.
El publicador exige main limpio y sincronizado, compila, transfiere el commit,
respalda la base existente, migra y comprueba HTTPS. No copia entornos ni datos locales.
Backend remoto: servicio `abissol-v2`, puerto interno 8015; releases bajo
`/home/abissol/apps/abissol-v2`, almacenamiento compartido fuera de la raíz pública.

La migración `0001_platform` es una línea base nueva para bases vacías. **No se aplica
sobre una base SIACAT ni sobre el ABISSOL anterior.** El repositorio anterior no fue modificado.

Estado y verificaciones: [documentación del proyecto](docs/ia-agentica/README.md).
Repositorio vigente desde el 05/10/2026: `https://github.com/Virtual-IA-Technologies/abissol-v2.git`. Publicación directa en main autorizada el 05/10/2026.
