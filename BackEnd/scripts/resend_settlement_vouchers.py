"""Explicit, idempotent reissue of real seller vouchers with the current format."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal,engine
from app.models.medical import MedicalLiquidation as L,MedicalVoucher as V,MedicalDispatch as D,MedicalBusinessSetting
from app.services.medical_settlement_delivery import RESEND_KIND,deliver,message,office_recipients,ADDITIONAL_RECIPIENT
from app.services.medical_settings import business_settings
from app.routes.medical import STORAGE

parser=argparse.ArgumentParser()
parser.add_argument('--expected-database',required=True)
parser.add_argument('--send',action='store_true')
parser.add_argument('--expected-count',type=int,required=True)
args=parser.parse_args()
if engine.url.database!=args.expected_database:raise SystemExit('Base distinta de la esperada')
with SessionLocal() as db:
    settings=business_settings(db)
    recipient=office_recipients(settings)
    if not settings['settlement_office_email'] or len(recipient)>180:raise SystemExit('Revisa destinatarios')
    candidates=db.query(L).filter(L.kind=='seller',L.status!='cancelled',~L.code.like('PRUEBA-%')).order_by(L.id).all()
    rows=[]
    for row in candidates:
        vouchers=db.query(V).filter_by(liquidation_id=row.id,active=True).all()
        if not vouchers:continue
        message(db,row)
        for v in vouchers:
            if hashlib.sha256((STORAGE/v.storage_key).read_bytes()).hexdigest()!=v.digest:
                raise SystemExit(f'Integridad incorrecta voucher {v.id}')
        rows.append(row)
    if len(rows)!=args.expected_count:raise SystemExit(f'Se esperaban {args.expected_count}; encontrados {len(rows)}')
    print(json.dumps({'count':len(rows),'recipients':recipient,'liquidation_ids':[r.id for r in rows]}),flush=True)
    if args.send:
        # Persist the additional copy in settings as well as enforcing it in delivery.
        settings['settlement_office_cc']=', '.join(dict.fromkeys([i.strip() for i in settings['settlement_office_cc'].split(',') if i.strip()]+[ADDITIONAL_RECIPIENT]))
        setting=db.get(MedicalBusinessSetting,1)
        if not setting:setting=MedicalBusinessSetting(id=1);db.add(setting)
        setting.values=settings
        db.commit()
        for row in rows:
            db.query(L).filter_by(id=row.id).with_for_update().one()
            attempt=db.query(D).filter_by(liquidation_id=row.id,kind=RESEND_KIND).first()
            if not attempt:
                attempt=D(liquidation_id=row.id,kind=RESEND_KIND,channel='email',recipient=recipient,status='queued',created_by=row.created_by)
                db.add(attempt);db.commit()
                deliver(db,attempt.id)
            else:db.commit()
            print(json.dumps({'liquidation_id':row.id,'dispatch_id':attempt.id,'status':attempt.status}),flush=True)
