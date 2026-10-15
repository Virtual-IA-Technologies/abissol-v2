"""Connector contract and privacy, without contacting people or external services."""
import os
import secrets
import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault('DB_NAME', 'abissol_v2_local')
os.environ.setdefault('DB_USER', 'test')
os.environ.setdefault('SECRET_KEY', secrets.token_urlsafe(48))

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.dialects import mysql
from app.database import Base, get_db
from app.models.user import Usuario
from app.models.device_session import DeviceSession
from app.models.support_chat import SupportChatPresence
from app.routes import support_chat
from app.services import support_chat as presence
from app.utils.jwt import get_current_identity
from app.utils.time import utc_now


class SupportChatTests(unittest.TestCase):
    def test_main_mounts_chat_under_abissol_api_prefix(self):
        from app.main import app
        paths = app.openapi()['paths']
        for route in ('contacts', 'presence', 'messages', 'direct/{operator_id}/messages'):
            self.assertIn('/abissol/api/v1/support-chat/' + route, paths)

    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(support_chat.router, prefix='/abissol/api/v1')
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.user = SimpleNamespace(id=7, nombre='Persona', apellido='ABISSOL', requiere_cambio_clave=False)
        self.identity = SimpleNamespace(effective_user=self.user, device_session_id=11, impersonation_id=None)
        self.app.dependency_overrides[get_current_identity] = lambda: self.identity
        self.app.dependency_overrides[get_db] = lambda: MagicMock()
        self.config = patch.dict(os.environ, SUPPORT_CHAT_URL='https://support.example/support-chat', SUPPORT_CHAT_TOKEN='test-only-secret')
        self.config.start()
        self.addCleanup(self.config.stop)

    def test_session_required_and_impersonation_rejected(self):
        self.app.dependency_overrides.pop(get_current_identity)
        self.assertEqual(self.client.get('/abissol/api/v1/support-chat/contacts').status_code, 401)
        self.app.dependency_overrides[get_current_identity] = lambda: self.identity
        self.identity.impersonation_id = 4
        self.assertEqual(self.client.get('/abissol/api/v1/support-chat/contacts').status_code, 403)
        self.assertEqual(self.client.post('/abissol/api/v1/support-chat/presence').status_code, 403)

    def test_contacts_identity_and_secret_stay_on_server(self):
        response = httpx.Response(200, json={'operators': [], 'unread': 0, 'general_unread': 0})
        with patch.object(httpx.AsyncClient, 'request', new_callable=AsyncMock, return_value=response) as request:
            result = self.client.get('/abissol/api/v1/support-chat/contacts?external_id=999')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request.call_args.kwargs['params']['external_id'], '7')
        self.assertEqual(request.call_args.kwargs['headers']['Authorization'], 'Bearer test-only-secret')
        self.assertNotIn('test-only-secret', result.text)
        self.assertEqual(result.headers['cache-control'], 'private, no-store')

    def test_send_fixes_author_and_preserves_idempotency_key(self):
        from uuid import uuid4
        key = str(uuid4())
        response = httpx.Response(200, json={'id': 1})
        with patch.object(httpx.AsyncClient, 'request', new_callable=AsyncMock, return_value=response) as request:
            result = self.client.post('/abissol/api/v1/support-chat/direct/3/messages?external_id=999', data={
                'body': 'Mensaje ficticio', 'request_key': key, 'name': 'Otra persona', 'external_id': '999'})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(request.call_args.kwargs['params']['external_id'], '7')
        self.assertEqual(request.call_args.kwargs['data']['name'], 'Persona ABISSOL')
        self.assertEqual(request.call_args.kwargs['data']['request_key'], key)

    def test_failure_is_private_and_insecure_url_is_rejected(self):
        with patch.dict(os.environ, SUPPORT_CHAT_URL='http://support.example/support-chat'):
            self.assertEqual(self.client.get('/abissol/api/v1/support-chat/contacts').status_code, 503)
        response = httpx.Response(401, json={'detail': 'private upstream detail'})
        with patch.object(httpx.AsyncClient, 'request', new_callable=AsyncMock, return_value=response):
            result = self.client.get('/abissol/api/v1/support-chat/contacts')
        self.assertEqual(result.status_code, 503)
        self.assertNotIn('private upstream detail', result.text)

    def test_heartbeat_uses_current_session_and_atomic_upsert(self):
        with patch.object(support_chat, 'touch_presence') as touch:
            result = self.client.post('/abissol/api/v1/support-chat/presence', json={'device_session_id': 999})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(touch.call_args.args[1], 11)
        db = MagicMock()
        presence.touch_presence(db, 11)
        sql = str(db.execute.call_args.args[0].compile(dialect=mysql.dialect()))
        self.assertIn('ON DUPLICATE KEY UPDATE', sql)
        db.commit.assert_called_once()

    def test_directory_excludes_disabled_and_expires_revoked_sessions(self):
        engine = create_engine('sqlite://')
        self.addCleanup(engine.dispose)
        Base.metadata.create_all(engine)
        now = utc_now()
        with Session(engine) as db:
            for number in range(1, 7):
                db.add(Usuario(id=number, nombre=f'Usuario {number}', apellido='Prueba', username=f'test{number}',
                               contrasena='not-a-real-hash', correo=f'u{number}@example.invalid',
                               is_active=number != 5, deleted_at=now if number == 6 else None))
            db.flush()
            for number in range(1, 5):
                db.add(DeviceSession(id=number, usuario_id=number, token_hash=str(number) * 64,
                                     expires_at=now + timedelta(hours=1) if number != 4 else now - timedelta(seconds=1),
                                     revoked_at=now if number == 3 else None))
            db.flush()
            for number in range(1, 5):
                db.add(SupportChatPresence(device_session_id=number, seen_at=now - timedelta(seconds=61 if number == 2 else 0)))
            db.commit()
            rows = presence.directory_snapshot(db)
        self.assertEqual({row['external_id']: row['state'] for row in rows}, {
            '1': 'conectado', '2': 'desconectado', '3': 'desconectado', '4': 'desconectado'})
        self.assertTrue(all(set(row) == {'external_id', 'name', 'state'} for row in rows))

    def test_publisher_runs_without_open_chat_and_isolates_failure(self):
        import asyncio
        async def scenario():
            people = [{'external_id': '7', 'name': 'Persona ABISSOL', 'state': 'conectado'}]
            with patch.object(presence, 'snapshot', return_value=people), \
                 patch.object(support_chat, 'relay', new_callable=AsyncMock) as relay, \
                 patch.object(presence.asyncio, 'sleep', new_callable=AsyncMock, side_effect=asyncio.CancelledError):
                with self.assertRaises(asyncio.CancelledError): await presence.directory_loop()
                self.assertEqual(relay.call_args.args, ('POST', '/bridge/directory', None))
                self.assertEqual(relay.call_args.kwargs['json'], {'people': people})
                relay.side_effect = httpx.ConnectError('no network')
                with self.assertLogs(presence.__name__, level='WARNING'):
                    with self.assertRaises(asyncio.CancelledError): await presence.directory_loop()
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
