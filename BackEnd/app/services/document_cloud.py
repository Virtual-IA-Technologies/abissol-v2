import hashlib
import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import func, or_
from ..database import SessionLocal
from ..models import Usuario
from ..models.documents import Document, DocumentVersion
from ..models.document_cloud import CloudSetting, CloudAccount, CloudFolder, CloudSource
from ..utils.secrets import encrypt_secret, decrypt_secret
from ..utils.time import utc_now, utc_iso
from . import documents
from .access_control import access_by_slug, ACCESS_RANK
from .google_drive import GoogleDrive, exchange, FOLDER


def account_out(row):
    return {'id':row.id,'provider':row.provider,'label':row.label,'email':row.email,'active':row.active,'created_at':utc_iso(row.created_at)}


def folder_out(row):
    return {key:utc_iso(value) if key.endswith('_run') else value for key in ('id','account_id','remote_id','name','folder_id','enabled','last_run','next_run','status','message') for value in [getattr(row,key)]}


def source_out(row):
    return {key:utc_iso(value) if key=='updated_at' else value for key in ('id','account_id','remote_id','name','document_id','local_version','remote_version','status','message','updated_at') for value in [getattr(row,key)]}


def get_account(db,user,account_id,active=True):
    row=db.query(CloudAccount).filter_by(id=account_id,owner_id=user.id).first()
    if not row:raise HTTPException(404,'Cuenta no disponible')
    if active and not row.active:raise HTTPException(409,'Vuelve a conectar la cuenta')
    return row


@contextmanager
def account_lease(db, account):
    token=uuid4().hex
    changed=db.query(CloudAccount).filter(CloudAccount.id==account.id,or_(CloudAccount.lease_until.is_(None),CloudAccount.lease_until<utc_now())).update({'lease_token':token,'lease_until':utc_now()+timedelta(minutes=5)},synchronize_session=False)
    db.commit()
    if not changed:raise HTTPException(409,'Esta cuenta tiene una operación en curso; espera un momento')
    try:yield
    finally:
        db.rollback()
        db.query(CloudAccount).filter_by(id=account.id,lease_token=token).update({'lease_token':None,'lease_until':None},synchronize_session=False)
        db.commit()


def client(db,account):
    settings=db.get(CloudSetting,1)
    if not settings or not account.credentials:raise HTTPException(409,'Configura Google y vuelve a conectar la cuenta')
    tokens=json.loads(decrypt_secret(account.credentials))
    if tokens.get('expires',0)<time.time()+60:
        result=exchange({'client_id':settings.client_id,'client_secret':decrypt_secret(settings.secret),'refresh_token':tokens['refresh_token'],'grant_type':'refresh_token'})
        tokens.update(access_token=result['access_token'],expires=time.time()+int(result.get('expires_in',3600)))
        if result.get('refresh_token'):tokens['refresh_token']=result['refresh_token']
        account.credentials=encrypt_secret(json.dumps(tokens));db.commit()
    return GoogleDrive(tokens['access_token'])


def source_for(db,account,meta):
    row=db.query(CloudSource).filter_by(account_id=account.id,remote_id=meta['id']).first()
    if not row:
        row=CloudSource(account_id=account.id,remote_id=meta['id'],name=meta.get('name','Archivo')[:180])
        db.add(row);db.flush()
    return row


def import_file(db,account,user,drive,meta,folder_id,request=None,copy=False):
    from ..routes.audit import audit_change
    from ..routes.documentation import file_type
    from ..routes.document_tools import office_mime
    documents.get_folder(db,user,folder_id)
    source=source_for(db,account,meta)
    previous=source_out(source)
    version_tag=str(meta.get('version') or meta.get('modifiedTime',''))
    if not copy and source.document_id and source.remote_version==version_tag and source.status=='synced':return source
    doc=documents.get_document(db,user,source.document_id,edit=True,trash=True,lock=True) if source.document_id and not copy else None
    if doc and (doc.deleted_at or doc.current_version!=source.local_version):
        source.status='conflict';source.message='Editado en ABISSOL o enviado a papelera. Importa como copia para conservar ambos.';source.updated_at=utc_now()
        audit_change(db,request,user,'document_cloud_sources',source.id,before=previous,after=source_out(source),module='documentos');db.commit();return source
    name,data=drive.download(meta)
    # Una edición durante la descarga no puede quedar asociada a la versión anterior.
    fresh=drive.metadata(meta['id'])
    if str(fresh.get('version') or fresh.get('modifiedTime',''))!=version_tag:raise HTTPException(409,'El archivo cambió en Drive durante la descarga; reintenta')
    name=re.sub(r'[\x00-\x1f\x7f]','',name.replace('\\','/').split('/')[-1])
    suffix=Path(name).suffix.lower();name=Path(name).stem[:160]+suffix
    if not data:raise HTTPException(422,'El archivo remoto está vacío')
    mime=office_mime(data,name) or file_type(data,name)
    digest=hashlib.sha256(data).hexdigest()
    current=db.query(DocumentVersion).filter_by(document_id=doc.id,number=doc.current_version).first() if doc else None
    if current and current.sha256==digest:
        source.remote_version=version_tag;source.status='synced';source.message='';source.updated_at=utc_now();db.commit();return source
    used=db.query(func.coalesce(func.sum(DocumentVersion.size),0)).join(Document,Document.id==DocumentVersion.document_id).filter(Document.owner_id==user.id).scalar()
    if int(used)+len(data)>int(os.getenv('DOCUMENT_CLOUD_QUOTA_MB','1024'))*1024*1024:raise HTTPException(413,'La importación supera la cuota documental de tu cuenta')
    documents.STORAGE.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(documents.STORAGE).free<len(data)+512*1024*1024:raise HTTPException(507,'Espacio insuficiente en el servidor')
    before=documents.snapshot(doc) if doc else None
    if not doc:
        doc=Document(owner_id=user.id,folder_id=folder_id,title=name,description='',current_version=1);db.add(doc);db.flush()
    else:doc.current_version+=1;doc.updated_at=utc_now()
    key=uuid4().hex+suffix;path=documents.STORAGE/key
    try:
        with path.open('xb') as stream:stream.write(data)
        version=DocumentVersion(document_id=doc.id,number=doc.current_version,author_id=user.id,filename=name,storage_key=key,mime=mime,size=len(data),sha256=digest,reason='Importación Google Drive',processing='text_ready' if mime=='text/plain' and len(data)<=60000 else 'pending',text=data.decode('utf-8-sig') if mime=='text/plain' and len(data)<=60000 else None)
        db.add(version)
        source.document_id=doc.id;source.local_version=doc.current_version;source.remote_version=version_tag;source.name=name;source.status='synced';source.message='';source.updated_at=utc_now();db.flush()
        audit_change(db,request,user,'documents',doc.id,before=before,after={**documents.snapshot(doc),'file':documents.version_out(version)},module='documentos')
        audit_change(db,request,user,'document_cloud_sources',source.id,before=previous,after=source_out(source),module='documentos')
        db.commit()
    except Exception:
        db.rollback();path.unlink(missing_ok=True);raise
    return source


def sync_folder(binding_id):
    """Una página por ejecución, máximo 20 archivos y 120 segundos; cursor durable."""
    from ..routes.audit import audit_change
    with SessionLocal() as db:
        binding=db.get(CloudFolder,binding_id)
        if not binding or not binding.enabled:return
        account=db.get(CloudAccount,binding.account_id);user=db.get(Usuario,account.owner_id)
        if not account.active or not user or not user.is_active or user.deleted_at:return
        if ACCESS_RANK[access_by_slug(db,user).get('documentos','none')]<ACCESS_RANK['editor']:
            binding.next_run=utc_now()+timedelta(minutes=15);binding.status='error';binding.message='El propietario no tiene permiso editor en Documentos';db.commit();return
        try:
            with account_lease(db,account):
                db.refresh(binding)
                if not binding.enabled:return
                drive=client(db,account);before=folder_out(binding)
                if not binding.cursor:
                    binding.cursor=drive.start();db.commit()
                if binding.scanning:
                    result=drive.files(binding.remote_id,page=binding.scan_page or '')
                    changes=[{'file':f,'fileId':f['id']} for f in result.get('files',[])]
                else:
                    result=drive.changes(binding.cursor);changes=result.get('changes',[])
                completed=True;started=time.monotonic();count=0
                for change in changes:
                    if time.monotonic()-started>120:completed=False;break
                    meta=change.get('file',{});remote=change['fileId']
                    if change.get('removed') or meta.get('trashed'):
                        source=db.query(CloudSource).filter_by(account_id=account.id,remote_id=remote).first()
                        if source and source.status!='unavailable':
                            old=source_out(source);source.status='unavailable';source.message='Ya no disponible en Drive; se conserva la copia local.';source.updated_at=utc_now()
                            audit_change(db,None,user,'document_cloud_sources',source.id,before=old,after=source_out(source),module='documentos');db.commit()
                        continue
                    if meta.get('mimeType')==FOLDER or binding.remote_id not in meta.get('parents',[]):continue
                    try:
                        import_file(db,account,user,drive,meta,binding.folder_id);count+=1
                    except HTTPException as exc:
                        db.rollback()
                        if exc.status_code not in (403,404,413,422):raise
                        source=source_for(db,account,meta);old=source_out(source);source.status='skipped';source.message=str(exc.detail)[:500];source.updated_at=utc_now()
                        audit_change(db,None,user,'document_cloud_sources',source.id,before=old,after=source_out(source),module='documentos');db.commit()
                if completed:
                    if binding.scanning:
                        binding.scan_page=result.get('nextPageToken');binding.scanning=bool(binding.scan_page)
                    else:binding.cursor=result.get('nextPageToken') or result.get('newStartPageToken') or binding.cursor
                binding.status='ok';binding.message=f'{count} archivos revisados; consulta Actividad para omisiones o conflictos.'
                binding.last_run=utc_now();binding.next_run=utc_now()+timedelta(minutes=1 if binding.scanning or result.get('nextPageToken') or not completed else 15)
                audit_change(db,None,user,'document_cloud_folders',binding.id,before=before,after=folder_out(binding),module='documentos');db.commit()
        except HTTPException as exc:
            db.rollback();binding=db.get(CloudFolder,binding_id)
            if not binding:return
            if 'operación en curso' in str(exc.detail):return
            if exc.status_code==410:binding.cursor=None;binding.scan_page=None;binding.scanning=True
            binding.status='error';binding.message=str(exc.detail)[:500];binding.last_run=utc_now();binding.next_run=utc_now()+timedelta(minutes=15);db.commit()
        except Exception:
            db.rollback();binding=db.get(CloudFolder,binding_id)
            if not binding:return
            binding.status='error';binding.message='No se pudo completar la sincronización; revisa configuración y vuelve a intentar.';binding.next_run=utc_now()+timedelta(minutes=15);db.commit()
