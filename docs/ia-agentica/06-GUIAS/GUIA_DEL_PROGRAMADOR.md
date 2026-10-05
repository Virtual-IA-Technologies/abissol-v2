# Guía del programador

Los comandos completos están en el README de la raíz. Requisitos: Python 3.14,
Node.js 24 y MariaDB local. No reutilizar `.env`, bases ni usuarios del origen.

Instalar dependencias, configurar BackEnd/.env, aplicar `python scripts/migrate.py`
y ejecutar `python seed_core.py`. Este último crea menús y cuenta inicial, y sincroniza
la biblioteca documental con audiencias técnicas/internas separadas del manual.

Después de editar documentación, desde BackEnd ejecutar:

```python
from app.database import SessionLocal
from app.services.documentation import sync_repository
with SessionLocal() as db:
    print(sync_repository(db))
```

Comprobar previamente `DB_HOST`, `DB_NAME` y `EXPECTED_DB_NAME`, sin imprimir secretos.
Este proyecto local usa exclusivamente `127.0.0.1 / abissol_v2_local`.

Pruebas: `python -m unittest discover -s tests -v`. Esquema: `python -m alembic check`.
Frontend: `npm run build`. No es necesario encender servicios externos para estas pruebas.
