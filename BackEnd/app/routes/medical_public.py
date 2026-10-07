from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
import re
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import FileResponse,HTMLResponse,RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.medical import MedicalIssuance
from ..services.medical_information import letter_file,conditions_file

router=APIRouter(prefix='/medical/validate')
HEADERS={'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'}

@router.get('/assets/{name}')
def branding_asset(name:str):
    from ..services.medical_rendering import ASSETS
    if name not in {'abissol-logo.png','alp-logo.png'}:raise HTTPException(404,'Imagen no encontrada')
    return FileResponse(ASSETS/name,media_type='image/png',headers={'Cache-Control':'public, max-age=86400','X-Content-Type-Options':'nosniff'})

def public_record(db,token):
    if not re.fullmatch(r'[A-Za-z0-9_-]{43,64}',token):raise HTTPException(404,'Certificado no encontrado')
    row=db.query(MedicalIssuance).filter_by(token=token).first()
    if not row:raise HTTPException(404,'Certificado no encontrado')
    return row

def validation_page(db,row):
    today=datetime.now(ZoneInfo('America/Lima')).date()
    title='Programa anulado' if row.status=='cancelled' else 'Vigencia por iniciar' if row.starts_on>today else 'Programa no vigente' if row.ends_on<today else 'Programa vigente'
    if row.test_batch:title='PRUEBA LOCAL — No acredita cobertura real'
    masked=row.document_number[:2]+'****'+row.document_number[-2:]
    values=[('Código',row.code),('Documento',masked),('Afiliado',row.customer),('Plan',row.plan_name),('Fecha inicio',row.starts_on.strftime('%d/%m/%Y')),('Fecha fin',row.ends_on.strftime('%d/%m/%Y'))]
    fields=''.join('<div class="assistance-field"><span>'+label+'</span><b>'+escape(value)+'</b></div>' for label,value in values)
    base='/abissol/api/v1/medical/validate/'+row.token
    actions=''
    if row.status=='issued':
        actions=f'<a class="assistance-link" href="{base}/letter">Descargar carta de bienvenida</a>'
        if conditions_file(db,row) or row.conditions_url:actions+=f'<a class="assistance-link secondary" href="{base}/conditions">Ver condicionado</a>'
    from ..services.medical_rendering import template
    css=template('public-validation.css')
    return HTMLResponse('''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Consulta de membresía · ABISSOL</title><style>
body{margin:0;background:#f5f8f2;color:#243041;font:16px Arial,sans-serif}main{max-width:880px;margin:40px auto;padding:24px}header{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:28px}header img{max-width:180px;max-height:90px}h1{color:#174b32;font-size:28px}.assistance-result{margin-top:14px;padding:22px;border:1px solid #d8e7cf;border-radius:18px;background:#fff}.assistance-result-title{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:12px}.assistance-result-title strong{color:#174b32;font-size:20px}.assistance-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:16px}.assistance-field{padding:12px 14px;border-radius:12px;background:#f5f8f2;border:1px solid #e3ebdc}.assistance-field span{display:block;font-size:12px;text-transform:uppercase;color:#657460;letter-spacing:.04em;margin-bottom:5px}.assistance-field b{display:block;overflow-wrap:anywhere}.assistance-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:18px}.assistance-link{padding:12px 16px;border-radius:10px;background:#174b32;color:white;text-decoration:none}.assistance-link.secondary{background:#8cc63f;color:#17330c}@media(max-width:600px){main{margin:0;padding:18px}.assistance-grid{grid-template-columns:1fr}header img{max-width:130px}h1{font-size:23px}}
'''+css+'''@media(max-width:600px){.assistance-grid{grid-template-columns:1fr}}</style></head><body><main><header><img src="/abissol/api/v1/medical/validate/assets/abissol-logo.png" alt="ABISSOL"><img src="/abissol/api/v1/medical/validate/assets/alp-logo.png" alt="La Primera"></header><h1>Consulta la vigencia de tu programa de asistencia</h1><div class="assistance-result"><div class="assistance-result-title"><strong>'''+title+'''</strong></div><p>La asistencia fue encontrada en el registro institucional de ABISSOL. Verifica que los datos coincidan con el documento presentado y con las condiciones vigentes del programa.</p><div class="assistance-grid">'''+fields+'''</div><div class="assistance-actions">'''+actions+'''</div></div></main></body></html>''',headers=HEADERS)

@router.get('/{token}/letter')
def welcome_letter(token:str,db:Session=Depends(get_db)):
    row=public_record(db,token)
    if row.status!='issued':raise HTTPException(409,'El programa está anulado; revisa su estado')
    file=letter_file(db,row)
    if not file:raise HTTPException(404,'Carta no disponible')
    return FileResponse(file[0],filename=file[1],media_type=file[2],headers=HEADERS)

@router.get('/{token}/conditions')
def conditions(token:str,db:Session=Depends(get_db)):
    row=public_record(db,token)
    file=conditions_file(db,row)
    if file:return FileResponse(file[0],filename=file[1],media_type=file[2],headers=HEADERS)
    if row.conditions_url.startswith('https://'):return RedirectResponse(row.conditions_url,headers=HEADERS)
    raise HTTPException(404,'Condicionado no disponible')
