"""Durable, non-retrying delivery of documents for newly committed sales."""
import hashlib
from fastapi import HTTPException
from ..models.medical import MedicalDispatch,MedicalInvoice,MedicalIssuance
from . import medical_billing as fiscal
from .medical_testing import check_delivery

KIND='insured_auto'

def enqueue(db,emission,actor_id):
    if not fiscal.configuration(db)[1].get('automatic_documents_enabled'):return
    for channel,recipient in [('email',emission.email),('whatsapp',emission.phone)]:
        if not recipient:continue
        status,error='pending',''
        if emission.test_batch:
            try:check_delivery(db,emission,channel,recipient,True)
            except HTTPException:
                status,error='simulated','PRUEBA: destinatario no autorizado; no se contactó al proveedor.'
        db.add(MedicalDispatch(issuance_id=emission.id,kind=KIND,channel=channel,recipient=recipient,status=status,error=error,created_by=actor_id))

def receipt(db,emission):
    invoice=db.query(MedicalInvoice).filter_by(issuance_id=emission.id,deleted_at=None).first()
    if not invoice:return None
    digest=(invoice.details or {}).get('files',{}).get('PDF')
    if not digest:return None
    path=fiscal.artifact_path(invoice,'PDF')
    content=path.read_bytes()
    if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('Integridad del comprobante no válida')
    return invoice.full_number+'.pdf',content,'application/pdf'

def process(db,ident):
    from ..models import Usuario
    from ..routes import medical as m
    row=db.query(MedicalDispatch).filter_by(id=ident,kind=KIND,status='pending').with_for_update().first()
    if not row:return
    emission=db.get(MedicalIssuance,row.issuance_id)
    if not fiscal.configuration(db)[1].get('automatic_documents_enabled'):return
    if not emission or emission.status!='issued':
        row.status='failed';row.error='La emisión ya no está disponible para envío.';db.commit();return
    # A real invoice may still be rendering in the fiscal worker. Wait for its PDF.
    invoice=db.query(MedicalInvoice).filter_by(issuance_id=emission.id,deleted_at=None).first()
    if invoice and not (invoice.details or {}).get('files',{}).get('PDF'):return
    try:
        check_delivery(db,emission,row.channel,row.recipient,bool(emission.test_batch))
    except HTTPException:
        row.status='simulated';row.error='PRUEBA: envío real no autorizado actualmente.';db.commit();return
    m.deliver(db,None,db.get(Usuario,row.created_by),row,emission,real_test=bool(emission.test_batch))

def run_pending():
    from ..database import SessionLocal
    with SessionLocal() as db:
        ids=[r.id for r in db.query(MedicalDispatch.id).filter_by(kind=KIND,status='pending').order_by(MedicalDispatch.id).limit(20)]
    for ident in ids:
        try:
            with SessionLocal() as db:process(db,ident)
        except Exception:
            # Never repeat a provider attempt automatically; keep an inspectable result.
            with SessionLocal() as db:
                row=db.get(MedicalDispatch,ident)
                if row and row.status in ('pending','sending'):
                    row.status='failed';row.error='No se confirmó el envío automático. Revisar antes de reenviar.';db.commit()
    return len(ids)
