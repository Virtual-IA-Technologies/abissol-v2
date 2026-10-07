"""Atomic numbering, private fiscal configuration, and durable SUNAT outbox."""
import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from ..models.fiscal import FiscalJob
from ..models.legacy import LegacyFile, MedicalBillingConfiguration
from ..models.medical import MedicalInvoice, MedicalIssuance
from ..utils.secrets import decrypt_secret, encrypt_secret
from ..utils.time import utc_now
from . import sunat

STORAGE = Path(__file__).resolve().parents[2] / 'storage'
PUBLIC_FIELDS = ('company_name','trade_name','ruc','address','ubigeo','department','province','district','phone','email','provider','environment','igv_percent','sunat_address_type_code')


def programmer(user):
    return any(role.nombre.casefold() == 'programador' for role in user.active_roles())


def configuration(db, lock=False):
    query = db.query(MedicalBillingConfiguration).order_by(MedicalBillingConfiguration.id.desc())
    row = query.with_for_update().first() if lock else query.first()
    return row, json.loads(decrypt_secret(row.payload_encrypted)) if row else {}


def persist_config(row, data):
    row.payload_encrypted = encrypt_secret(json.dumps(data, ensure_ascii=False))


def certificate_bytes(db, config):
    file = db.get(LegacyFile, config.get('certificate_path_file_id')) if config.get('certificate_path_file_id') else None
    root = STORAGE / 'legacy_abissol'
    path = (root / file.storage_key).resolve() if file else None
    if not path or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise sunat.FiscalError('No se encontró el certificado digital conservado.')
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != file.sha256:
        raise sunat.FiscalError('No coincide la integridad del certificado digital.')
    return content


def validate_configuration(db, raw):
    for field in ('ruc','company_name','address','ubigeo','department','province','district','sol_user','sol_password'):
        if not str(raw.get(field) or '').strip():
            raise sunat.FiscalError('Configuración incompleta: '+field)
    if not re.fullmatch(r'\d{11}',str(raw['ruc'])) or not re.fullmatch(r'\d{6}',str(raw['ubigeo'])):
        raise sunat.FiscalError('RUC o ubigeo del emisor inválido.')
    if raw.get('environment') not in sunat.ENDPOINTS or raw.get('provider') != 'sunat_soap':
        raise sunat.FiscalError('Selecciona SUNAT SOAP y un entorno válido.')
    series = raw.get('v2_series', '')
    if not re.fullmatch(r'B[A-Z0-9]{3}',series):
        raise sunat.FiscalError('La serie exclusiva V2 debe tener B y tres caracteres alfanuméricos.')
    if series in {s.get('series') for s in raw.get('series', [])}:
        raise sunat.FiscalError('La serie sigue reservada al sistema anterior. Utiliza una exclusiva de V2.')
    invoice_series=raw.get('v2_invoice_series','')
    if invoice_series and (not re.fullmatch(r'F[A-Z0-9]{3}',invoice_series) or invoice_series in {s.get('series') for s in raw.get('series',[])}):
        raise sunat.FiscalError('La serie de factura debe ser exclusiva V2: F y tres caracteres alfanuméricos.')
    key, cert = sunat.read_certificate(certificate_bytes(db, raw),raw.get('certificate_password'))
    if raw['environment'] == 'production' and raw['ruc'] not in cert.subject.rfc4514_string():
        raise sunat.FiscalError('El RUC configurado no aparece en el titular del certificado.')
    return key, cert


def public_configuration(db):
    _, raw = configuration(db)
    if not raw:
        return {'imported':False,'enabled':False,'series':[]}
    ready, problem, expires = False, '', None
    try:
        _, cert = validate_configuration(db, raw)
        ready, expires = True, cert.not_valid_after_utc.isoformat()
    except sunat.FiscalError as exc:
        problem = str(exc)
    return {**{k:raw.get(k) for k in PUBLIC_FIELDS}, 'imported':True,'enabled':bool(raw.get('enabled_in_v2')),
            'test_batch':raw.get('test_batch'),
            'ready':ready,'problem':problem,'certificate_expires_at':expires,
            'v2_series':raw.get('v2_series',''), 'v2_counter':raw.get('v2_counter',0),
            'v2_invoice_series':raw.get('v2_invoice_series',''),'v2_invoice_counter':raw.get('v2_invoice_counter',0),
            'credentials_preserved':bool(raw.get('sol_user') and raw.get('sol_password')),
            'certificate_preserved':bool(raw.get('certificate_path_file_id')),
            'series':[{k:s.get(k) for k in ('document_type','series','current_number')} for s in raw.get('series',[])],
            'distribution':{'Hampi Esencial':sunat.plan_items('Hampi Esencial',55),'Hampi Plus':sunat.plan_items('Hampi Plus',255)}}


def enqueue_boleta(db, emission):
    """Queue the requested invoice, defaulting to boleta, inside the sale transaction."""
    if emission.test_batch:
        from .medical_testing import preview
        return preview(db,emission)
    row, raw = configuration(db, lock=True)
    if not raw.get('enabled_in_v2') or emission.legacy_id:
        return None
    # Imported invoices and pending jobs both block a second fiscal document.
    existing = db.query(MedicalInvoice).filter_by(issuance_id=emission.id).first()
    if existing:
        if not existing.legacy_id and emission.payment_status != 'pending':
            existing.payment_status = 'paid'
        return existing
    try:
        items = sunat.plan_items(emission.plan_name, emission.price)
    except sunat.FiscalError as exc:
        raise HTTPException(422,str(exc)) from exc
    preference=emission.billing_preference or {}
    is_invoice=preference.get('invoice_type_code')=='01'
    series_key,counter_key=('v2_invoice_series','v2_invoice_counter') if is_invoice else ('v2_series','v2_counter')
    counter = int(raw.get(counter_key,0)) + 1
    series=raw.get(series_key,'')
    if counter > 99999999 or not re.fullmatch(r'F[A-Z0-9]{3}' if is_invoice else r'B[A-Z0-9]{3}',series):
        raise HTTPException(422,'Revisar serie y correlativo fiscal antes de emitir.')
    if series in {s.get('series') for s in raw.get('series',[])}:
        raise HTTPException(422,'La serie sigue reservada al sistema anterior.')
    number = f"{series}-{counter}"
    if db.query(MedicalInvoice.id).filter_by(full_number=number).first():
        raise HTTPException(409,'Numeración fiscal ya utilizada; revisar configuración.')
    invoice = MedicalInvoice(issuance_id=emission.id, draft_key=emission.id, document_type='factura' if is_invoice else 'boleta', customer=preference.get('customer_name') or emission.customer,
        document_number=preference.get('customer_document_number') or emission.document_number,total=emission.price,status='queued',sunat_status='queued',
        full_number=number,issue_date=datetime.now(ZoneInfo('America/Lima')).date(),
        payment_status='pending' if emission.payment_status == 'pending' else 'paid',created_by=emission.created_by,
        details={'items':items,'customer_document_type':preference.get('customer_document_type') or emission.document_type,'environment':raw['environment'],
                 'invoice_type_code':'01' if is_invoice else '03','customer_address':preference.get('customer_address',''),
                 'customer_ubigeo':preference.get('customer_ubigeo',''),'due_date':preference.get('due_date'),
                 'payment_terms':'Credito' if is_invoice and emission.payment_status=='pending' else 'Contado',
                 'issue_time':datetime.now(ZoneInfo('America/Lima')).strftime('%H:%M:%S'),
                 'issuer':{k:raw.get(k) for k in PUBLIC_FIELDS},'tax_amount':'0.00','unaffected_amount':str(emission.price),'files':{},'sunat_logs':[]})
    db.add(invoice)
    db.flush()
    db.add(FiscalJob(invoice_id=invoice.id,environment=raw['environment'],series=series,number=counter))
    raw[counter_key] = counter
    persist_config(row,raw)
    return invoice


def artifact_path(invoice, kind):
    extensions = {'XML':'xml','ZIP':'zip','PDF':'pdf','Ticket':'pdf','CDR':'zip'}
    if kind not in extensions:
        raise sunat.FiscalError('Tipo de archivo inválido.')
    return STORAGE / 'fiscal' / str(invoice.id) / (kind+'.'+extensions[kind])


def write_artifact(invoice, kind, content):
    path = artifact_path(invoice,kind)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_bytes(content)
    temporary.replace(path)
    return hashlib.sha256(content).hexdigest()


def printable_pdf(invoice, digest, ticket=False):
    from .medical_rendering import invoice as render_invoice
    return render_invoice(invoice,digest,ticket)


def log_result(invoice, action, status, message=''):
    data = dict(invoice.details)
    data['sunat_logs'] = [*data.get('sunat_logs',[]),dict(action=action,status=status,created_at=utc_now().isoformat(),message=message) ][-100:]
    invoice.details = data


def prepare_artifacts(db,invoice,job,raw):
    if (invoice.details or {}).get('test_batch'):
        raise sunat.FiscalError('Un comprobante de prueba nunca se firma ni se convierte en real.')
    config={**raw,**invoice.details['issuer'],'environment':job.environment}
    config['v2_invoice_series' if invoice.document_type=='factura' else 'v2_series']=job.series
    config['document_type_code']='01' if invoice.document_type=='factura' else '03'
    if job.sent_at:
        return config
    key,cert=validate_configuration(db,config)
    today=datetime.now(ZoneInfo('America/Lima')).date()
    if not today-timedelta(days=1)<=invoice.issue_date<=today:
        raise sunat.FiscalError('Comprobante sin enviar fuera de la ventana operativa de hoy/ayer: requiere revisión del programador.')
    root=sunat.build_invoice(config,invoice,invoice.details['items'])
    xml,digest=sunat.sign_xml(root,key,cert)
    name=config['ruc']+'-'+config['document_type_code']+'-'+invoice.full_number
    data=dict(invoice.details)
    data['digest']=digest
    data['files']={kind:write_artifact(invoice,kind,content) for kind,content in (
        ('XML',xml),('ZIP',sunat.package_xml(name,xml)),('PDF',printable_pdf(invoice,digest)),('Ticket',printable_pdf(invoice,digest,True)))}
    invoice.details=data
    invoice.status='generated'
    from .medical_documents import invoice as archive_invoice
    archive_invoice(db,invoice)
    return config


def process_job(db, ident):
    job = db.query(FiscalJob).filter_by(id=ident).with_for_update().first()
    if not job or job.state in {'accepted','rejected','blocked'} or job.next_attempt_at > utc_now():
        return
    _, raw = configuration(db)
    if not raw.get('enabled_in_v2') or raw.get('test_batch'):
        return
    invoice = db.get(MedicalInvoice,job.invoice_id)
    if (invoice.details or {}).get('test_batch'):
        return
    # Snapshot public issuer/environment; current private credentials stay private.
    config = {**raw,**invoice.details['issuer'],'environment':job.environment}
    config['v2_invoice_series' if invoice.document_type=='factura' else 'v2_series'] = job.series
    config['document_type_code']='01' if invoice.document_type=='factura' else '03'
    try:
        if not job.sent_at:
            config=prepare_artifacts(db,invoice,job,raw)
            name = config['ruc']+'-'+config['document_type_code']+'-'+invoice.full_number
            job.sent_at,job.state = utc_now(),'sending'
            job.next_attempt_at = utc_now()+timedelta(minutes=5)
            job.attempts += 1
            invoice.status,invoice.sunat_status = 'generated','pending'
            log_result(invoice,'sendBill','pending')
            db.commit()  # Durable intent BEFORE the remote call: crashes only query CDR.
            content = sunat.send_bill(config,name,artifact_path(invoice,'ZIP').read_bytes())
        else:
            # No automatic resend after an uncertain response, including restarts.
            job.next_attempt_at = utc_now()+timedelta(minutes=5)
            db.commit()
            content = sunat.query_cdr(config,invoice.full_number)
        result = sunat.cdr_result(content,invoice.full_number,config['ruc'])
        data = dict(invoice.details)
        data['files'] = {**data['files'],'CDR':write_artifact(invoice,'CDR',content)}
        data.update(sunat_message=result['message'],sunat_code=result['code'],sunat_notes=result['notes'])
        invoice.details = data
        from .medical_documents import invoice as archive_invoice
        archive_invoice(db,invoice)
        job.state,job.error = result['status'],None
        invoice.sunat_status = result['status']
        invoice.status = 'issued' if result['status']=='accepted' else 'rejected'
        log_result(invoice,'CDR',result['status'],result['message'])
        db.commit()
    except Exception as exc:
        # Raw exceptions may contain credentials or customer data: never persist them.
        safe = str(exc) if isinstance(exc,sunat.FiscalError) else 'No se pudo completar la conexión o generación fiscal. Revisar el servicio.'
        db.rollback()
        job = db.get(FiscalJob,ident)
        if job.state in {'accepted','rejected'}:
            return
        invoice = db.get(MedicalInvoice,job.invoice_id)
        job.state = 'uncertain' if job.sent_at else 'blocked'
        job.error, job.next_attempt_at = safe,utc_now()+timedelta(minutes=5)
        invoice.sunat_status = job.state
        log_result(invoice,'consulta' if job.sent_at else 'generacion',job.state,safe)
        db.commit()
