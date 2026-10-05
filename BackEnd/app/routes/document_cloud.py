import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import timedelta
from typing import Literal
from urllib.parse import urlencode, urlparse
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.orm import Session
from ..config import get_settings
from ..database import get_db
from ..models import Usuario
from ..models.documents import DocumentVersion
from ..models.document_cloud import CloudSetting, CloudAuth, CloudAccount, CloudFolder, CloudSource
from ..services import documents, document_cloud as service
from ..services.access_control import require_access, access_by_slug, ACCESS_RANK
from ..services.google_drive import SCOPES, FOLDER, GoogleDrive, exchange, remote_id
from ..utils.secrets import encrypt_secret, decrypt_secret
from ..utils.time import utc_now
from .audit import audit_change
from .documents import editor, reader, manager

router=APIRouter(prefix='/documentos/nube')
platform_editor=require_access('apariencia','editor')
COOKIE='abissol_drive_state'
CALLBACK='/abissol/api/v1/documentos/nube/oauth/callback'


class SettingsWrite(BaseModel):
    client_id: str=Field(min_length=10,max_length=250)
    client_secret: str=Field(default='',max_length=500)
    redirect_uri: str=Field(max_length=500)
    frontend_origin: str=Field(max_length=250)

    @model_validator(mode='after')
    def valid(self):
        if not self.client_id.endswith('.apps.googleusercontent.com'):raise ValueError('Usa el ID de cliente web de Google')
        if self.frontend_origin not in get_settings().cors_origins:raise ValueError('El origen web debe estar autorizado en CORS_ORIGINS')
        callback=urlparse(self.redirect_uri);front=urlparse(self.frontend_origin)
        if callback.username or callback.password or callback.query or callback.fragment or not callback.path.endswith(CALLBACK):raise ValueError('URL de retorno inválida')
        if callback.hostname!=front.hostname or callback.scheme!=front.scheme:raise ValueError('El retorno debe pertenecer al mismo servidor que la plataforma')
        if callback.scheme!='https' and callback.hostname not in ('localhost','127.0.0.1'):raise ValueError('El retorno requiere HTTPS')
        return self


def settings_out(row):
    return {'configured':bool(row),'client_id':row.client_id if row else '', 'has_secret':bool(row and row.secret),'redirect_uri':row.redirect_uri if row else '', 'frontend_origin':row.frontend_origin if row else ''}


@router.get('/estado')
def state(db:Session=Depends(get_db),user=Depends(reader)):
    return {'configured':db.get(CloudSetting,1) is not None,'providers':['google'],'automatic':os.getenv('DOCUMENT_CLOUD_SCHEDULER','true').lower()=='true'}


@router.get('/configuracion')
def configuration(db:Session=Depends(get_db),user=Depends(platform_editor)):
    return settings_out(db.get(CloudSetting,1))


@router.put('/configuracion')
def configure(payload:SettingsWrite,request:Request,db:Session=Depends(get_db),user=Depends(platform_editor)):
    if getattr(request.state,'auth_identity',None) and request.state.auth_identity.impersonation_id:raise HTTPException(403,'Configura la integración desde tu propia sesión')
    row=db.get(CloudSetting,1);before=settings_out(row) if row else None
    if row and row.client_id!=payload.client_id and db.query(CloudAccount).filter_by(active=True).first():raise HTTPException(409,'Desconecta las cuentas antes de cambiar el cliente OAuth')
    if row and row.client_id!=payload.client_id and not payload.client_secret:raise HTTPException(422,'Un cliente OAuth diferente requiere su propio secreto')
    if not row and not payload.client_secret:raise HTTPException(422,'Ingresa el secreto del cliente OAuth')
    if not row:row=CloudSetting(id=1);db.add(row)
    row.client_id=payload.client_id;row.redirect_uri=payload.redirect_uri;row.frontend_origin=payload.frontend_origin
    if payload.client_secret:row.secret=encrypt_secret(payload.client_secret)
    audit_change(db,request,user,'document_cloud_settings',1,before=before,after=settings_out(row),module='documentos');db.commit()
    return settings_out(row)


@router.post('/oauth/iniciar')
def start(request:Request,response:Response,db:Session=Depends(get_db),user=Depends(editor)):
    if getattr(request.state,'auth_identity',None) and request.state.auth_identity.impersonation_id:raise HTTPException(403,'Conecta Drive desde tu propia sesión')
    settings=db.get(CloudSetting,1)
    if not settings:raise HTTPException(409,'Primero configura el cliente OAuth de Google')
    if db.query(CloudAccount).filter_by(owner_id=user.id,active=True).count()>=10:raise HTTPException(422,'Máximo diez cuentas activas por usuario')
    db.query(CloudAuth).filter(CloudAuth.expires_at<=utc_now()).delete(synchronize_session=False)
    db.query(CloudAuth).filter_by(owner_id=user.id).delete(synchronize_session=False)
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    db.add(CloudAuth(state_hash=hashlib.sha256(state.encode()).hexdigest(),owner_id=user.id,verifier=encrypt_secret(verifier),expires_at=utc_now()+timedelta(minutes=10)));db.commit()
    response.set_cookie(COOKIE,state,max_age=600,httponly=True,secure=settings.redirect_uri.startswith('https:'),samesite='lax',path='/')
    return {'url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({'client_id':settings.client_id,'redirect_uri':settings.redirect_uri,'response_type':'code','scope':SCOPES,'state':state,'access_type':'offline','prompt':'consent select_account','code_challenge':base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('='),'code_challenge_method':'S256'})}


@router.get('/oauth/callback')
def callback(request:Request,state:str=Query(default='',max_length=200),code:str=Query(default='',max_length=4096),error:str=Query(default='',max_length=200),db:Session=Depends(get_db)):
    settings=db.get(CloudSetting,1)
    cookie=request.cookies.get(COOKIE,'')
    if not settings or not state or not cookie or not hmac.compare_digest(cookie,state):raise HTTPException(400,'La autorización no corresponde a este navegador')
    row=db.query(CloudAuth).filter_by(state_hash=hashlib.sha256(state.encode()).hexdigest()).with_for_update().first()
    if not row or row.expires_at<=utc_now():raise HTTPException(400,'La autorización venció o ya fue utilizada')
    user=db.get(Usuario,row.owner_id);verifier=decrypt_secret(row.verifier);db.delete(row);db.commit()
    if not user or not user.is_active or user.deleted_at or ACCESS_RANK[access_by_slug(db,user).get('documentos','none')]<ACCESS_RANK['editor']:raise HTTPException(403,'La cuenta ya no tiene acceso a Documentos')
    result_status='cancelado' if error else 'error'
    if code and not error:
        try:
            tokens=exchange({'client_id':settings.client_id,'client_secret':decrypt_secret(settings.secret),'code':code,'code_verifier':verifier,'redirect_uri':settings.redirect_uri,'grant_type':'authorization_code'})
            if not set(SCOPES.split()).issubset(set(tokens.get('scope','').split())):raise HTTPException(403,'Faltan permisos de Google')
            identity=GoogleDrive(tokens['access_token']).identity()
            account=db.query(CloudAccount).filter_by(owner_id=user.id,provider='google',remote_id=identity['permissionId']).with_for_update().first()
            before=service.account_out(account) if account else None
            if account and account.lease_until and account.lease_until>utc_now():raise HTTPException(409,'Cuenta ocupada')
            if not tokens.get('refresh_token'):raise HTTPException(409,'Google no otorgó acceso sin conexión; vuelve a autorizar')
            if not account:
                account=CloudAccount(owner_id=user.id,provider='google',remote_id=identity['permissionId']);db.add(account)
            account.label=identity.get('displayName',identity['emailAddress'])[:180];account.email=identity['emailAddress'];account.active=True
            account.credentials=encrypt_secret(json.dumps({'access_token':tokens['access_token'],'refresh_token':tokens['refresh_token'],'expires':time.time()+int(tokens.get('expires_in',3600))}))
            db.flush();audit_change(db,request,user,'document_cloud_accounts',account.id,before=before,after=service.account_out(account),module='documentos');db.commit();result_status='conectado'
        except (HTTPException,KeyError,ValueError):db.rollback()
    response=RedirectResponse(settings.frontend_origin+'/documentos/archivos?nube='+result_status,status_code=303)
    response.delete_cookie(COOKIE,path='/');response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='no-referrer'
    return response


@router.get('/cuentas')
def accounts(db:Session=Depends(get_db),user=Depends(reader)):
    return [service.account_out(row) for row in db.query(CloudAccount).filter_by(owner_id=user.id).order_by(CloudAccount.label).all()]


class AccountWrite(BaseModel):
    label:str=Field(min_length=1,max_length=180)


@router.patch('/cuentas/{account_id}')
def rename(account_id:int,payload:AccountWrite,request:Request,db:Session=Depends(get_db),user=Depends(editor)):
    account=service.get_account(db,user,account_id,False);before=service.account_out(account)
    if not payload.label.strip():raise HTTPException(422,'Escribe un nombre')
    account.label=payload.label.strip();audit_change(db,request,user,'document_cloud_accounts',account.id,before=before,after=service.account_out(account),module='documentos');db.commit();return service.account_out(account)


@router.delete('/cuentas/{account_id}',status_code=204)
def disconnect(account_id:int,request:Request,db:Session=Depends(get_db),user=Depends(editor)):
    # Retirar la propia autorización externa siempre está permitido al editor.
    account=service.get_account(db,user,account_id,False)
    with service.account_lease(db,account):
        before=service.account_out(account);account.active=False;account.credentials=None
        for binding in db.query(CloudFolder).filter_by(account_id=account.id).all():
            old=service.folder_out(binding);binding.enabled=False
            audit_change(db,request,user,'document_cloud_folders',binding.id,before=old,after=service.folder_out(binding),module='documentos')
        audit_change(db,request,user,'document_cloud_accounts',account.id,before=before,after=service.account_out(account),module='documentos');db.commit()


@router.get('/cuentas/{account_id}/archivos')
def files(account_id:int,folder:str=Query(default='root',max_length=160),q:str=Query(default='',max_length=100),page:str=Query(default='',max_length=4096),size:Literal[10,25,50]=10,order:Literal['name','name desc','modifiedTime','modifiedTime desc']='name',db:Session=Depends(get_db),user=Depends(reader)):
    account=service.get_account(db,user,account_id)
    with service.account_lease(db,account):return service.client(db,account).files(folder,q,page,size,order)


class ImportWrite(BaseModel):
    remote_id:str
    folder_id:int|None=None
    as_copy:bool=False
    _remote=field_validator('remote_id')(remote_id)


@router.post('/cuentas/{account_id}/importar')
def import_file(account_id:int,payload:ImportWrite,request:Request,db:Session=Depends(get_db),user=Depends(editor)):
    account=service.get_account(db,user,account_id)
    with service.account_lease(db,account):
        drive=service.client(db,account);meta=drive.metadata(payload.remote_id)
        return service.source_out(service.import_file(db,account,user,drive,meta,payload.folder_id,request,payload.as_copy))


class ExportWrite(BaseModel):
    document_id:int
    number:int=Field(ge=1)
    remote_folder:str
    _remote=field_validator('remote_folder')(remote_id)


@router.post('/cuentas/{account_id}/exportar')
def export_file(account_id:int,payload:ExportWrite,request:Request,db:Session=Depends(get_db),user=Depends(editor)):
    account=service.get_account(db,user,account_id)
    documents.get_document(db,user,payload.document_id,edit=True)
    version=db.query(DocumentVersion).filter_by(document_id=payload.document_id,number=payload.number).first()
    if not version:raise HTTPException(404,'Versión no disponible')
    with service.account_lease(db,account):
        drive=service.client(db,account)
        if drive.metadata(payload.remote_folder)['mimeType']!=FOLDER:raise HTTPException(422,'Selecciona una carpeta de destino')
        key=hashlib.sha256((str(user.id)+':'+str(version.id)+':'+version.sha256).encode()).hexdigest()
        result=drive.export_copy(payload.remote_folder,version.filename,version.mime,documents.file_path(version.storage_key).read_bytes(),key)
        audit_change(db,request,user,'document_cloud_exports',version.id,after={'account_id':account.id,'document_id':payload.document_id,'version':payload.number,'remote_id':result['id'],'remote_folder':payload.remote_folder},module='documentos');db.commit();return result


@router.get('/cuentas/{account_id}/carpetas')
def folders(account_id:int,db:Session=Depends(get_db),user=Depends(reader)):
    service.get_account(db,user,account_id,False)
    return [service.folder_out(row) for row in db.query(CloudFolder).filter_by(account_id=account_id).order_by(CloudFolder.name).all()]


class FolderWrite(BaseModel):
    remote_id:str
    folder_id:int
    _remote=field_validator('remote_id')(remote_id)


@router.post('/cuentas/{account_id}/carpetas',status_code=201)
def link_folder(account_id:int,payload:FolderWrite,request:Request,background:BackgroundTasks,db:Session=Depends(get_db),user=Depends(editor)):
    account=service.get_account(db,user,account_id);documents.get_folder(db,user,payload.folder_id)
    with service.account_lease(db,account):
        if db.query(CloudFolder).filter_by(account_id=account.id,remote_id=payload.remote_id).first():raise HTTPException(409,'Esta carpeta ya está vinculada')
        if db.query(CloudFolder).filter_by(account_id=account.id).count()>=20:raise HTTPException(422,'Máximo veinte carpetas por cuenta')
        drive=service.client(db,account);meta=drive.metadata(payload.remote_id)
        if meta['mimeType']!=FOLDER:raise HTTPException(422,'Selecciona una carpeta de Drive')
        row=CloudFolder(account_id=account.id,remote_id=meta['id'],name=meta['name'][:180],folder_id=payload.folder_id,cursor=drive.start());db.add(row);db.flush()
        audit_change(db,request,user,'document_cloud_folders',row.id,after=service.folder_out(row),module='documentos');db.commit()
        result=service.folder_out(row)
    background.add_task(service.sync_folder,row.id)
    return result


class FolderUpdate(BaseModel):
    enabled:bool


@router.patch('/cuentas/{account_id}/carpetas/{binding_id}')
def pause(account_id:int,binding_id:int,payload:FolderUpdate,request:Request,db:Session=Depends(get_db),user=Depends(editor)):
    account=service.get_account(db,user,account_id)
    with service.account_lease(db,account):
        row=db.query(CloudFolder).filter_by(id=binding_id,account_id=account.id).first()
        if not row:raise HTTPException(404,'Carpeta no disponible')
        before=service.folder_out(row);row.enabled=payload.enabled;row.next_run=utc_now()
        audit_change(db,request,user,'document_cloud_folders',row.id,before=before,after=service.folder_out(row),module='documentos');db.commit();return service.folder_out(row)


@router.post('/cuentas/{account_id}/carpetas/{binding_id}/sincronizar',status_code=202)
def synchronize(account_id:int,binding_id:int,background:BackgroundTasks,db:Session=Depends(get_db),user=Depends(editor)):
    service.get_account(db,user,account_id)
    row=db.query(CloudFolder).filter_by(id=binding_id,account_id=account_id).first()
    if not row or not row.enabled:raise HTTPException(409,'Activa la carpeta antes de sincronizar')
    background.add_task(service.sync_folder,row.id)
    return {'queued':True}


@router.delete('/cuentas/{account_id}/carpetas/{binding_id}',status_code=204)
def unlink(account_id:int,binding_id:int,request:Request,db:Session=Depends(get_db),user=Depends(manager)):
    account=service.get_account(db,user,account_id,False)
    with service.account_lease(db,account):
        row=db.query(CloudFolder).filter_by(id=binding_id,account_id=account.id).first()
        if not row:raise HTTPException(404,'Vínculo no disponible')
        audit_change(db,request,user,'document_cloud_folders',row.id,before=service.folder_out(row),module='documentos');db.delete(row);db.commit()


@router.get('/cuentas/{account_id}/actividad')
def activity(account_id:int,q:str=Query(default='',max_length=100),status:Literal['','synced','conflict','skipped','unavailable']='',page:int=Query(default=1,ge=1),size:Literal[0,10,25,50]=10,db:Session=Depends(get_db),user=Depends(reader)):
    service.get_account(db,user,account_id,False)
    query=db.query(CloudSource).filter_by(account_id=account_id)
    if q:query=query.filter(CloudSource.name.contains(q,autoescape=True))
    if status:query=query.filter_by(status=status)
    total=query.count()
    if not size and total>5000:raise HTTPException(422,'Limita los filtros a 5000 registros')
    query=query.order_by(CloudSource.updated_at.desc(),CloudSource.id.desc())
    if size:query=query.offset((page-1)*size).limit(size)
    return {'items':[service.source_out(row) for row in query.all()],'total':total}
