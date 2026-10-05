"""Corte de sesiones anterior a una publicación; se ejecuta solo en ese flujo."""
from ..models.device_session import DeviceSession
from ..models.wolverine import ImpersonationSession


def close_previous(db, cutoff):
    sessions=db.query(DeviceSession).filter(DeviceSession.created_at<=cutoff,DeviceSession.revoked_at.is_(None)).update(
        {DeviceSession.revoked_at:cutoff,DeviceSession.revoked_reason:'deployment'},synchronize_session=False)
    impersonations=db.query(ImpersonationSession).filter(ImpersonationSession.started_at<=cutoff,ImpersonationSession.ended_at.is_(None)).update(
        {ImpersonationSession.ended_at:cutoff},synchronize_session=False)
    return {'revoked_sessions':sessions,'closed_impersonations':impersonations,'cutoff':cutoff.isoformat()+'Z'}
