"""Archivo verificado de HTTP exitosos antiguos; conserva evidencia funcional."""
from datetime import timedelta
import gzip
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select, func
from ..models.audit import AuditLog
from ..utils.time import utc_now

ARCHIVE_ROOT=Path(__file__).resolve().parents[2]/'storage'/'audit-archive'
RETENTION_DAYS=90


def eligible_query():
    q=select(AuditLog).where(AuditLog.creado_en<utc_now()-timedelta(days=RETENTION_DAYS),
        AuditLog.accion.in_(['post','put','patch','delete']),AuditLog.estado_http>=200,AuditLog.estado_http<400,
        AuditLog.datos_antes.is_(None),AuditLog.datos_despues.is_(None),
        AuditLog.detalle=='Movimiento HTTP auditado automáticamente por ABISSOL')
    return q


def archive_due(db, *, root=ARCHIVE_ROOT, limit=1000):
    rows=db.scalars(eligible_query().order_by(AuditLog.creado_en,AuditLog.id).limit(min(max(limit,1),1000)).with_for_update()).all()
    if not rows:return 0
    payload=b''.join((json.dumps({c.name:getattr(row,c.name) for c in AuditLog.__table__.columns},ensure_ascii=False,default=str)+'\n').encode('utf-8') for row in rows)
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=root/f'{utc_now():%Y%m%dT%H%M%S}-{rows[0].id}-{rows[-1].id}-{uuid4().hex}.jsonl.gz'
    temporary=target.with_suffix('.tmp')
    try:
        with temporary.open('xb') as output:
            os.chmod(temporary,0o600)
            output.write(gzip.compress(payload,mtime=0));output.flush();os.fsync(output.fileno())
        if hashlib.sha256(gzip.decompress(temporary.read_bytes())).digest()!=hashlib.sha256(payload).digest():
            raise RuntimeError('No se pudo verificar el archivo de auditoría')
        temporary.replace(target)
        if os.name=='posix':
            directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(directory)
            finally:os.close(directory)
        for row in rows:db.delete(row)
        db.flush()
        # El llamador confirma en la misma transacción que la auditoría de archivo.
    finally:
        temporary.unlink(missing_ok=True)
    return len(rows)


def list_archives(root=ARCHIVE_ROOT):
    return [{'name':p.name,'bytes':p.stat().st_size} for p in sorted(root.glob('*.jsonl.gz'),reverse=True) if p.is_file() and not p.is_symlink()]
