import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo
import test_medical as medical
from app.services.apiperu import ApiPeruResult, ApiPeruUnavailable


class EmissionDniTests(unittest.TestCase):
    setUp = medical.MedicalTests.setUp
    cleanup = medical.MedicalTests.cleanup
    login = medical.MedicalTests.login
    prepare = medical.MedicalTests.prepare
    post = medical.MedicalTests.post
    issuance = medical.MedicalTests.issuance

    def test_automatic_lookup_permission_validation_and_name_order(self):
        self.prepare()
        path = medical.platform.API + '/smart-forms/documents/lookup'
        payload = dict(option_slug='medical-emissions', document_type='dni', document_number='12345678')
        with patch('app.routes.smart_forms.lookup_document', return_value=ApiPeruResult({'nombres':'ANA MARIA','apellido_paterno':'PEREZ','apellido_materno':'ROJAS','nombre_completo':'PEREZ ROJAS ANA MARIA','ubigeo':['01','0101','010101']})) as provider:
            result = self.client.post(path, headers=self.headers, json=payload)
            self.assertEqual(result.status_code,200)
            self.assertEqual(result.json()['full_name'],'ANA MARIA PEREZ ROJAS')
            self.assertEqual(result.json()['ubigeo'],'010101')
            self.assertEqual(self.client.post(path,headers=self.headers,json={**payload,'document_number':'1234567'}).status_code,422)
            _, limited = self.login('reader')
            self.assertEqual(self.client.post(path,headers=limited,json=payload).status_code,403)
            self.assertEqual(self.client.post(path,headers=limited,json={**payload,'option_slug':'inicio'}).status_code,403)
            self.assertEqual(provider.call_count,1)
        with patch('app.routes.smart_forms.lookup_document', side_effect=ApiPeruUnavailable('El proveedor no está disponible')):
            self.assertEqual(self.client.post(path,headers=self.headers,json=payload).status_code,503)

    def test_start_date_is_strictly_after_today_in_lima(self):
        self.prepare()
        today = datetime.now(ZoneInfo('America/Lima')).date()
        for value in [today-timedelta(days=1), today]:
            self.post('/emissions', dict(plan_id=self.plan_id,emitter_id=self.profile_id,document_type='DNI',document_number='12345678',customer='Prueba de vigencia',starts_on=value.isoformat()),422)
        for value in [today+timedelta(days=1),today+timedelta(days=10)]:
            result = self.issuance(starts_on=value.isoformat())
            self.assertEqual(result['starts_on'],value.isoformat())

    def test_provider_ubigeo_shapes(self):
        from app.services.apiperu import public_document_result
        from app.schemas.smart_forms import DocumentLookupResponse
        for data, expected in [({'ubigeo': ['01','0101','010101']}, '010101'), ({'ubigeo':'010101'}, '010101'), ({'ubigeo':[]}, None), ({'ubigeo':{}}, None), ({'ubigeo':['01'], 'ubigeo_sunat':'010101'}, '010101')]:
            result = DocumentLookupResponse(**public_document_result('dni','12345678',data))
            self.assertEqual(result.ubigeo, expected)
