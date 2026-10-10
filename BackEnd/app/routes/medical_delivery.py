from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..services.access_control import require_access
from ..models.medical import MedicalSource
from . import medical as m
from .medical_integrations import ExternalDispatch, send_information, external_id

router=APIRouter(prefix='/medical')


@router.post('/emissions/{ident}/send-client')
def send_client(ident:int,payload:ExternalDispatch,request:Request,db:Session=Depends(get_db),user=Depends(require_access('medical-dispatches','editor'))):
    row=m.find(m.scope(db,user),ident,True)
    return send_information(external_id(row),payload,request,db,(db.get(MedicalSource,row.source_id),user))
