"""Idempotent archive backfill; no fiscal generation, provider calls or mail."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal,engine
from app.models import Usuario,Rol
from app.services.medical_documents import sync

parser=argparse.ArgumentParser()
parser.add_argument('--expected-database',required=True)
args=parser.parse_args()
if engine.url.database!=args.expected_database:raise SystemExit('Base distinta de la esperada')
with SessionLocal() as db:
    actor=db.query(Usuario).filter(Usuario.is_active.is_(True),Usuario.deleted_at.is_(None),Usuario.roles.any(Rol.nombre=='Programador')).order_by(Usuario.id).first()
    if not actor:raise SystemExit('Falta una cuenta Programador para la trazabilidad del archivo')
    print(json.dumps(sync(db,actor.id),ensure_ascii=True))
