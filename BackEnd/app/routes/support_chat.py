"""ABISSOL identifica al usuario; únicamente el servidor conserva la clave del conector."""
import os
from urllib.parse import urlsplit
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Form, File, UploadFile, Response
from pydantic import BaseModel, Field
from uuid import UUID
from ..services.support_chat import chat_user as get_current_user
from ..services.support_chat import chat_identity, touch_presence
from ..database import get_db

def private_response(response:Response):
    response.headers['Cache-Control']='private, no-store'

router=APIRouter(prefix='/support-chat',tags=['Soporte de Sistemas'],dependencies=[Depends(private_response)])


@router.post('/presence')
def presence(identity=Depends(chat_identity), db=Depends(get_db)):
    settings()
    touch_presence(db, identity.device_session_id)
    return {'ok': True}

def settings():
    url=os.getenv('SUPPORT_CHAT_URL','').rstrip('/')
    token=os.getenv('SUPPORT_CHAT_TOKEN','')
    parsed=urlsplit(url)
    if not url or not token:raise HTTPException(503,'El canal de soporte todavía no está conectado')
    if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in {'localhost','127.0.0.1'}):raise HTTPException(503,'La conexión de soporte requiere HTTPS')
    return url,token

async def relay(method,path,user,*,params=None,data=None,files=None,json=None,binary=False,timeout=30):
    url,token=settings()
    query=dict(params or {})
    if user is not None:query['external_id']=str(user.id)
    try:
        async with httpx.AsyncClient(timeout=timeout,follow_redirects=False) as client:
            result=await client.request(method,url+path,headers={'Authorization':'Bearer '+token},params=query,data=data,files=files,json=json)
    except httpx.HTTPError as exc:
        raise HTTPException(503,'No se pudo conectar con soporte. Conserva el mensaje y vuelve a intentar.') from exc
    if result.status_code>=400:
        detail='El servicio de soporte no está disponible'
        if result.status_code in (404,409,413,422):
            try:detail=result.json().get('detail',detail)
            except ValueError:pass
        raise HTTPException(result.status_code if result.status_code in (404,409,413,422) else 503,detail)
    if binary:return Response(result.content,media_type=result.headers.get('content-type','application/octet-stream'),headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})
    try:return result.json()
    except ValueError:raise HTTPException(502,'Respuesta de soporte no válida') from None

@router.get('/messages')
async def messages(before:int|None=Query(None,gt=0),user=Depends(get_current_user)):
    return await relay('GET','/bridge/messages',user,params={'before':before} if before else {})

@router.post('/messages')
async def send(body:str=Form('',max_length=4000),request_key:UUID=Form(...),file:UploadFile|None=File(None),user=Depends(get_current_user)):
    files=None
    if file:
        content=await file.read(5*1024*1024+1)
        if len(content)>5*1024*1024:raise HTTPException(413,'La captura supera 5 MB')
        files={'file':(file.filename or 'captura.png',content,file.content_type)}
    if not body.strip() and not file:raise HTTPException(422,'Escribe un mensaje o adjunta una captura')
    return await relay('POST','/bridge/messages',user,data={'external_id':str(user.id),'name':f'{user.nombre} {user.apellido or ""}'.strip(),'body':body,'request_key':str(request_key)},files=files)

class ReadRequest(BaseModel):message_id:int=Field(gt=0)
@router.post('/read')
async def read(data:ReadRequest,user=Depends(get_current_user)):
    return await relay('POST','/bridge/read',user,json=data.model_dump())

@router.get('/messages/{message_id}/attachments/{index}')
async def attachment(message_id:int,index:int,user=Depends(get_current_user)):
    return await relay('GET',f'/bridge/messages/{message_id}/attachments/{index}',user,binary=True)

@router.get('/contacts')
async def contacts(user=Depends(get_current_user)):
    # The publisher runs independently; neither portraits nor its POST block this GET.
    return await relay('GET','/bridge/people',user,timeout=5)

@router.get('/direct/{operator_id}/messages')
async def direct_messages(operator_id:int,before:int|None=Query(None,gt=0),user=Depends(get_current_user)):
    return await relay('GET',f'/bridge/direct/{operator_id}/messages',user,params={'before':before} if before else {})

@router.post('/direct/{operator_id}/messages')
async def direct_send(operator_id:int,body:str=Form('',max_length=4000),request_key:UUID=Form(...),file:UploadFile|None=File(None),user=Depends(get_current_user)):
    files=None
    if file:
        content=await file.read(5*1024*1024+1)
        if len(content)>5*1024*1024:raise HTTPException(413,'La captura supera 5 MB')
        files={'file':(file.filename or 'captura.png',content,file.content_type)}
    if not body.strip() and not file:raise HTTPException(422,'Escribe un mensaje o adjunta una captura')
    return await relay('POST',f'/bridge/direct/{operator_id}/messages',user,data={'name':f'{user.nombre} {user.apellido or ""}'.strip(),'body':body,'request_key':str(request_key)},files=files)

@router.post('/direct/{operator_id}/read')
async def direct_read(operator_id:int,data:ReadRequest,user=Depends(get_current_user)):
    return await relay('POST',f'/bridge/direct/{operator_id}/read',user,json=data.model_dump())

@router.get('/direct/{operator_id}/messages/{message_id}/attachments/{index}')
async def direct_attachment(operator_id:int,message_id:int,index:int,user=Depends(get_current_user)):
    return await relay('GET',f'/bridge/direct/{operator_id}/messages/{message_id}/attachments/{index}',user,binary=True)
