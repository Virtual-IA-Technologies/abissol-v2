"""Puente ONLYOFFICE: configuración y callbacks firmados, archivos privados."""
import hashlib
import io
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse, urlencode
from urllib.request import build_opener, HTTPRedirectHandler
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from ..database import get_db
from ..models import Usuario
from ..models.documents import DocumentVersion, DocumentEditSession
from ..services import documents as service
from ..services.access_control import access_by_slug, ACCESS_RANK
from ..utils.time import utc_now
from .documents import editor, commit, save_file
from .audit import audit_change

router = APIRouter(prefix='/documentos/office')
KINDS = {'docx':'word', 'xlsx':'cell', 'pptx':'slide'}


def settings():
    server = os.getenv('ONLYOFFICE_DOCUMENT_SERVER_URL', '').rstrip('/')
    callback = os.getenv('ONLYOFFICE_CALLBACK_BASE_URL', '').rstrip('/')
    secret = os.getenv('ONLYOFFICE_JWT_SECRET', '')
    if not server or not callback or len(secret) < 32:
        raise HTTPException(503, 'ONLYOFFICE aún no está configurado. Conserva el archivo y vuelve a intentarlo después.')
    return server, callback, secret


def signed_session(token, db, allow_closed=False):
    _, _, secret = settings()
    try:
        claims = jwt.decode(token, secret, algorithms=['HS256'])
        if claims.get('purpose') != 'abissol-office':
            raise ValueError()
        session = db.get(DocumentEditSession, claims['session'])
        if not session or session.expires_at <= utc_now() or (session.closed_at and not allow_closed):
            raise ValueError()
    except (JWTError, ValueError, KeyError):
        raise HTTPException(403, 'Sesión de edición no válida')
    user = db.get(Usuario, session.author_id)
    if not user or user.deleted_at or not user.is_active or ACCESS_RANK[access_by_slug(db, user).get('documentos', 'none')] < ACCESS_RANK['editor']:
        raise HTTPException(403, 'La autorización de edición terminó')
    document = service.get_document(db, user, session.document_id, edit=True, lock=True)
    db.refresh(session)
    if session.closed_at and not allow_closed:
        raise HTTPException(403, 'La sesión de edición terminó')
    return session, user, document


@router.post('/{document_id}/config')
def config(document_id: int, request: Request, db: Session = Depends(get_db), user=Depends(editor)):
    server, callback, secret = settings()
    document = service.get_document(db, user, document_id, edit=True, lock=True)
    version = db.query(DocumentVersion).filter_by(document_id=document_id, number=document.current_version).one()
    extension = Path(version.filename).suffix.lower().lstrip('.')
    if extension not in KINDS:
        raise HTTPException(422, 'Edición Office disponible para DOCX, XLSX y PPTX')
    session = db.query(DocumentEditSession).filter(DocumentEditSession.document_id == document_id, DocumentEditSession.closed_at.is_(None), DocumentEditSession.expires_at > utc_now()).first()
    if session and session.expected_version != document.current_version:
        raise HTTPException(409, 'Cierra el editor anterior antes de abrir la versión actual')
    if not session:
        session = DocumentEditSession(id=uuid4().hex, document_id=document_id, version_id=version.id,
            author_id=user.id, expected_version=document.current_version, expires_at=utc_now()+timedelta(hours=4))
        db.add(session)
        audit_change(db, request, user, 'document_edit_sessions', session.id, after={'document_id':document_id,'version_id':version.id,'author_id':user.id}, module='documentos')
        commit(db)
    token = jwt.encode({'purpose':'abissol-office','session':session.id,'exp':session.expires_at}, secret, algorithm='HS256')
    query = urlencode({'access_token':token})
    cfg = {'documentType': KINDS[extension], 'document':{'fileType':extension, 'key':session.id,
        'title':version.filename,'url':f'{callback}/documentos/office/content?{query}',
        'permissions':{'edit':True,'download':True,'print':True}},
        'editorConfig':{'mode':'edit','lang':'es', 'callbackUrl':f'{callback}/documentos/office/callback?{query}',
        'user':{'id':str(user.id),'name':f'{user.nombre} {user.apellido}'},'customization':{'autosave':True,'forcesave':True}}}
    cfg['token'] = jwt.encode(cfg, secret, algorithm='HS256')
    return {'server':server,'config':cfg}


@router.get('/content')
def content(access_token: str, db: Session = Depends(get_db)):
    session, _, _ = signed_session(access_token, db)
    version = db.get(DocumentVersion, session.version_id)
    return FileResponse(service.file_path(version.storage_key), media_type=version.mime, filename=version.filename,
        headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPException(422, 'Redirección de guardado no permitida')


def download_result(url, server):
    target = urlparse(url)
    allowed = [urlparse(server), urlparse(os.getenv('ONLYOFFICE_INTERNAL_URL', server))]
    if target.scheme not in ('http','https') or target.username or target.password or not any((target.scheme,target.hostname,target.port)==(a.scheme,a.hostname,a.port) for a in allowed):
        raise HTTPException(422, 'Origen de guardado no autorizado')
    with build_opener(NoRedirect()).open(url, timeout=30) as response:
        data = response.read(20*1024*1024+1)
    if not data or len(data)>20*1024*1024:
        raise HTTPException(413, 'Resultado fuera del límite de 20 MB')
    return data


@router.post('/callback')
async def callback(request: Request, access_token: str, db: Session = Depends(get_db)):
    server, _, secret = settings()
    body = await request.json()
    signature = request.headers.get('authorization', '').removeprefix('Bearer ') or body.get('token', '')
    try:
        signed = jwt.decode(signature, secret, algorithms=['HS256'])
        payload = signed.get('payload', signed)
        if not isinstance(payload, dict):
            raise ValueError()
    except (JWTError, ValueError):
        raise HTTPException(403, 'Callback sin firma válida')
    session, user, document = signed_session(access_token, db, allow_closed=True)
    if payload.get('key') != session.id:
        raise HTTPException(403, 'Clave de edición no válida')
    status = payload.get('status')
    if session.closed_at:
        return {'error':0}
    if status == 4:
        session.closed_at=utc_now(); commit(db); return {'error':0}
    if status not in (2,6):
        return {'error':0 if status==1 else 1}
    if document.current_version != session.expected_version:
        raise HTTPException(409, 'El documento cambió fuera del editor; no se sobrescribió')
    data = await run_in_threadpool(download_result, payload.get('url',''), server)
    digest = hashlib.sha256(data).hexdigest()
    if digest != session.saved_hash:
        before=service.snapshot(document)
        original=db.get(DocumentVersion, session.version_id)
        document.current_version+=1; document.updated_at=utc_now()
        path=None
        try:
            version,path=await save_file(db,user,UploadFile(filename=original.filename,file=io.BytesIO(data)),document,'Edición ONLYOFFICE')
            session.expected_version=document.current_version; session.saved_hash=digest
            if status==2: session.closed_at=utc_now()
            db.flush()
            audit_change(db,request,user,'documents',document.id,before=before,after={**service.snapshot(document),'file':service.version_out(version)},module='documentos')
            commit(db)
        except Exception:
            db.rollback()
            if path: path.unlink(missing_ok=True)
            raise
    elif status==2:
        session.closed_at=utc_now();commit(db)
    return {'error':0}
