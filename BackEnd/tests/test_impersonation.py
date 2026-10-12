import unittest
import test_platform as platform
from app.models import Usuario, AuditLog
from app.models.wolverine import ImpersonationSession


class ImpersonationTests(unittest.TestCase):
    setUp = platform.PlatformTests.setUp
    cleanup = platform.PlatformTests.cleanup
    login = platform.PlatformTests.login

    def test_enter_scope_audit_return_and_password_guard(self):
        _, headers = self.login()
        with self.sessions() as db:
            admin = db.query(Usuario).filter_by(username='admin').one().id
            reader = db.query(Usuario).filter_by(username='reader').one().id
        result = self.client.post(platform.API+f'/impersonation/start/{reader}',headers=headers)
        self.assertEqual(result.status_code,200,result.text)
        session = result.json()
        self.assertEqual(session['usuario']['id'],reader)
        self.assertTrue(session['impersonation']['active'])
        acting = {'Authorization':'Bearer '+session['access_token']}
        self.assertEqual(self.client.get(platform.API+'/usuarios',headers=acting).status_code,403)
        self.assertEqual(self.client.post(platform.API+f'/impersonation/start/{admin}',headers=acting).status_code,409)
        leave = self.client.post(platform.API+'/impersonation/leave',headers=acting)
        self.assertEqual(leave.status_code,200,leave.text)
        self.assertEqual(leave.json()['usuario']['id'],admin)
        self.assertFalse(leave.json()['impersonation']['active'])
        with self.sessions() as db:
            row=db.query(ImpersonationSession).one()
            self.assertEqual((row.impersonator_id,row.impersonated_id),(admin,reader))
            self.assertIsNotNone(row.ended_at)
            self.assertTrue(db.query(AuditLog).filter_by(actor_usuario_id=admin,usuario_id=reader,impersonacion_id=row.id).count())
            db.get(Usuario,reader).requiere_cambio_clave=True
            db.commit()
        own = {'Authorization':'Bearer '+leave.json()['access_token']}
        self.assertEqual(self.client.post(platform.API+f'/impersonation/start/{reader}',headers=own).status_code,409)
        _, ordinary = self.login('reader')
        self.assertEqual(self.client.post(platform.API+f'/impersonation/start/{admin}',headers=ordinary).status_code,403)
