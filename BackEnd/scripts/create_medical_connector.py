"""Provision a source-only technical credential; token goes to a private file."""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models import Usuario
from app.models.medical import MedicalSource, MedicalIntegrationCredential
from app.routes.auth import hash_password


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--test-only',action='store_true')
    args=parser.parse_args()
    if args.output.exists():
        raise SystemExit('El archivo de salida ya existe; no se sobrescribe una credencial.')
    token=secrets.token_urlsafe(48)
    with SessionLocal() as db:
        source=db.query(MedicalSource).filter_by(external_key=args.source,active=True).one()
        username='connector-'+args.source
        actor=db.query(Usuario).filter_by(username=username).first()
        if not actor:
            actor=Usuario(nombre='Conector '+source.code,apellido='',username=username,correo=username+'@integrations.invalid',
                contrasena=hash_password(secrets.token_urlsafe(48)),requiere_cambio_clave=True,is_active=True)
            db.add(actor);db.flush()
        # Do not reuse an account that acquired platform privileges.
        if actor.active_roles() or actor.deleted_at or not actor.is_active:
            raise SystemExit('La cuenta técnica tiene permisos o estado no admitidos.')
        db.add(MedicalIntegrationCredential(source_id=source.id,actor_id=actor.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),active=True,test_only=args.test_only))
        fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'w') as handle: handle.write(token)
            db.commit()
        except BaseException:
            args.output.unlink(missing_ok=True)
            raise
    print('Credencial creada en el archivo privado indicado; acceso limitado al origen.')


if __name__=='__main__':
    main()
