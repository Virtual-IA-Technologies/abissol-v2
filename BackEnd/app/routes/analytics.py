from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.user import Usuario
from ..services.access_control import require_access
from ..services.analytics import dashboard_metrics

router = APIRouter()


@router.get("/panel-principal/metricas")
def get_dashboard_metrics(
    refresh: bool = False,
    db: Session = Depends(get_db),
    user: Usuario = Depends(require_access("inicio", "lector")),
):
    return dashboard_metrics(db, user, use_cache=True, refresh=refresh)
