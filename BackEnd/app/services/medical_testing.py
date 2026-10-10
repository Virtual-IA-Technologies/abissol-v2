"""Disposable local previews: no fiscal reservation, signature or network send."""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from lxml import etree
from fastapi import HTTPException
from ..models.medical import MedicalInvoice
from . import medical_billing as fiscal

def batch(db,lock=False):
    return fiscal.configuration(db,lock=lock)[1].get('test_batch') or None


def check_delivery(db, emission, channel, recipient, real_test=False):
    if not emission.test_batch or not real_test:return
    import re
    raw=fiscal.configuration(db)[1]
    normalize=(lambda value: str(value).strip().lower()) if channel=='email' else (lambda value: re.sub(r'\D','',str(value)))
    allowed=raw.get('test_delivery_emails' if channel=='email' else 'test_delivery_phones',[])
    if not raw.get('test_batch') or normalize(recipient) not in {normalize(v) for v in allowed}:
        raise HTTPException(403,'Destinatario no autorizado para recepción real de pruebas. El envío fiscal permanece bloqueado.')

def activate(db,enabled):
    row,raw=fiscal.configuration(db,lock=True)
    if not row:raise HTTPException(422,'Falta la configuración fiscal')
    # Disabling tests never enables fiscal sending implicitly.
    raw['enabled_in_v2']=False
    raw['test_batch']=(raw.get('test_batch') or 'PRUEBA-'+uuid4().hex[:20]) if enabled else None
    fiscal.persist_config(row,raw)
    return raw['test_batch']

def preview(db,emission):
    existing=db.query(MedicalInvoice).filter_by(issuance_id=emission.id).first()
    if existing:return existing
    _,raw=fiscal.configuration(db)
    preference=emission.billing_preference or {}
    invoice_type=preference.get('invoice_type_code','03')
    is_invoice=invoice_type=='01'
    number=str(int(uuid4().hex[:12],16))
    series='TF00' if is_invoice else 'TB00'
    details={'test_batch':emission.test_batch,'environment':'local_test','items':fiscal.sunat.plan_items(emission.plan_name,emission.price),
        'customer_document_type':preference.get('customer_document_type') or emission.document_type,
        'customer_address':preference.get('customer_address',''),'customer_ubigeo':preference.get('customer_ubigeo',''),
        'customer_email':emission.email,'due_date':preference.get('due_date'),'invoice_type_code':invoice_type,
        'payment_terms':'Credito' if is_invoice and preference.get('due_date') else 'Contado',
        'issuer':{k:raw.get(k) for k in fiscal.PUBLIC_FIELDS},'issue_time':datetime.now(ZoneInfo('America/Lima')).strftime('%H:%M:%S'),
        'tax_amount':'0.00','unaffected_amount':str(emission.price),'files':{},'sunat_logs':[],'unsigned_preview':True}
    row=MedicalInvoice(issuance_id=emission.id,draft_key=emission.id,document_type='factura' if is_invoice else 'boleta',
        customer=preference.get('customer_name') or emission.customer,document_number=preference.get('customer_document_number') or emission.document_number,
        total=emission.price,status='generated',sunat_status='test_not_sent',full_number=series+'-'+number,
        issue_date=emission.sale_date,payment_status='pending' if emission.payment_status=='pending' else 'paid',created_by=emission.created_by,details=details)
    db.add(row);db.flush()
    config={**raw,**details['issuer'],'document_type_code':invoice_type}
    xml=etree.tostring(fiscal.sunat.build_invoice(config,row,details['items']),encoding='UTF-8',xml_declaration=True)
    # Deliberately unsigned XML and invalid fiscal series; never creates FiscalJob.
    contents={'PDF':fiscal.printable_pdf(row,''),'Ticket':fiscal.printable_pdf(row,'',True),'XML':xml,
              'ZIP':fiscal.sunat.package_xml('PRUEBA-'+row.full_number,xml)}
    files={}
    for kind,content in contents.items():
        db.info.setdefault('archive_files',[]).append(fiscal.artifact_path(row,kind))
        files[kind]=fiscal.write_artifact(row,kind,content)
    row.details={**details,'files':files}
    from .medical_documents import invoice
    invoice(db,row)
    return row
