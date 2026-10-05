"""Transporte Google con destinos fijos, sin redirecciones ni secretos en errores."""
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from uuid import uuid4
from fastapi import HTTPException

API = 'https://www.googleapis.com/drive/v3/'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
SCOPES = 'https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file'
FOLDER = 'application/vnd.google-apps.folder'
FIELDS = 'id,name,mimeType,size,version,modifiedTime,parents,trashed,capabilities(canDownload)'
MAX_BYTES = 20 * 1024 * 1024
EXPORTS = {
    'application/vnd.google-apps.document': ('docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    'application/vnd.google-apps.spreadsheet': ('xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
    'application/vnd.google-apps.presentation': ('pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation'),
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def remote_id(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',value):
        raise HTTPException(422,'Identificador de Drive inválido')
    return value


def transport(url, *, token=None, data=None, content_type=None, binary=False):
    headers={'Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    if content_type:headers['Content-Type']=content_type
    limit=MAX_BYTES if binary else 2*1024*1024
    try:
        started=time.monotonic()
        with build_opener(NoRedirect).open(Request(url,data=data,headers=headers),timeout=15) as response:
            chunks=[];length=0
            while length<=limit:
                if time.monotonic()-started>30:raise HTTPException(504,'La transferencia de Google tardó demasiado; reintenta')
                chunk=response.read(min(65536,limit+1-length))
                if not chunk:break
                chunks.append(chunk);length+=len(chunk)
            raw=b''.join(chunks)
        if len(raw)>limit:raise HTTPException(413,'El archivo o respuesta supera el límite permitido (20 MB por archivo)')
        return raw if binary else json.loads(raw)
    except HTTPError as exc:
        if exc.code in (401,400) and url==TOKEN_URL:
            raise HTTPException(409,'Google requiere volver a conectar la cuenta') from None
        code=exc.code if exc.code in (403,404,410,429) else 502
        message={403:'Google no permite acceder a este archivo; revisa sus permisos',404:'Archivo no disponible en Google Drive',410:'El cursor de Drive venció; se reiniciará la lectura',429:'Google limitó las solicitudes; se reintentará después'}.get(code,'No se pudo completar la operación con Google')
        raise HTTPException(code,message) from None
    except (URLError,TimeoutError,ValueError,OSError):
        raise HTTPException(502,'Google no respondió correctamente; vuelve a intentarlo') from None


def exchange(values):
    return transport(TOKEN_URL,data=urlencode(values).encode(),content_type='application/x-www-form-urlencoded')


class GoogleDrive:
    def __init__(self, token):self.token=token

    def get(self, path, **params):
        return transport(API+path+('?' + urlencode(params) if params else ''),token=self.token)

    def identity(self):return self.get('about',fields='user(displayName,emailAddress,permissionId)')['user']

    def metadata(self, file_id):return self.get('files/'+remote_id(file_id),fields=FIELDS,supportsAllDrives='true')

    def files(self, folder='root', search='', page='', size=20, order='name'):
        parent=remote_id(folder)
        q="trashed = false and '"+parent+"' in parents"
        if search:q+=" and name contains '"+search.replace('\\','\\\\').replace("'","\\'")+"'"
        args=dict(q=q,pageSize=size,fields='nextPageToken,files('+FIELDS+')',orderBy=order,spaces='drive',supportsAllDrives='true',includeItemsFromAllDrives='true')
        if page:args['pageToken']=page
        return self.get('files',**args)

    def start(self):return self.get('changes/startPageToken')['startPageToken']

    def changes(self, cursor):return self.get('changes',pageToken=cursor,pageSize=20,spaces='drive',fields='nextPageToken,newStartPageToken,changes(fileId,removed,file('+FIELDS+'))',includeRemoved='true')

    def download(self, metadata):
        if metadata.get('capabilities',{}).get('canDownload') is False:raise HTTPException(403,'El propietario impide descargar este archivo')
        if int(metadata.get('size',0))>MAX_BYTES:raise HTTPException(413,'Máximo 20 MB por archivo')
        file_id=remote_id(metadata['id']);name=metadata['name']
        if metadata['mimeType'] in EXPORTS:
            suffix,mime=EXPORTS[metadata['mimeType']]
            name=name+'.'+suffix
            path='files/'+file_id+'/export?'+urlencode({'mimeType':mime})
        else:
            if metadata['mimeType'].startswith('application/vnd.google-apps.'):
                raise HTTPException(422,'Este tipo de Google no se importa; selecciona un documento, hoja o presentación')
            path='files/'+file_id+'?alt=media&supportsAllDrives=true'
        return name,transport(API+path,token=self.token,binary=True)

    def export_copy(self, parent, filename, mime, data, key):
        parent=remote_id(parent)
        # La marca permite recuperar una creación cuya respuesta se perdió.
        found=self.get('files',q="trashed=false and '"+parent+"' in parents and appProperties has { key='abissol_version' and value='"+key+"' }",fields='files(id,name)',pageSize=1)
        if found.get('files'):return found['files'][0]
        boundary=uuid4().hex
        metadata=json.dumps({'name':filename,'parents':[parent],'appProperties':{'abissol_version':key}},ensure_ascii=False).encode()
        body=(('--'+boundary+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n').encode()+metadata+('\r\n--'+boundary+'\r\nContent-Type: '+mime+'\r\n\r\n').encode()+data+('\r\n--'+boundary+'--\r\n').encode())
        return transport('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name&supportsAllDrives=true',token=self.token,data=body,content_type='multipart/related; boundary='+boundary)
