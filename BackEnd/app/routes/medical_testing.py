from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.medical import Payload
from ..services.access_control import require_access
from ..services.medical_testing import activate
from . import medical as m
router=APIRouter(prefix='/medical')

class TestMode(Payload):
    enabled:bool

@router.put('/billing/test-mode')
def test_mode(payload:TestMode,request:Request,db:Session=Depends(get_db),user=Depends(require_access('medical-billing','gestor'))):
    if not m.fiscal.programmer(user):raise HTTPException(403,'Solo Programador puede cambiar el modo de pruebas')
    batch=activate(db,payload.enabled)
    m.audit_change(db,request,user,'medical_test_mode',0,after={'test_batch':batch,'sunat_enabled':False},module='abissol_medical')
    db.commit()
    return {'test_batch':batch,'sunat_enabled':False}
