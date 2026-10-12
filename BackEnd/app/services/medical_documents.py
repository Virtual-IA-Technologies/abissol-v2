"""Versioned business archive. Public documents only; never archive configuration or keys."""
import hashlib
import io
import json
import mimetypes
import os
import shutil
from pathlib import Path
from uuid import uuid4
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..models.documents import Document,DocumentBinding,DocumentFolder,DocumentVersion
from ..models.legacy import LegacyFile
from ..utils.time import utc_now
from . import documents


@event.listens_for(Session,'after_commit')
def keep_archive_files(db):
    if not db.in_nested_transaction():db.info.pop('archive_files',None)


@event.listens_for(Session,'after_rollback')
def rollback_archive_files(db):
    if not db.in_nested_transaction():
        for path in db.info.pop('archive_files',[]):path.unlink(missing_ok=True)


def binding(db,source,ident,key):
    return db.query(DocumentBinding).filter_by(source_type=source,source_id=ident,artifact_key=key).first()


def folders(db,actor,path):
    parent=None
    for key,name in path:
        row=db.query(DocumentFolder).filter_by(system_key=key).with_for_update().first()
        if not row:
            try:
                with db.begin_nested():
                    row=DocumentFolder(owner_id=actor,parent_id=parent,name=name[:180],system_key=key)
                    db.add(row);db.flush()
            except IntegrityError:
                row=db.query(DocumentFolder).filter_by(system_key=key).with_for_update().one()
        parent=row.id
    return parent


def archive(db,*,source,ident,key,actor,path,filename,content=None,file_path=None,expected_hash=None,description=''):
    suffix=Path(filename).suffix.lower()
    if suffix not in {'.pdf','.xml','.zip','.png','.jpg','.jpeg','.webp','.xlsx','.docx','.pptx','.txt','.md'}:
        raise ValueError('Formato no permitido en el archivo de negocio')
    stream=Path(file_path).open('rb') if file_path else io.BytesIO(content)
    with stream:
        digest=hashlib.file_digest(stream,'sha256').hexdigest()
        size=stream.seek(0,2);stream.seek(0)
        if not size or size>500*1024*1024:raise ValueError('Archivo vacío o demasiado grande')
        if expected_hash and expected_hash!=digest:raise ValueError('No coincide la integridad del documento original')
        folder_id=folders(db,actor,path)
        bound=db.query(DocumentBinding).filter_by(source_type=source,source_id=ident,artifact_key=key).with_for_update().first()
        doc=db.get(Document,bound.document_id) if bound else None
        if doc:
            # Reorganizing a bound document must not duplicate its binary or version.
            if doc.folder_id != folder_id:
                doc.folder_id=folder_id;doc.updated_at=utc_now()
            latest=db.query(DocumentVersion).filter_by(document_id=doc.id,number=doc.current_version).one()
            if latest.sha256==digest:
                documents.file_path(latest.storage_key)
                return doc
            doc.current_version+=1;doc.updated_at=utc_now()
        else:
            doc=Document(owner_id=actor,folder_id=folder_id,title=filename[:180],description=description[:1000],is_system=True,current_version=1)
            db.add(doc);db.flush()
            db.add(DocumentBinding(document_id=doc.id,source_type=source,source_id=ident,artifact_key=key))
        documents.STORAGE.mkdir(parents=True,exist_ok=True)
        storage_key=uuid4().hex+suffix
        target=documents.STORAGE/storage_key
        db.info.setdefault('archive_files',[]).append(target)
        try:
            if not file_path:raise OSError('Contenido generado en memoria')
            os.link(file_path,target)
        except OSError:
            with target.open('xb') as output:shutil.copyfileobj(stream,output,1024*1024)
        mime={'.xml':'application/xml','.zip':'application/zip'}.get(suffix) or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        db.add(DocumentVersion(document_id=doc.id,number=doc.current_version,author_id=actor,filename=filename[:180],
            storage_key=storage_key,mime=mime,size=size,sha256=digest,reason='Archivo automático del módulo de origen',processing='disabled'))
        db.flush()
        return doc


def record_path(category,row,date):
    base='abissol:'+category
    names={'emission':'Emisiones','invoice':'Facturación','liquidation':'Liquidaciones','plan':'Planes y condiciones'}
    path=[('abissol','ABISSOL'),(base,names[category])]
    if date:
        year,month=str(date.year),f'{date.month:02d}'
        path.extend([(base+':'+year,year),(base+':'+year+':'+month,month)])
    path.append((base+':record:'+str(row.id),str(getattr(row,'full_number',None) or getattr(row,'code',None) or getattr(row,'name',None) or row.id)))
    return path


def affiliate_path(row):
    """Identity is document type/number, never a mutable name or invoice buyer."""
    identity=str(row.document_type).strip().upper()+':'+str(row.document_number).strip().upper()
    key='abissol:affiliate:'+hashlib.sha256(identity.encode()).hexdigest()
    name=' '.join(row.customer.split()).upper()
    return [('abissol','ABISSOL'),('abissol:affiliates','Afiliados'),
            (key,f'{name[:140]} · {row.document_type} {row.document_number}'),
            ('abissol:affiliate:emission:'+str(row.id),row.code)]


def invoice_path(db,row):
    from ..models.medical import MedicalIssuance
    emission=db.get(MedicalIssuance,row.issuance_id) if row.issuance_id else None
    if emission:
        return affiliate_path(emission)+[('abissol:affiliate:invoice:'+str(row.id),row.full_number or str(row.id))]
    # Unlinked historical invoices are not evidence of an affiliate identity.
    return record_path('invoice',row,row.issue_date)


def organize_affiliates(db,actor):
    """Metadata-only, idempotent relocation. Original bindings/versions stay intact."""
    from ..models.medical import MedicalIssuance,MedicalInvoice
    moved=0;unlinked=0;cached={}
    def relocate(doc,path):
        nonlocal moved
        key=path[-1][0]
        if key not in cached:cached[key]=folders(db,actor,path)
        if doc.folder_id!=cached[key]:
            doc.folder_id=cached[key];doc.updated_at=utc_now();moved+=1
    for doc,row in db.query(Document,MedicalIssuance).join(DocumentBinding,DocumentBinding.document_id==Document.id).join(MedicalIssuance,MedicalIssuance.id==DocumentBinding.source_id).filter(DocumentBinding.source_type=='emission',Document.is_system.is_(True)):
        relocate(doc,affiliate_path(row))
    for doc,invoice,emission in db.query(Document,MedicalInvoice,MedicalIssuance).join(DocumentBinding,DocumentBinding.document_id==Document.id).join(MedicalInvoice,MedicalInvoice.id==DocumentBinding.source_id).outerjoin(MedicalIssuance,MedicalIssuance.id==MedicalInvoice.issuance_id).filter(DocumentBinding.source_type=='invoice',Document.is_system.is_(True)):
        if emission:
            relocate(doc,affiliate_path(emission)+[('abissol:affiliate:invoice:'+str(invoice.id),invoice.full_number or str(invoice.id))])
        else:unlinked+=1
    # Imported originals also remain browsable under their affiliate. Preserve
    # their personal ownership/shares and versions; never infer by customer name.
    from ..models.legacy import LegacyRecord
    from ..utils.secrets import decrypt_secret
    emissions={r.id:r for r in db.query(MedicalIssuance)}
    invoices={r.id:r for r in db.query(MedicalInvoice)}
    references={(r.source_table,r.source_key):r.target_id for r in db.query(LegacyRecord).filter(LegacyRecord.source_table.in_(['medical_issuances','billing_invoices']))}
    for doc,record in db.query(Document,LegacyRecord).join(LegacyRecord,LegacyRecord.target_id==Document.id).filter(LegacyRecord.source_table=='documents',Document.is_system.is_(False)):
        raw=json.loads(decrypt_secret(record.payload_encrypted))
        entity=raw.get('entity_type');ident=str(raw.get('entity_id'))
        invoice=None;emission=None
        if entity=='medical_issuance':emission=emissions.get(references.get(('medical_issuances',ident)))
        elif entity=='billing_invoice':
            invoice=invoices.get(references.get(('billing_invoices',ident)))
            if invoice:emission=emissions.get(invoice.issuance_id)
        if emission:
            path=affiliate_path(emission)
            if invoice:path+=[('abissol:affiliate:invoice:'+str(invoice.id),invoice.full_number or str(invoice.id))]
            relocate(doc,path)
    db.flush()
    return {'moved':moved,'unlinked_invoice_documents':unlinked}


def legacy_file(db,source_path):
    key=hashlib.sha256(str(source_path).replace('\\','/').encode()).hexdigest()
    return db.query(LegacyFile).filter_by(path_hash=key).first() if source_path else None


def legacy_path(file):
    root=Path(__file__).resolve().parents[2]/'storage/legacy_abissol'
    path=(root/file.storage_key).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():raise FileNotFoundError('Original histórico no disponible')
    return path


def emission(db,row,actor=None):
    from ..routes import medical as m
    path=affiliate_path(row)
    bound=binding(db,'emission',row.id,'letter')
    if bound:
        doc=db.get(Document,bound.document_id)
        folder_id=folders(db,actor or row.created_by,path)
        if doc.folder_id!=folder_id:doc.folder_id=folder_id;doc.updated_at=utc_now()
        return
    kwargs=dict(source='emission',ident=row.id,key='letter',actor=actor or row.created_by,path=path,filename=row.code+'.pdf',description='Certificado del programa · '+row.customer)
    if row.legacy_id:
        file=legacy_file(db,m.legacy_data(db,'medical_issuances',row.legacy_id).get('welcome_letter_path'))
        if not file:return
        archive(db,**kwargs,file_path=legacy_path(file),expected_hash=file.sha256)
    else:
        # Stable production verification URL; no user-supplied hosts or public storage URLs.
        from .medical_public_links import verification_url
        archive(db,**kwargs,content=m.letter_pdf(row,verification_url(row)))


def invoice(db,row,actor=None):
    from . import medical_billing as fiscal
    for kind,value in (row.details or {}).get('files',{}).items():
        if kind not in {'PDF','Ticket','XML','ZIP','CDR'}:continue
        if row.legacy_id:
            file=db.get(LegacyFile,value)
            if not file:continue
            path=legacy_path(file);digest=file.sha256
        else:
            path=fiscal.artifact_path(row,kind);digest=value
        filename=(row.full_number or str(row.id))+'-'+kind+path.suffix
        # Legacy storage keys may have no extension; use the actual original name.
        if row.legacy_id:filename=(row.full_number or str(row.id))+'-'+kind+Path(file.filename).suffix.lower()
        archive(db,source='invoice',ident=row.id,key=kind,actor=actor or row.created_by,path=invoice_path(db,row),
            filename=filename,file_path=path,expected_hash=digest,description='Comprobante · '+row.customer)


def voucher(db,row,actor):
    from ..routes import medical as m
    liquidation=db.get(m.Liquidation,row.liquidation_id)
    archive(db,source='liquidation',ident=liquidation.id,key='voucher:'+str(row.id),actor=actor,
        path=record_path('liquidation',liquidation,liquidation.starts_on),filename=row.filename,
        file_path=m.STORAGE/row.storage_key,expected_hash=row.digest,description={'deposit':'Constancia de depósito','commission_payment':'Pago de comisión','commission_offset':'Acuerdo de compensación'}.get(row.purpose,'Constancia')+' · '+row.reference)


def monthly(db,row,emissions,actor):
    from .medical_exports import meta_xlsx
    from ..routes.medical_workspaces import monthly_letter
    # Liquidation items are fixed at creation. Avoid regenerating XLSX/PDF merely on refresh.
    for key,extension,generate in [('meta-xlsx','.xlsx',lambda:meta_xlsx(emissions,db,monthly=True)),('meta-letter','.pdf',lambda:monthly_letter(row,len(emissions)))]:
        if not binding(db,'liquidation',row.id,key):
            archive(db,source='liquidation',ident=row.id,key=key,actor=actor,path=record_path('liquidation',row,row.starts_on),
                filename=(row.code or str(row.id))+'-'+key+extension,content=generate(),description='Documentación mensual META')


def closing_receipt(db,row,actor):
    import pymupdf as fitz
    from .medical_reconciliation import balance,totals
    values=balance(row,totals(db,row.id))
    with fitz.open() as document:
        page=document.new_page()
        page.insert_text((45,60),'ABISSOL - Constancia de cierre',fontsize=18)
        text=f"Liquidacion: {row.code}\nPeriodo: {row.starts_on} a {row.ends_on}\nVentas: S/ {row.sales_total}\nDeposito requerido: S/ {row.deposit_required}\nDepositos conciliados: S/ {values['deposit_verified']}\nComision compensada: S/ {values['commission_offset']}\nSaldo por depositar: S/ {values['balance_due']}\nComision pagada: S/ {values['commission_paid']}\nComision pendiente al cierre: S/ {values['commission_due']}\n\nEsta constancia acredita la conciliacion de la liquidacion.\nEl cierre no acredita por si solo el pago de comisiones.\nLos pagos posteriores se consultan en el estado de cuenta."
        page.insert_textbox(fitz.Rect(45,100,550,700),text,fontsize=12,lineheight=1.6)
        archive(db,source='liquidation',ident=row.id,key='closing-receipt',actor=actor,path=record_path('liquidation',row,row.starts_on),filename=row.code+'-cierre.pdf',content=document.tobytes(),description='Constancia de cierre conciliado')


def plan(db,row,actor):
    from ..routes import medical as m
    from ..models.legacy import LegacyRecord
    record=db.query(LegacyRecord).filter_by(source_table='medical_plans',target_id=row.id).first()
    if not record:return
    file=legacy_file(db,m.legacy_data(db,'medical_plans',record.source_key).get('conditioned_document_path'))
    if file:
        archive(db,source='plan',ident=row.id,key='conditions',actor=actor,path=record_path('plan',row,None),
            filename=row.name+Path(file.filename).suffix.lower(),file_path=legacy_path(file),expected_hash=file.sha256,description='Condiciones del plan de asistencia')


def sync(db,actor):
    from ..routes import medical as m
    from ..models.documents import DocumentBinding
    organization=organize_affiliates(db,actor);db.commit()
    before=db.query(DocumentBinding).count()
    missing=[]
    tasks=[('emission',db.query(m.Issuance).order_by(m.Issuance.id),lambda row:emission(db,row,actor)),
           ('invoice',db.query(m.Invoice).order_by(m.Invoice.id),lambda row:invoice(db,row,actor)),
           ('voucher',db.query(m.Voucher).order_by(m.Voucher.id),lambda row:voucher(db,row,actor)),
           ('plan',db.query(m.Plan).order_by(m.Plan.id),lambda row:plan(db,row,actor))]
    for name,query,handle in tasks:
        model=query.column_descriptions[0]['entity']
        last=0
        while True:
            ids=[ident for ident, in query.with_entities(model.id).filter(model.id>last).limit(100).all()]
            if not ids:break
            for ident in ids:
                try:
                    handle(db.get(model,ident));db.commit()
                except FileNotFoundError:
                    db.rollback();missing.append({'type':name,'id':ident})
            last=ids[-1]
    for row in db.query(m.Liquidation).filter_by(kind='meta').order_by(m.Liquidation.id):
        entries=db.query(m.Issuance).join(m.Item,m.Item.issuance_id==m.Issuance.id).filter(m.Item.liquidation_id==row.id).order_by(m.Issuance.id).all()
        if entries:monthly(db,row,entries,actor);db.commit()
    return {'created':db.query(DocumentBinding).count()-before,'bindings':db.query(DocumentBinding).count(),'missing_originals':missing,'organization':organization}
