"""Durable office notification; no automatic retries after an uncertain SMTP result."""
from html import escape
import hashlib
from ..models.medical import MedicalDispatch, MedicalLiquidation, MedicalProfile, MedicalVoucher, MedicalIssuance, MedicalLiquidationItem
from .email import send_email

KIND='settlement_office'
RESEND_KIND='settlement_office_format_v2'
ADDITIONAL_RECIPIENT='abbisol.hampi@gmail.com'

def office_recipients(settings):
    return ', '.join(dict.fromkeys(i.strip().lower() for value in
        [settings['settlement_office_email'],settings['settlement_office_cc'],ADDITIONAL_RECIPIENT]
        for i in value.split(',') if i.strip()))

def message(db, settlement):
    entries=db.query(MedicalIssuance).join(MedicalLiquidationItem,
        MedicalLiquidationItem.issuance_id==MedicalIssuance.id).filter(
        MedicalLiquidationItem.liquidation_id==settlement.id).order_by(MedicalIssuance.id).all()
    if not entries or any(e.test_batch for e in entries):
        raise ValueError('Se requieren emisiones reales para enviar el comprobante')
    owner=db.get(MedicalProfile,settlement.responsible_id)
    signature=owner.display_name if owner else 'ABISSOL'
    plans=', '.join(dict.fromkeys(e.plan_name for e in entries))
    subject=f"ENVIO DE COMPROBANTE DE PAGO: {plans} ({', '.join(e.customer for e in entries)})"
    intro=f'Estimados, buenos d?as.\nAdjunto el comprobante de pago correspondiente al seguro {plans}.'
    blocks=[];html_blocks=[]
    for e in entries:
        validity=f'{e.starts_on:%d/%m/%Y} AL {e.ends_on:%d/%m/%Y}'
        label='DNI' if e.document_type.lower() in {'dni','1','01'} else e.document_type.upper()
        blocks.append(f'DATOS DEL ASEGURADO:\nCLIENTE: {e.customer}\n{label}: {e.document_number}\nVIGENCIA: {validity}')
        html_blocks.append(f'<p><b>DATOS DEL ASEGURADO:<br>CLIENTE: {escape(e.customer)}<br>{escape(label)}: {escape(e.document_number)}<br>VIGENCIA: <span style="background-color:#ffff00">{validity}</span></b></p>')
    closing='Por favor, esperamos respuesta de conformidad a la liquidaci?n de esta venta.'
    text=intro+'\n\n'+'\n\n'.join(blocks)+'\n\n'+closing+'\n\nSaludos cordiales,\n'+signature
    html='<div style="font-family:Arial,sans-serif;font-size:14px;color:#333"><p>'+escape(intro).replace('\n','<br>')+'</p>'+''.join(html_blocks)+'<p>'+closing+'</p><p>Saludos cordiales,<br>'+escape(signature)+'</p></div>'
    return subject,text,html


def deliver(db, ident):
    from ..routes import medical as m
    row=db.query(MedicalDispatch).filter(MedicalDispatch.id==ident,MedicalDispatch.kind.in_([KIND,RESEND_KIND])).with_for_update().first()
    if not row or row.status!='queued':return
    row.status='sending';row.attempts+=1;db.commit()
    try:
        settlement=db.get(MedicalLiquidation,row.liquidation_id)
        owner=db.get(MedicalProfile,settlement.responsible_id)
        vouchers=db.query(MedicalVoucher).filter_by(liquidation_id=settlement.id,active=True).all()
        if not vouchers:raise ValueError('Falta el voucher adjunto')
        files=[]
        for v in vouchers:
            content=(m.STORAGE/v.storage_key).read_bytes()
            if hashlib.sha256(content).hexdigest()!=v.digest:raise ValueError('Integridad del voucher no v?lida')
            mime='application/pdf' if v.filename.lower().endswith('.pdf') else 'image/png' if v.filename.lower().endswith('.png') else 'image/jpeg'
            files.append((v.filename,content,mime))
        subject,text,html=message(db,settlement)
        recipients=list(dict.fromkeys(i.strip().lower() for i in (row.recipient+','+ADDITIONAL_RECIPIENT).split(',') if i.strip()))
        row.recipient=', '.join(recipients)
        send_email(db,recipients[0],subject,text,html=html,attachments=files,cc=', '.join(recipients[1:]) or None)
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
