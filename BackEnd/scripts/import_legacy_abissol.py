"""Ejecutar solo en el servidor ABISSOL. Simulación por defecto; --apply confirma.

La instantánea privada debe crearse antes del respaldo definitivo y de aplicar.
Nunca pasar claves por argumentos ni traer la instantánea al repositorio.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--create-snapshot', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--operator-email')
    parser.add_argument('--source-root', type=Path, default=Path('/home/abissol/public_html/api.abissol.org'))
    args = parser.parse_args()
    if os.name != 'posix' or not args.snapshot.is_absolute() or '/public_html/' in str(args.snapshot):
        parser.error('Se requiere servidor Linux y una instantánea privada fuera de public_html.')
    from app.services.legacy_import import Importer, ImportFailure, packed
    if args.create_snapshot:
        import pymysql
        conn = pymysql.connect(read_default_file='/root/.my.cnf', database='abissol_laravel', cursorclass=pymysql.cursors.DictCursor)
        try:
            with conn.cursor() as cursor:
                cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                cursor.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
                cursor.execute('SHOW TABLES')
                names = [next(iter(r.values())) for r in cursor.fetchall()]
                data = {}
                for name in names:
                    if name.startswith(('medical_', 'billing_')) or name in {'users', 'roles', 'permissions', 'model_has_roles', 'role_has_permissions', 'model_has_permissions', 'documents'}:
                        cursor.execute('SELECT * FROM `' + name + '`')
                        data[name] = cursor.fetchall()
            fd = os.open(args.snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(packed(data))
            print(json.dumps({'snapshot_created': True, 'counts': {t: len(r) for t, r in data.items()}}))
        finally:
            conn.rollback(); conn.close()
        return
    from datetime import datetime
    from app.database import SessionLocal, engine
    from app.models import Usuario
    if engine.url.database != 'abissol_v2':
        parser.error('Destino permitido: abissol_v2; nunca ejecutar sobre Laravel.')
    if not args.operator_email:
        parser.error('Es obligatorio identificar al administrador V2.')
    data = json.loads(args.snapshot.read_text(encoding='utf-8'))
    # PyMySQL retorna fechas reales; JSON las conserva con representación ISO.
    for rows in data.values():
        for row in rows:
            for key, value in row.items():
                if value and isinstance(value, str) and (key.endswith('_at') or key in {'sale_date', 'period_start', 'period_end', 'issue_date', 'due_date', 'payment_date', 'start_date', 'end_date'}):
                    try:
                        row[key] = datetime.fromisoformat(value) if ' ' in value or 'T' in value else datetime.fromisoformat(value).date()
                    except ValueError:
                        pass
    with SessionLocal() as db:
        operator = db.query(Usuario).filter_by(correo=args.operator_email, is_active=True).one()
        if not any(r.es_superusuario for r in operator.active_roles()):
            parser.error('El operador debe tener rol Programador activo.')
        importer = Importer(db, data, args.source_root, Path(__file__).resolve().parents[1] / 'storage', operator.id, copy_files=args.apply)
        try:
            result = importer.run()
            if args.apply:
                if result['new_records']:
                    from app.models import AuditLog
                    db.add(AuditLog(usuario_id=operator.id, actor_usuario_id=operator.id, accion='crear', modulo='abissol_medical',
                        entidad='legacy_import', entidad_id='abissol_laravel', detalle='Migración autorizada de datos reales ABISSOL; instantánea privada y archivos originales conservados.',
                        datos_despues=json.dumps(result), metodo='CLI'))
                db.commit()
            else:
                db.rollback()
            print(json.dumps({'applied': args.apply, **result}))
        except ImportFailure as exc:
            db.rollback()
            print(str(exc), file=sys.stderr)
            raise SystemExit(2)
        except Exception as exc:
            db.rollback()
            # SQLAlchemy agrega parámetros con hashes/PII al traceback: NO imprimir.
            print(f'Importación revertida: {type(exc).__name__}. Revisar el informe privado del servidor.', file=sys.stderr)
            import traceback
            log = args.snapshot.with_suffix('.error.log')
            fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                traceback.print_exc(file=f)
            raise SystemExit(3)


if __name__ == '__main__':
    main()
