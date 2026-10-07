from pathlib import Path
from typing import Literal
from pydantic import EmailStr,Field
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.medical import Payload
from ..services.access_control import require_access
from . import medical as m

router=APIRouter(prefix='/medical')
class InvoiceDelivery(Payload):
    recipient:EmailStr
    files:list[Literal['PDF','XML','CDR','ZIP','Ticket']]=Field(default_factory=lambda:['PDF','XML'],min_length=1,max_length=5)
    force:bool=False

@router.post('/billing/{ident}/send-client')
def send_invoice(ident:int,payload:InvoiceDelivery,request:Request,db:Session=Depends(get_db),user=Depends(require_access('medical-billing','editor'))):
    row=m.find(m.invoice_scope(db,user),ident,True)
    if row.deleted_at or row.status in {'cancelled','voided'}:raise HTTPException(409,'El comprobante está anulado o retirado')
    if row.details and row.details.get('environment')=='beta':raise HTTPException(409,'No se envían comprobantes Beta a clientes desde este flujo')
    previous=db.query(m.Dispatch).filter_by(invoice_id=ident,channel='email',recipient=str(payload.recipient))
    if previous.filter(m.Dispatch.status.in_(['pending','sending'])).first():raise HTTPException(409,'Existe un envío en curso; comprueba su resultado')
    if not payload.force and previous.first():raise HTTPException(409,'Ya existe un intento; comprueba la recepción y confirma el reenvío')
    attachments=[]
    for kind in dict.fromkeys(payload.files):
        response=m.invoice_file(ident,kind,db,user)
        path=Path(response.path);suffix=Path(response.filename or path.name).suffix
        mime='application/pdf' if kind in {'PDF','Ticket'} else 'application/xml' if suffix.lower()=='.xml' else 'application/zip'
        attachments.append((f'{row.full_number}-{kind}{suffix}',path.read_bytes(),mime))
    if sum(len(content) for _,content,_ in attachments)>20*1024*1024:raise HTTPException(413,'Los adjuntos superan 20 MB')
    attempt=m.Dispatch(invoice_id=ident,issuance_id=row.issuance_id,kind='invoice_client',channel='email',recipient=str(payload.recipient),status='sending',attempts=1,created_by=user.id)
    m.save(db,request,user,attempt)
    try:
        m.send_email(db,attempt.recipient,'Comprobante electrónico '+row.full_number,'Adjuntamos su comprobante electrónico '+row.full_number,attachments=attachments)
        attempt.status='sent'
    except Exception:
        attempt.status='uncertain';attempt.error='El proveedor no confirmó la entrega. Comprueba su registro antes de autorizar otro envío.'
    return m.save(db,request,user,attempt,{'status':'sending'})
