"""Two Lima daily cutoffs; pending real emissions only, no blind retries."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from ..models.medical import MedicalBusinessSetting,MedicalIssuance,MedicalDispatch
from .medical_settings import business_settings

def due_slot(settings,now):
    local=now.astimezone(ZoneInfo('America/Lima'))
    slots=[datetime.fromisoformat(str(local.date())+'T'+hour+':00').replace(tzinfo=local.tzinfo) for hour in {settings['daily_dispatch_time'],settings['evening_dispatch_time']}]
    return max((slot for slot in slots if slot<=local),default=None)

def process(db,now=None):
    from ..models import Usuario
    from ..routes.medical_workspaces import send_meta,META_KIND
    settings=business_settings(db)
    if not settings['meta_auto_enabled']:return {'status':'disabled','count':0}
    slot=due_slot(settings,now or datetime.now(timezone.utc))
    if slot is None:return {'status':'waiting','count':0}
    state=db.query(MedicalBusinessSetting).filter_by(id=2).with_for_update().first()
    if not state or not state.values.get('actor_id'):return {'status':'unconfigured','count':0}
    if state.values.get('last_slot','')>=slot.isoformat():return {'status':'checked','count':0}
    previous=db.query(MedicalDispatch.id).filter(MedicalDispatch.issuance_id==MedicalIssuance.id,MedicalDispatch.kind==META_KIND).exists()
    emissions=db.query(MedicalIssuance).filter(MedicalIssuance.test_batch.is_(None),MedicalIssuance.status=='issued',
        MedicalIssuance.created_at<=slot.astimezone(timezone.utc).replace(tzinfo=None),~previous).order_by(MedicalIssuance.id).with_for_update().all()
    state.values={**state.values,'last_slot':slot.isoformat()}
    if not emissions:
        db.commit();return {'status':'empty','count':0}
    return send_meta(db,None,db.get(Usuario,state.values['actor_id']),emissions,META_KIND)

def run():
    from ..database import SessionLocal
    with SessionLocal() as db:return process(db)
