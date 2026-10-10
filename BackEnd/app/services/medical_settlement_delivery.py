"""Durable office notification; no automatic retries after an uncertain SMTP result."""
from ..models.medical import MedicalDispatch, MedicalLiquidation, MedicalProfile, MedicalVoucher
from .email import send_email

KIND='settlement_office'

def deliver(db, ident):
    from ..routes import medical as m
    row=db.query(MedicalDispatch).filter_by(id=ident,kind=KIND).with_for_update().first()
    if not row or row.status!='queued':return
    row.status='sending';row.attempts+=1;db.commit()
    try:
        settlement=db.get(MedicalLiquidation,row.liquidation_id)
        owner=db.get(MedicalProfile,settlement.responsible_id)
        vouchers=db.query(MedicalVoucher).filter_by(liquidation_id=settlement.id,active=True).all()
        files=[(v.filename,(m.STORAGE/v.storage_key).read_bytes(),'application/pdf' if v.filename.lower().endswith('.pdf') else 'image/png' if v.filename.lower().endswith('.png') else 'image/jpeg') for v in vouchers]
        text=(f'Oficina Principal:\n\nSe ha enviado la liquidación {settlement.code} para su revisión.\n'
              f'Responsable: {owner.display_name}\nMonto: S/ {settlement.deposit_required:.2f}\n\n'
              f'Comentarios:\n{settlement.notes}\n\n'
              'Revise el voucher y confirme la liquidación en:\nhttps://v2.abissol.org/plataforma/medical/liquidations')
        recipients=row.recipient.split(', ')
        send_email(db,recipients[0],f'ABISSOL - Liquidación enviada {settlement.code}',text,attachments=files,cc=', '.join(recipients[1:]) or None)
        row.status='sent';row.error=''
    except Exception:
        row.status='uncertain';row.error='No se confirmó el correo. Revisar recepción antes de reenviar.'
    db.commit()

def run():
    from ..database import SessionLocal
    with SessionLocal() as db:
        ids=[ident for ident, in db.query(MedicalDispatch.id).filter_by(kind=KIND,status='queued').order_by(MedicalDispatch.id).limit(20)]
        for ident in ids:deliver(db,ident)
    return len(ids)
