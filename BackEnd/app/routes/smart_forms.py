from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.ubigeo import Ubigeo
from ..schemas.smart_forms import CatalogOption, DocumentLookupRequest, DocumentLookupResponse
from ..services.access_control import ensure_option_access
from ..services.apiperu import (
    ApiPeruNotFound,
    ApiPeruUnavailable,
    lookup_document,
    public_document_result,
)
from ..utils.jwt import AuthIdentity, get_current_identity


router = APIRouter(prefix="/smart-forms")


def _authorize(db: Session, identity: AuthIdentity, option_slug: str) -> None:
    ensure_option_access(db, identity.effective_user, option_slug, "lector")


@router.post("/documents/lookup", response_model=DocumentLookupResponse)
def document_lookup(
    payload: DocumentLookupRequest,
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    if payload.option_slug not in {'medical-emissions', 'medical-billing'}:
        raise HTTPException(status_code=403, detail='La consulta de documentos requiere acceso comercial')
    ensure_option_access(db, identity.effective_user, payload.option_slug, 'editor')
    try:
        result = lookup_document(payload.document_type, payload.document_number)
    except ApiPeruNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ApiPeruUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return public_document_result(payload.document_type, payload.document_number, result.payload)


@router.get("/ubigeos/departments", response_model=list[CatalogOption])
def departments(
    option_slug: str = Query(min_length=2, max_length=120),
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    _authorize(db, identity, option_slug)
    rows = db.query(Ubigeo.department_code, Ubigeo.department).filter(
        Ubigeo.is_active.is_(True)
    ).distinct().order_by(Ubigeo.department).all()
    return [{"value": code, "label": name} for code, name in rows]


@router.get("/ubigeos/provinces", response_model=list[CatalogOption])
def provinces(
    department_code: str = Query(pattern=r"^\d{2}$"),
    option_slug: str = Query(min_length=2, max_length=120),
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    _authorize(db, identity, option_slug)
    rows = db.query(Ubigeo.province_code, Ubigeo.province).filter(
        Ubigeo.department_code == department_code,
        Ubigeo.is_active.is_(True),
    ).distinct().order_by(Ubigeo.province).all()
    return [{"value": code, "label": name} for code, name in rows]


@router.get("/ubigeos/districts", response_model=list[CatalogOption])
def districts(
    province_code: str = Query(pattern=r"^\d{4}$"),
    option_slug: str = Query(min_length=2, max_length=120),
    identity: AuthIdentity = Depends(get_current_identity),
    db: Session = Depends(get_db),
):
    _authorize(db, identity, option_slug)
    rows = db.query(Ubigeo.code, Ubigeo.district).filter(
        Ubigeo.province_code == province_code,
        Ubigeo.is_active.is_(True),
    ).order_by(Ubigeo.district).all()
    return [{"value": code, "label": name} for code, name in rows]
