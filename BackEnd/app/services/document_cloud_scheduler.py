"""Planificador ligero; los leases en base coordinan procesos y ejecución manual."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from sqlalchemy import or_
from ..database import SessionLocal
from ..models.document_cloud import CloudAccount, CloudFolder
from ..models import Usuario
from ..utils.time import utc_now
from .document_cloud import sync_folder


def run_due(limit=1):
    with SessionLocal() as db:
        ids=[row.id for row in db.query(CloudFolder).join(CloudAccount).join(Usuario,Usuario.id==CloudAccount.owner_id).filter(CloudFolder.enabled.is_(True),CloudAccount.active.is_(True),Usuario.is_active.is_(True),Usuario.deleted_at.is_(None),CloudFolder.next_run<=utc_now(),or_(CloudAccount.lease_until.is_(None),CloudAccount.lease_until<utc_now())).order_by(CloudFolder.next_run).limit(limit).all()]
    for binding_id in ids:sync_folder(binding_id)
    return len(ids)


async def loop():
    while True:
        await asyncio.sleep(60)
        try:await asyncio.to_thread(run_due)
        except Exception:logging.getLogger(__name__).warning('No se pudo revisar la cola documental; se reintentará en un minuto')


@asynccontextmanager
async def lifespan(app):
    from .support_chat import directory_loop
    support_task = asyncio.create_task(directory_loop())
    enabled=os.getenv('DOCUMENT_CLOUD_SCHEDULER','true').lower()=='true'
    task=asyncio.create_task(loop()) if enabled else None
    trash_task=asyncio.create_task(trash_loop())
    from .document_extraction import recover_interrupted
    recover_interrupted()
    extraction_task=asyncio.create_task(extraction_loop())
    yield
    support_task.cancel()
    with suppress(asyncio.CancelledError):await support_task
    extraction_task.cancel()
    with suppress(asyncio.CancelledError):await extraction_task
    trash_task.cancel()
    with suppress(asyncio.CancelledError):await trash_task
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):await task


async def trash_loop():
    from .document_trash import run_due as clean_trash
    while True:
        await asyncio.sleep(3600)
        try:await asyncio.to_thread(clean_trash)
        except Exception:logging.getLogger(__name__).exception('No se pudo procesar la retención de Papelera')


async def extraction_loop():
    """Cola documental durable y de baja concurrencia para el VPS inicial."""
    from ..models.settings import AviThread
    from .document_extraction import run_due as extract_due
    cycles = 0
    while True:
        await asyncio.sleep(15)
        try:
            await asyncio.to_thread(extract_due, 2)
            cycles += 1
            if cycles % 240 == 0:  # una vez por hora
                with SessionLocal() as db:
                    db.query(AviThread).filter(AviThread.updated_at < utc_now() - timedelta(days=30)).delete()
                    db.commit()
        except Exception:
            logging.getLogger(__name__).exception('No se pudo procesar la cola de extraccion documental')
