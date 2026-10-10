"""Durable outbox consumer; systemd ensures only one instance is running."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.database import SessionLocal
from app.models.fiscal import FiscalJob
from app.services.medical_billing import process_job
from app.utils.time import utc_now

def run():
    with SessionLocal() as db:
        ids = [row.id for row in db.query(FiscalJob.id).filter(FiscalJob.state.in_(['queued','sending','uncertain']),FiscalJob.next_attempt_at <= utc_now()).order_by(FiscalJob.id).limit(20)]
    try:
        for ident in ids:
            with SessionLocal() as db:
                process_job(db,ident)
        print('Fiscal jobs checked:',len(ids))
    finally:
        from app.services.medical_auto_delivery import run_pending
        print('Automatic document deliveries checked:',run_pending())
        from app.services.medical_meta_schedule import run as run_meta
        print('META schedule:',run_meta())

if __name__ == '__main__':
    run()
