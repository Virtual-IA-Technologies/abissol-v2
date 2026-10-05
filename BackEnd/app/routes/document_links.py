"""Publicación explícita autorizada: versión siete días, preview Office quince minutos."""
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from ..database import get_db
from ..models import Usuario
from ..models.documents import Document, DocumentLink, DocumentVersion
from ..services import documents as service
from ..services.access_control import ensure_option_access
from ..services.upload_stream import prepare_upload, document_mime
from ..utils.time import utc_now, utc_iso
from .documents import editor, commit
from .document_tools import version_for
from .audit import audit_change

router = APIRouter(prefix='/documentos')


class LinkExpiry(BaseModel):
    expires_at: datetime

    @field_validator('expires_at')
    @classmethod
    def future(cls, value):
        if value.tzinfo is None:
            raise ValueError('Indica la zona horaria del vencimiento')
        value = value.astimezone(UTC).replace(tzinfo=None)
        if value <= utc_now():
            raise ValueError('El vencimiento debe ser una fecha futura')
        return value


def out(row):
    return {'id':row.id,'expires_at':utc_iso(row.expires_at),'revoked_at':utc_iso(row.revoked_at) if row.revoked_at else None,'purpose':row.purpose}


def cleanup_previews(db):
    rows=db.query(DocumentLink).filter(DocumentLink.version_id.is_(None),DocumentLink.storage_key.is_not(None),DocumentLink.expires_at<=utc_now()).limit(200).all()
    for row in rows:
        try: service.file_path(row.storage_key).unlink(missing_ok=True)
        except HTTPException: pass
        row.storage_key=None
    db.commit()
    return len(rows)


@router.post('/{document_id}/versiones/{number}/enlaces',status_code=201)
def create_link(document_id:int,number:int,request:Request,payload:LinkExpiry | None=None,db:Session=Depends(get_db),user=Depends(editor)):
    _,version=version_for(db,user,document_id,number,edit=True)
    token=secrets.token_urlsafe(32)
    row=DocumentLink(version_id=version.id,author_id=user.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),purpose='share',expires_at=payload.expires_at if payload else utc_now()+timedelta(days=7))
    db.add(row);db.flush()
    audit_change(db,request,user,'document_links',row.id,after={**out(row),'version_id':version.id},module='documentos')
    commit(db)
    return {**out(row),'token':token}


@router.get('/{document_id}/enlaces')
def links(document_id:int,db:Session=Depends(get_db),user=Depends(editor)):
    service.get_document(db,user,document_id,edit=True,trash=True)
    return [{**out(row),'number':number} for row,number in db.query(DocumentLink,DocumentVersion.number).join(DocumentVersion,DocumentVersion.id==DocumentLink.version_id).filter(DocumentVersion.document_id==document_id,DocumentLink.purpose=='share').order_by(DocumentLink.id.desc()).limit(100).all()]


@router.delete('/{document_id}/enlaces/{link_id}',status_code=204)
def revoke(document_id:int,link_id:int,request:Request,db:Session=Depends(get_db),user=Depends(editor)):
    service.get_document(db,user,document_id,edit=True,trash=True,lock=True)
    row=db.query(DocumentLink).join(DocumentVersion,DocumentVersion.id==DocumentLink.version_id).filter(DocumentLink.id==link_id,DocumentVersion.document_id==document_id).first()
    if not row: raise HTTPException(404,'Enlace no disponible')
    before=out(row);row.revoked_at=utc_now()
    audit_change(db,request,user,'document_links',row.id,before=before,after=out(row),module='documentos')
    commit(db)


@router.patch('/{document_id}/enlaces/{link_id}')
def change_expiry(document_id:int,link_id:int,payload:LinkExpiry,request:Request,db:Session=Depends(get_db),user=Depends(editor)):
    service.get_document(db,user,document_id,edit=True,lock=True)
    row=db.query(DocumentLink).join(DocumentVersion,DocumentVersion.id==DocumentLink.version_id).filter(DocumentLink.id==link_id,DocumentVersion.document_id==document_id,DocumentLink.purpose=='share').first()
    if not row: raise HTTPException(404,'Enlace no disponible')
    if row.revoked_at: raise HTTPException(409,'Un enlace retirado no puede reactivarse; crea otro')
    before=out(row)
    row.expires_at=payload.expires_at
    audit_change(db,request,user,'document_links',row.id,before=before,after=out(row),module='documentos')
    commit(db)
    return out(row)


@router.post('/previas/office',status_code=201)
async def temporary_preview(request:Request,file:UploadFile=File(),db:Session=Depends(get_db),user=Depends(editor)):
    cleanup_previews(db)
    active=db.query(DocumentLink).filter(DocumentLink.author_id==user.id,DocumentLink.version_id.is_(None),DocumentLink.expires_at>utc_now()).count()
    if active>=10: raise HTTPException(429,'Tienes diez vistas temporales activas. Espera a que venzan.')
    name=Path((file.filename or '').replace('\\','/')).name[:180]
    if Path(name).suffix.lower() not in ('.docx','.xlsx','.pptx'): raise HTTPException(422,'Vista Office para DOCX, XLSX o PPTX')
    data=await prepare_upload(file)
    mime=document_mime(data,name)
    token=secrets.token_urlsafe(32)
    key=uuid4().hex+Path(name).suffix.lower()
    service.STORAGE.mkdir(parents=True,exist_ok=True)
    path=service.STORAGE/key
    row=DocumentLink(author_id=user.id,token_hash=hashlib.sha256(token.encode()).hexdigest(),purpose='office-preview',expires_at=utc_now()+timedelta(minutes=15),storage_key=key,filename=name,mime=mime)
    try:
        data.write(path)
        db.add(row);db.flush()
        audit_change(db,request,user,'document_links',row.id,after={**out(row),'filename':name,'purpose':'office-preview'},module='documentos')
        commit(db)
    except Exception:
        db.rollback();path.unlink(missing_ok=True);raise
    return {**out(row),'token':token}


@router.get('/publico/archivo')
def public_file(token:str=Query(min_length=40,max_length=100),db:Session=Depends(get_db)):
    row=db.query(DocumentLink).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest()).first()
    if not row or row.revoked_at or row.expires_at<=utc_now(): raise HTTPException(404,'El enlace venció o fue retirado')
    owner=db.get(Usuario,row.author_id)
    if not owner or owner.deleted_at or not owner.is_active: raise HTTPException(404,'Archivo no disponible')
    try:ensure_option_access(db,owner,'documentos','editor')
    except HTTPException:raise HTTPException(404,'Archivo no disponible') from None
    if row.version_id:
        version=db.get(DocumentVersion,row.version_id)
        if not version:raise HTTPException(404,'Archivo no disponible')
        document=db.get(Document,version.document_id)
        if not document or document.deleted_at or document.owner_id!=row.author_id: raise HTTPException(404,'Archivo no disponible')
        key,name,mime=version.storage_key,version.filename,version.mime
    else:
        key,name,mime=row.storage_key,row.filename,row.mime
    if not key: raise HTTPException(404,'Archivo no disponible')
    return FileResponse(service.file_path(key),filename=name,media_type=mime,content_disposition_type='attachment',
        headers={'Cache-Control':'private, no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','Content-Security-Policy':"sandbox; default-src 'none'"})
