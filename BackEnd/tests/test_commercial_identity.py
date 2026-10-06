"""Identidades y límites de acceso con datos ficticios, sin tocar Laravel."""
import unittest
import test_medical as medical
from app.models import Usuario
from app.models.medical import MedicalProfile, MedicalSource
from app.services.commercial_roles import ROLE_NAMES


class CommercialIdentityTests(unittest.TestCase):
    setUp = medical.MedicalTests.setUp
    cleanup = medical.MedicalTests.cleanup
    login = medical.MedicalTests.login
    prepare = medical.MedicalTests.prepare
    post = medical.MedicalTests.post
    issuance = medical.MedicalTests.issuance

    def test_external_participant_does_not_create_login_and_ids_are_scoped(self):
        self.prepare()
        first = self.post('/sources', {'code': 'AFOCAT-A', 'name': 'Entidad A', 'kind': 'afocat', 'external_key': 'test_a'})
        second = self.post('/sources', {'code': 'AFOCAT-B', 'name': 'Entidad B', 'kind': 'afocat', 'external_key': 'test_b'})
        payload = {'source_id': first['id'], 'kind': 'responsible', 'display_name': 'Punto externo', 'external_user_id': '4'}
        actor = self.post('/profiles', payload)
        self.assertIsNone(actor['user_id'])
        self.post('/profiles', payload, 409)
        self.post('/profiles', {**payload, 'source_id': second['id']})
        with self.sessions() as db:
            self.assertEqual(db.query(Usuario).count(), 2)
        data = dict(plan_id=self.plan_id, emitter_id=actor['id'], document_number='12345678', customer='Cliente ficticio', starts_on='2099-01-01')
        self.post('/emissions', data, 422)
        self.post('/profiles', {**payload, 'external_user_id': '5', 'apply_role': True}, 422)

    def test_commercial_role_limits_menu_and_records(self):
        self.prepare()
        own_sale = self.issuance()
        linked = self.post('/profiles', {'source_id': self.source_id, 'kind': 'responsible', 'user_id': self.reader_id, 'apply_role': True})
        _, reader_headers = self.login('reader')
        response = self.client.get(medical.API + '/emissions', headers=reader_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 0)
        self.assertEqual(self.client.get(medical.API + f'/emissions/{own_sale["id"]}/letter', headers=reader_headers).status_code, 404)
        for path in ['/network', '/plans', '/billing']:
            self.assertEqual(self.client.get(medical.API + path, headers=reader_headers).status_code, 403)
        with self.sessions() as db:
            u = db.get(Usuario, self.reader_id)
            self.assertIn(ROLE_NAMES['responsible'], [r.nombre for r in u.active_roles()])
            self.assertFalse(any(r.es_superusuario for r in u.active_roles()))
        self.post('/emissions', {'plan_id': self.plan_id, 'emitter_id': linked['id'], 'document_number': '12345678', 'customer': 'Cliente ficticio', 'starts_on': '2099-01-01', 'external_source': 'test_a', 'external_reference': '123'}, 422, reader_headers)

    def test_source_scope_and_cross_source_manager_are_enforced(self):
        self.prepare()
        self.issuance()
        source = self.post('/sources', {'code': 'AFOCAT-A', 'name': 'Entidad A', 'kind': 'afocat', 'external_key': 'test_a'})
        coordinator = self.post('/profiles', {'source_id': source['id'], 'kind': 'source_admin', 'user_id': self.reader_id, 'apply_role': True})
        self.post('/profiles', {'source_id': source['id'], 'kind': 'emitter', 'display_name': 'Emisor externo', 'external_user_id': '7', 'manager_id': self.profile_id}, 404)
        _, headers = self.login('reader')
        self.assertEqual(self.client.get(medical.API + '/emissions', headers=headers).json()['total'], 0)
        self.assertEqual(self.client.get(medical.API + '/network', headers=headers).json()['total'], 1)
        self.post('/sources', {'code': 'ILLEGAL', 'name': 'No autorizado'}, 403, headers)
        with self.sessions() as db:
            db.get(MedicalSource, source['id']).active = False
            db.commit()
        self.assertEqual(self.client.get(medical.API + '/network', headers=headers).json()['total'], 0)

    def test_link_external_account_keeps_the_original_participant(self):
        self.prepare()
        source = self.post('/sources', {'code': 'AFOCAT-A', 'name': 'Entidad A', 'kind': 'afocat', 'external_key': 'test_a'})
        payload = {'source_id': source['id'], 'kind': 'responsible', 'display_name': 'Responsable externo', 'external_user_id': '6'}
        participant = self.post('/profiles', payload)
        response = self.client.put(medical.API + f'/profiles/{participant["id"]}', headers=self.headers, json={**payload, 'user_id': self.reader_id, 'apply_role': True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['id'], participant['id'])
        self.assertEqual(response.json()['external_user_id'], '6')
        with self.sessions() as db:
            self.assertEqual(db.query(MedicalProfile).filter_by(source_id=source['id']).count(), 1)
