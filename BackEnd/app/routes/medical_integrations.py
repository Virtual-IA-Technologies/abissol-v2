"""Source-scoped connector contract. Technical tokens never authorize portal APIs."""
import hashlib
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response,FileResponse
from pydantic import EmailStr, Field, model_validator, ValidationError
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Usuario
from ..models.medical import MedicalIntegrationCredential, MedicalSource, MedicalProfile, MedicalIssuance, MedicalPlan, MedicalInvoice
from ..schemas.medical import Payload, IssuanceInput, Money, BillingPreference
from ..services.medical_issuance import create_sale
from ..services import medical_billing as fiscal
from . import medical as m

router = APIRouter(prefix="/integrations/medical")
V2_ID_BASE = 1_000_000_000


def connector(request:Request,authorization: str = Header(""), db: Session = Depends(get_db)):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not 40 <= len(token) <= 180:
        raise HTTPException(401,"Credencial de integración requerida")
    credential = db.query(MedicalIntegrationCredential).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest(),active=True).first()
    source = db.get(MedicalSource,credential.source_id) if credential else None
    actor = db.get(Usuario,credential.actor_id) if credential else None
    if not source or not source.active or not source.external_key or not actor or not actor.is_active or actor.deleted_at:
        raise HTTPException(401,"Integración desactivada o credencial inválida")
    if credential.test_only:
        if not fiscal.configuration(db)[1].get('test_batch'):
            raise HTTPException(409,'El acceso de prueba está cerrado. No se permiten emisiones reales con esta credencial.')
        if request.url.path.endswith('/external-users/sync'):
            raise HTTPException(403,'El acceso de prueba no modifica usuarios ni comisiones reales')
        request.state.medical_test_only=True
        db.info['medical_test_only']=True
    return source, actor


def external_id(row):
    return row.legacy_id or V2_ID_BASE + row.id


def issuance(db, source, ident):
    query = db.query(MedicalIssuance).filter_by(source_id=source.id)
    if db.info.get('medical_test_only'):query=query.filter(MedicalIssuance.test_batch.is_not(None))
    row = query.filter(MedicalIssuance.id==ident-V2_ID_BASE).first() if ident>=V2_ID_BASE else query.filter_by(legacy_id=ident).first()
    if not row:
        raise HTTPException(404,"Emisión no encontrada en este origen")
    return row


def shape(db, row, request, profiles=None, invoices=None):
    profiles = profiles if profiles is not None else {p.id:p for p in db.query(MedicalProfile).filter(MedicalProfile.id.in_({row.emitter_id,row.responsible_id}))}
    emitter, responsible = profiles.get(row.emitter_id),profiles.get(row.responsible_id)
    invoice=invoices.get(row.id) if invoices is not None else db.query(MedicalInvoice).filter_by(issuance_id=row.id).first()
    url = str(request.base_url).rstrip('/') + '/abissol/api/v1/integrations/medical/emissions/' + str(external_id(row)) + '/letter'
    return {"id":external_id(row),"internal_code":row.code,"plan_id":row.plan_id,"plan":{"id":row.plan_id,"name":row.plan_name,"conditioned_public_url":row.conditions_url},
        "contractor_name":row.first_names or row.customer,"contractor_paternal_last_name":row.paternal_surname,"contractor_maternal_last_name":row.maternal_surname,
        "contractor_document_type":row.document_type,"contractor_document_number":row.document_number,"contractor_email":row.email,"contractor_phone":row.phone,
        "sale_date":str(row.sale_date),"starts_at":str(row.starts_on),"ends_at":str(row.ends_on),"status":row.status,"payment_status":row.payment_status,
        "sale_price":str(row.price),"provider_cost":str(row.provider_cost),"seller_commission_amount":str(row.seller_commission),"platform_commission_amount":str(row.platform_fee),
        "external_source":db.get(MedicalSource,row.source_id).external_key,"external_reference":row.external_reference,
        "issuance_channel":"external" if row.external_reference else "internal",
        "external_emitter_id":int(emitter.external_user_id) if emitter and (emitter.external_user_id or '').isdigit() else None,
        "external_responsible_id":int(responsible.external_user_id) if responsible and (responsible.external_user_id or '').isdigit() else None,
        "external_emitter_name":emitter.display_name if emitter else '',"external_responsible_name":responsible.display_name if responsible else '',
        "welcome_letter_api_url":url,"public_verification_url":m.public_url(request,row),"conditioned_public_url":row.conditions_url,
        "invoice_id":external_id(invoice) if invoice else None,"invoice_number":invoice.full_number if invoice else None,
        "invoice_pdf_api_url":str(request.base_url).rstrip('/')+'/abissol/api/v1/integrations/medical/billing/'+str(external_id(invoice))+'/file/PDF' if invoice else None,
        "test_batch":row.test_batch,"billing_mode":"local_test" if row.test_batch else "automatic_queue","integration_version":2}


class ExternalEmission(Payload):
    plan_id: int = Field(gt=0)
    external_source: str = Field(min_length=1,max_length=80)
    external_reference: str = Field(min_length=1,max_length=100)
    external_emitter_id: int = Field(gt=0)
    external_responsible_id: int = Field(gt=0)
    contractor_document_type: Literal["DNI","CE","PASSPORT"] = "DNI"
    contractor_document_number: str = Field(min_length=6,max_length=20)
    contractor_name: str = Field(min_length=1,max_length=100)
    contractor_paternal_last_name: str = Field(default="",max_length=80)
    contractor_maternal_last_name: str = Field(default="",max_length=80)
    contractor_email: str | None = Field(default=None,max_length=180)
    contractor_phone: str | None = Field(default=None,max_length=25)
    starts_at: date | None = None
    sale_date: date | None = None
    ends_at: date | None = None
    payment_method: Literal["cash","online","transfer","card"] = "cash"
    payment_status: Literal["pending","collected_by_seller"] | None = None
    seller_id: int | None = None  # Legacy hint, never used as an identity.
    billing: BillingPreference
    metadata: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_size(self):
        if len(str(self.metadata))>6000:
            raise ValueError("Metadata demasiado grande")
        return self


@router.get("/capabilities")
def capabilities(db: Session = Depends(get_db), identity=Depends(connector)):
    config=fiscal.configuration(db)[1]
    return {"version":2,"source":identity[0].external_key,"emissions":True,"idempotency":True,
            "test_batch":config.get("test_batch"),"billing_enabled":bool(config.get('enabled_in_v2') or config.get("test_batch")),"invoice_types":["03","01"],
            "billing_mode":"automatic_queue","letter_delivery":"authenticated_api","cutover_ready":False,
            "pending":["Confirmar series exclusivas y corte del conector ALP con el adaptador V2"]}


@router.get("/plans")
def plans(db: Session = Depends(get_db), identity=Depends(connector)):
    return {"data":[{"id":p.id,"code":p.code,"name":p.name,"sale_price":str(p.price),"is_active":p.active,
        "conditioned_public_url":p.conditions_url} for p in db.query(MedicalPlan).filter_by(active=True).order_by(MedicalPlan.id)]}


def prepare_external(payload, request, db, identity, dry_run=False):
    source, actor = identity
    if payload.metadata.get('is_test') and not dry_run and not fiscal.configuration(db)[1].get('test_batch'):
        raise HTTPException(422,"Para pruebas usa emissions/validate; no se registran ventas simuladas en producción")
    if payload.external_source != source.external_key:
        raise HTTPException(403,"La credencial no autoriza este origen")
    # Source lock serializes references even when several credentials serve one origin.
    db.query(MedicalSource).filter_by(id=source.id).with_for_update().one()
    existing=db.query(MedicalIssuance).filter_by(external_source=source.external_key,external_reference=payload.external_reference).first()
    if existing:
        if db.info.get('medical_test_only') and not existing.test_batch:
            raise HTTPException(409,'La referencia pertenece a una emisión real')
        em=db.get(MedicalProfile,existing.emitter_id)
        rp=db.get(MedicalProfile,existing.responsible_id)
        if existing.source_id!=source.id or existing.plan_id!=payload.plan_id or existing.document_number!=payload.contractor_document_number or existing.document_type!=payload.contractor_document_type or em.external_user_id!=str(payload.external_emitter_id) or rp.external_user_id!=str(payload.external_responsible_id):
            raise HTTPException(409,"La referencia ya corresponde a otra emisión; no reutilices la referencia")
        if existing.billing_preference and existing.billing_preference!=payload.billing.model_dump(mode='json'):
            raise HTTPException(409,"La referencia ya tiene otros datos de facturación; no se cambia un comprobante mediante reintentos")
        return {"data":shape(db,existing,request),"idempotent":True}
    emitter=db.query(MedicalProfile).filter_by(source_id=source.id,external_user_id=str(payload.external_emitter_id),active=True).first()
    responsible=db.query(MedicalProfile).filter_by(source_id=source.id,external_user_id=str(payload.external_responsible_id),active=True,kind="responsible").first()
    if not emitter or not responsible or (emitter.manager_id if emitter.kind=="emitter" else emitter.id)!=responsible.id:
        raise HTTPException(422,"Emisor y responsable no están vinculados en este origen. Sincroniza la red comercial.")
    parts=[payload.contractor_name,payload.contractor_paternal_last_name,payload.contractor_maternal_last_name]
    try:
        values=IssuanceInput(plan_id=payload.plan_id,emitter_id=emitter.id,document_type=payload.contractor_document_type,
        document_number=payload.contractor_document_number,customer=' '.join(p for p in parts if p),first_names=parts[0],paternal_surname=parts[1],maternal_surname=parts[2],
        email=payload.contractor_email or '',phone=payload.contractor_phone or '',starts_on=payload.starts_at or datetime.now(ZoneInfo('America/Lima')).date()+timedelta(days=1),
        payment_method=payload.payment_method,payment_status=payload.payment_status or ('pending' if payload.payment_method=='online' else 'collected_by_seller'),
            external_source=source.external_key,external_reference=payload.external_reference,billing=payload.billing)
    except ValidationError:
        raise HTTPException(422,"Revisa documento, nombres, correo, teléfono y forma de pago de la emisión") from None
    row=create_sale(db,values,emitter,actor.id)
    result={"data":shape(db,row,request),"idempotent":False,"validated_only":dry_run}
    if dry_run:
        db.rollback()
        result["data"].pop("id",None)
        result["data"].pop("public_verification_url",None)
        result["data"].pop("welcome_letter_api_url",None)
    else:
        m.save(db,request,actor,row)
    return result


@router.post("/emissions/validate")
def validate_emission(payload: ExternalEmission, request: Request, db: Session=Depends(get_db), identity=Depends(connector)):
    return prepare_external(payload,request,db,identity,True)


@router.post("/emissions")
def create_emission(payload: ExternalEmission, request: Request, db: Session=Depends(get_db), identity=Depends(connector)):
    return prepare_external(payload,request,db,identity)


@router.get("/emissions")
def emissions(request: Request, date_from: date | None=None, date_to: date | None=None, search: str=Query('',max_length=180),
              offset: int=Query(0,ge=0),limit: int=Query(100,ge=1,le=500),db: Session=Depends(get_db),identity=Depends(connector)):
    query=m.filtered(db.query(MedicalIssuance).filter_by(source_id=identity[0].id),search,date_from,date_to)
    if db.info.get('medical_test_only'):query=query.filter(MedicalIssuance.test_batch.is_not(None))
    total=query.count()
    rows=query.order_by(MedicalIssuance.id.desc()).offset(offset).limit(limit).all()
    ids={ident for row in rows for ident in (row.emitter_id,row.responsible_id)}
    profiles={p.id:p for p in db.query(MedicalProfile).filter(MedicalProfile.id.in_(ids))} if ids else {}
    invoices={i.issuance_id:i for i in db.query(MedicalInvoice).filter(MedicalInvoice.issuance_id.in_([r.id for r in rows]))} if rows else {}
    return {"data":[shape(db,row,request,profiles,invoices) for row in rows],"total":total,"offset":offset,"limit":limit}


@router.get("/emissions/{ident}")
def detail(ident:int,request:Request,db:Session=Depends(get_db),identity=Depends(connector)):
    return {"data":shape(db,issuance(db,identity[0],ident),request)}


@router.get("/emissions/{ident}/letter")
def letter(ident:int,request:Request,db:Session=Depends(get_db),identity=Depends(connector)):
    row=issuance(db,identity[0],ident)
    from ..services.medical_information import letter_file
    archived=letter_file(db,row)
    if archived:return FileResponse(archived[0],filename=archived[1],media_type=archived[2],headers={'Cache-Control':'no-store'})
    if row.legacy_id:
        original=m.legacy_data(db,'medical_issuances',row.legacy_id)
        return m.legacy_download(db,original.get('welcome_letter_path'),filename=row.code+'.pdf')
    return Response(m.letter_pdf(row,m.public_url(request,row)),media_type='application/pdf',headers={'Cache-Control':'no-store'})


@router.get("/liquidations/pending-issuances")
def pending(period_start:date,period_end:date,db:Session=Depends(get_db),identity=Depends(connector)):
    if period_end<period_start:
        raise HTTPException(422,"El período está invertido")
    query=db.query(MedicalIssuance).filter_by(source_id=identity[0].id,status='issued',test_batch=None)
    active=db.query(m.Item.issuance_id).join(m.Liquidation,m.Liquidation.id==m.Item.liquidation_id).filter(m.Item.active_key.is_not(None),m.Liquidation.kind=='seller')
    rows=query.filter(MedicalIssuance.sale_date.between(period_start,period_end),MedicalIssuance.payment_status!='pending',~MedicalIssuance.id.in_(active.scalar_subquery())).order_by(MedicalIssuance.id).limit(1001).all()
    if len(rows)>1000:
        raise HTTPException(422,"Reduce el período a un máximo de 1000 emisiones")
    afocat=m.afocat_emissions(db,rows,'seller')
    return {"data":{"items":[{"issuance_id":external_id(e),"internal_code":e.code,"commission":str(e.seller_commission),"deposit":str(m.liquidation_amounts(e,'seller',afocat)[1])} for e in rows]}}


@router.get("/billing/from-issuance/{ident}")
def billing_status(ident:int,db:Session=Depends(get_db),identity=Depends(connector)):
    row=issuance(db,identity[0],ident)
    invoice=db.query(MedicalInvoice).filter_by(issuance_id=row.id).first()
    return {"data":None if not invoice else {"id":external_id(invoice),"full_number":invoice.full_number,"status":invoice.status,"sunat_status":invoice.sunat_status},
            "billing_enabled":bool(fiscal.configuration(db)[1].get('enabled_in_v2'))}


class ExternalSource(Payload):
    external_key: str = Field(min_length=1,max_length=80)
    code: str = Field(min_length=1,max_length=50)
    name: str = Field(min_length=1,max_length=180)


class ExternalUser(Payload):
    external_user_id: int = Field(gt=0)
    name: str = Field(min_length=1,max_length=180)
    username: str | None = Field(default=None,max_length=50)
    phone: str | None = Field(default=None,max_length=30)
    role: Literal[2,3,4]
    responsible_external_user_id: int | None = Field(default=None,gt=0)
    active: bool
    commission_esencial: Money | None = None
    commission_plus: Money | None = None


class ExternalUsers(Payload):
    source: ExternalSource
    users: list[ExternalUser] = Field(min_length=1,max_length=2000)


@router.post("/external-users/sync")
def sync_users(payload:ExternalUsers,request:Request,db:Session=Depends(get_db),identity=Depends(connector)):
    source,actor=identity
    if payload.source.external_key!=source.external_key:
        raise HTTPException(403,"La credencial no autoriza este origen")
    if len({p.external_user_id for p in payload.users})!=len(payload.users):
        raise HTTPException(422,"Hay usuarios externos duplicados en el lote")
    db.query(MedicalSource).filter_by(id=source.id).with_for_update().one()
    profiles={p.external_user_id:p for p in db.query(MedicalProfile).filter_by(source_id=source.id)}
    used={ident for e,r in db.query(MedicalIssuance.emitter_id,MedicalIssuance.responsible_id).filter_by(source_id=source.id).distinct() for ident in (e,r)}
    plans={p.code.replace('-','_'):p for p in db.query(MedicalPlan)}
    created=0
    for entry in payload.users:
        key=str(entry.external_user_id)
        profile=profiles.get(key)
        kind={2:'source_admin',3:'responsible',4:'emitter'}[entry.role]
        if not profile:
            profile=MedicalProfile(source_id=source.id,external_user_id=key,kind=kind)
            db.add(profile);profiles[key]=profile;created+=1
        if profile.id in used and profile.kind!=kind:
            raise HTTPException(409,"No se puede cambiar el tipo de un participante con emisiones históricas")
        profile.display_name,profile.kind,profile.active=entry.name,kind,entry.active
        overrides=dict(profile.commission_overrides or {})
        for code,amount in (('HAMPI_ESENCIAL',entry.commission_esencial),('HAMPI_PLUS',entry.commission_plus)):
            plan=plans.get(code)
            if amount is not None and plan:
                if amount+plan.provider_cost+plan.platform_fee>plan.price:
                    raise HTTPException(422,"La comisión supera el margen del plan")
                overrides[str(plan.id)]=str(amount)
        profile.commission_overrides=overrides
    db.flush()
    for entry in payload.users:
        profile=profiles[str(entry.external_user_id)]
        parent=profiles.get(str(entry.responsible_external_user_id)) if entry.role==4 else None
        if entry.role==4 and (not parent or parent.kind!='responsible' or (entry.active and not parent.active)):
            raise HTTPException(422,"Falta el responsable activo del emisor externo")
        manager_id=parent.id if parent else None
        if profile.id in used and profile.manager_id!=manager_id:
            raise HTTPException(409,"El responsable de un emisor con historial requiere conciliación; no se reasigna automáticamente")
        profile.manager_id=manager_id
    # The source cannot change portal passwords, roles, linked accounts or another source.
    m.audit_change(db,request,actor,'medical_external_sync',source.id,after={'source':source.external_key,'received':len(payload.users),'created':created},module='abissol_medical')
    db.commit()
    return {'data':{'created':created,'updated':len(payload.users)-created,'source_id':source.id}}


@router.get("/sellers")
def sellers(db:Session=Depends(get_db),identity=Depends(connector)):
    return {'data':[{'id':p.id,'name':p.display_name,'external_source':identity[0].external_key,'external_user_id':p.external_user_id,
        'source_role':p.kind,'responsible_seller_id':p.manager_id,'active':p.active} for p in db.query(MedicalProfile).filter_by(source_id=identity[0].id)]}


class ExternalDispatch(Payload):
    email: bool = False
    whatsapp: bool = False
    recipient_email: EmailStr | None = None
    recipient_phone: str | None = Field(default=None,min_length=6,max_length=25,pattern=r'^[+0-9 ()-]+$')
    force: bool = False
    real_test: bool = False


@router.post('/emissions/{ident}/resend')
def send_information(ident:int,payload:ExternalDispatch,request:Request,db:Session=Depends(get_db),identity=Depends(connector)):
    source,actor=identity
    row=issuance(db,source,ident)
    db.query(MedicalIssuance).filter_by(id=row.id).with_for_update().one()
    if row.status!='issued':
        raise HTTPException(409,'No se envían certificados anulados')
    channels=[]
    if payload.email:channels.append(('email',str(payload.recipient_email or row.email)))
    if payload.whatsapp:channels.append(('whatsapp',payload.recipient_phone or row.phone))
    if not channels or any(not recipient for _,recipient in channels):
        raise HTTPException(422,'Selecciona un canal con destinatario válido')
    from ..services.medical_testing import check_delivery
    for channel,recipient in channels:check_delivery(db,row,channel,recipient,payload.real_test)
    attempts=[]
    for channel,recipient in channels:
        previous=db.query(m.Dispatch).filter_by(issuance_id=row.id,channel=channel,recipient=recipient).filter(
            m.or_(m.Dispatch.kind.is_(None),m.Dispatch.kind.notin_(['meta_daily_report','metafin_monthly'])))
        if previous.filter(m.Dispatch.status.in_(['pending','sending'])).first():
            raise HTTPException(409,'Hay un envío en curso; comprueba su resultado antes de repetir')
        if not payload.force and previous.first():
            raise HTTPException(409,'Existe un intento previo; revisa el proveedor y confirma force para reenviar')
        attempt=m.Dispatch(issuance_id=row.id,kind='insured',channel=channel,recipient=recipient,status='pending',created_by=actor.id)
        db.add(attempt);attempts.append(attempt)
    m.audit_change(db,request,actor,'medical_external_dispatch',row.id,after={'channels':[c for c,_ in channels],'source':source.external_key},module='abissol_medical')
    db.commit()  # Reserve all selected channels before contacting any provider.
    return {'data':[m.deliver(db,request,actor,attempt,row,real_test=payload.real_test) for attempt in attempts]}


def scoped_invoice(db,source,ident):
    query=db.query(MedicalInvoice).join(MedicalIssuance,MedicalIssuance.id==MedicalInvoice.issuance_id).filter(MedicalIssuance.source_id==source.id)
    if db.info.get('medical_test_only'):query=query.filter(MedicalIssuance.test_batch.is_not(None))
    row=query.filter(MedicalInvoice.id==ident-V2_ID_BASE).first() if ident>=V2_ID_BASE else query.filter(MedicalInvoice.legacy_id==ident).first()
    if not row:raise HTTPException(404,'Comprobante no encontrado en este origen')
    return row


def invoice_shape(db,row,request):
    emission=db.get(MedicalIssuance,row.issuance_id)
    base=str(request.base_url).rstrip('/')+'/abissol/api/v1/integrations/medical/billing/'+str(external_id(row))
    files=(row.details or {}).get('files',{})
    return {'id':external_id(row),'issuance_id':external_id(emission),'full_number':row.full_number,'full_number_label':row.full_number,
        'invoice_type_code':'01' if row.document_type=='factura' else '03','status':row.status,'sunat_status':row.sunat_status,
        'pdf_a4_path':'available' if files.get('PDF') else None,'pdf_api_url':base+'/file/PDF','xml_api_url':base+'/file/XML',
        'cdr_path':'available' if files.get('CDR') else None,'cdr_api_url':base+'/file/CDR','total':str(row.total)}


class BillingRequest(BillingPreference):
    customer_email: EmailStr | None = None
    customer_phone: str | None = Field(default=None,max_length=30)
    customer_department_id: str | None = Field(default=None,max_length=2)
    customer_province_id: str | None = Field(default=None,max_length=4)
    customer_district_id: str | None = Field(default=None,max_length=6)
    include_exonerated: bool = True


@router.post('/billing/from-issuance/{ident}')
def existing_invoice(ident:int,payload:BillingRequest,request:Request,db:Session=Depends(get_db),identity=Depends(connector)):
    emission=issuance(db,identity[0],ident)
    row=db.query(MedicalInvoice).filter_by(issuance_id=emission.id).first()
    if not row:
        raise HTTPException(409,'No se numeró un comprobante. Revisa la configuración fiscal antes de volver a emitir; no dupliques la venta.')
    if payload.invoice_type_code!=('01' if row.document_type=='factura' else '03') or (payload.customer_document_number and payload.customer_document_number!=row.document_number):
        raise HTTPException(409,'El comprobante ya fue numerado para otro tipo o adquirente; no se genera un segundo documento')
    return {'data':invoice_shape(db,row,request),'idempotent':True}


class DniLookup(Payload):
    dni: str = Field(pattern=r'^\d{8}$')


class RucLookup(Payload):
    document: str = Field(pattern=r'^\d{11}$')


def lookup_identity(kind,number):
    from ..services.apiperu import lookup_document,public_document_result,ApiPeruNotFound,ApiPeruUnavailable
    try:
        result=public_document_result(kind,number,lookup_document(kind,number).payload)
    except ApiPeruNotFound as exc:
        raise HTTPException(404,str(exc)) from exc
    except ApiPeruUnavailable as exc:
        raise HTTPException(503,str(exc)) from exc
    return {'data':{**result,'document':number,'number':number,'name':result.get('business_name') or result.get('full_name'),
        'names':result.get('first_names'),'paternal_last_name':result.get('paternal_surname'),'maternal_last_name':result.get('maternal_surname'),
        'nombres':result.get('first_names'),'apellido_paterno':result.get('paternal_surname'),'apellido_materno':result.get('maternal_surname'),
        'department_id':(result.get('ubigeo') or '')[:2],'province_id':(result.get('ubigeo') or '')[:4],'district_id':result.get('ubigeo')}}


@router.post('/lookup/dni')
def lookup_dni(payload:DniLookup,identity=Depends(connector)):
    return lookup_identity('dni',payload.dni)


@router.post('/billing/lookup-document')
def lookup_ruc(payload:RucLookup,identity=Depends(connector)):
    return lookup_identity('ruc',payload.document)


@router.get('/billing/departments')
def departments(db:Session=Depends(get_db),identity=Depends(connector)):
    from ..models.ubigeo import Ubigeo as U
    return {'data':[{'id':code,'description':name,'name':name} for code,name in db.query(U.department_code,U.department).filter_by(is_active=True).distinct().order_by(U.department)]}


@router.get('/billing/provinces')
def provinces(department_id:str=Query(pattern=r'^\d{2}$'),db:Session=Depends(get_db),identity=Depends(connector)):
    from ..models.ubigeo import Ubigeo as U
    return {'data':[{'id':code,'description':name,'name':name} for code,name in db.query(U.province_code,U.province).filter_by(is_active=True,department_code=department_id).distinct().order_by(U.province)]}


@router.get('/billing/districts')
def districts(province_id:str=Query(pattern=r'^\d{4}$'),db:Session=Depends(get_db),identity=Depends(connector)):
    from ..models.ubigeo import Ubigeo as U
    return {'data':[{'id':code,'description':name,'name':name} for code,name in db.query(U.code,U.district).filter_by(is_active=True,province_code=province_id).order_by(U.district)]}


@router.get('/billing/{ident}')
def invoice_detail(ident:int,request:Request,db:Session=Depends(get_db),identity=Depends(connector)):
    return {'data':invoice_shape(db,scoped_invoice(db,identity[0],ident),request)}


@router.post('/billing/{ident}/generate')
def generate_invoice(ident:int,request:Request,db:Session=Depends(get_db),identity=Depends(connector)):
    row=scoped_invoice(db,identity[0],ident)
    job=db.query(m.FiscalJob).filter_by(invoice_id=row.id).with_for_update().first()
    if row.legacy_id or (row.details or {}).get('test_batch'):
        return {'data':invoice_shape(db,row,request)}
    if not job:raise HTTPException(409,'No existe cola fiscal para este comprobante')
    try:
        fiscal.prepare_artifacts(db,row,job,fiscal.configuration(db)[1])
    except m.FiscalError as exc:
        raise HTTPException(422,str(exc)) from exc
    m.audit_change(db,request,identity[1],'medical_external_fiscal',row.id,after={'action':'generate'},module='abissol_medical')
    db.commit()
    return {'data':invoice_shape(db,row,request)}


@router.post('/billing/{ident}/send-sunat')
def send_invoice(ident:int,request:Request,db:Session=Depends(get_db),identity=Depends(connector)):
    row=scoped_invoice(db,identity[0],ident)
    if (row.details or {}).get('test_batch') or fiscal.configuration(db)[1].get('test_batch'):
        return {'data':invoice_shape(db,row,request),'sent':False,'test_mode':True}
    if row.legacy_id:
        return {'data':invoice_shape(db,row,request),'historical':True}
    job=db.query(m.FiscalJob).filter_by(invoice_id=row.id).first()
    if not job:raise HTTPException(409,'No existe cola fiscal para este comprobante')
    m.audit_change(db,request,identity[1],'medical_external_fiscal',row.id,after={'action':'send_or_query'},module='abissol_medical')
    db.commit()
    fiscal.process_job(db,job.id)
    db.refresh(row)
    return {'data':invoice_shape(db,row,request)}


@router.get('/billing/{ident}/file/{kind}')
def invoice_file(ident:int,kind:Literal['PDF','Ticket','XML','CDR','ZIP'],db:Session=Depends(get_db),identity=Depends(connector)):
    row=scoped_invoice(db,identity[0],ident)
    if row.legacy_id:
        file_id=(row.details or {}).get('files',{}).get(kind)
        if not file_id:raise HTTPException(404,'Archivo histórico no disponible')
        return m.legacy_download(db,file_id=file_id)
    path=fiscal.artifact_path(row,kind)
    digest=(row.details or {}).get('files',{}).get(kind)
    if not digest or not path.is_file():raise HTTPException(404,'Archivo todavía no generado')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise HTTPException(409,'El archivo no supera la comprobación de integridad')
    return m.FileResponse(path,filename=f'{row.full_number}-{kind}{path.suffix}',headers={'Cache-Control':'no-store'})
