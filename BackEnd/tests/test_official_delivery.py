import json
import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from test_medical_testing import LocalTestModeTests
from test_medical import API
from app.models.medical import MedicalIssuance
from app.services import medical_billing as fiscal


class OfficialDeliveryTests(LocalTestModeTests):
    def test_receipt_preview_respects_emission_scope(self):
        from app.models import AccessGrant, Menu
        self.prepare();self.enable()
        with TemporaryDirectory() as tmp,patch.object(fiscal,'STORAGE',Path(tmp)):
            sale=self.issuance()
            path=API+f'/emissions/{sale["id"]}/receipt'
            response=self.client.get(path,headers=self.headers)
            self.assertEqual(response.status_code,200)
            self.assertTrue(response.content.startswith(b'%PDF'))
            _,headers=self.login('reader')
            with self.sessions() as db:
                menu=db.query(Menu).filter_by(slug='medical-emissions').one()
                db.add(AccessGrant(usuario_id=self.reader_id,menu_id=menu.id,access_level='lector'));db.commit()
            self.assertEqual(self.client.get(path,headers=headers).status_code,404)

    def test_official_search_and_allowed_test_delivery(self):
        self.prepare();self.enable()
        with TemporaryDirectory() as tmp,patch.object(fiscal,'STORAGE',Path(tmp)),patch('app.routes.medical.send_email') as mail,patch('app.routes.medical.send_whatsapp') as whatsapp:
            sale=self.issuance()
            response=self.client.get(API+'/public/search',params={'q':sale['document_number']})
            self.assertEqual(response.status_code,200)
            row=response.json()['data'][0]
            self.assertTrue(row['is_test']);self.assertFalse(row['valid'])
            self.assertEqual(row['document_number'],'12****78')
            self.assertEqual(row['document_display'],sale['document_number'])
            url=row['public_verification_url'];encoded=url.split('consulta=')[1]
            self.assertEqual(json.loads(base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)))['code'],sale['token'])
            self.assertEqual(self.client.get(API+'/public/search',params={'code':sale['token']}).status_code,200)
            self.assertEqual(self.client.get(API+'/public/search',params={'code':sale['token']}).json()['data'][0]['document_display'],sale['document_number'])
            self.assertEqual(self.client.get(API+'/public/search',params={'code':sale['code']}).json()['data'][0]['document_display'],'12****78')
            self.assertEqual(self.client.get(API+'/public/search',params={'q':'unknown-code'}).status_code,404)
            self.assertEqual(self.client.get(API+'/public/search',params={'q':"' OR 1=1"}).status_code,422)
            self.assertTrue(row['welcome_letter_url'].endswith('/letter'))
            path=f'/emissions/{sale["id"]}/send-client'
            denied=self.client.post(API+path,headers=self.headers,json={'email':True,'recipient_email':'approved@example.com','real_test':True})
            self.assertEqual(denied.status_code,403);mail.assert_not_called()
            with self.sessions() as db:
                config,raw=fiscal.configuration(db);raw['test_delivery_emails']=['approved@example.com'];raw['test_delivery_phones']=['51998896625'];fiscal.persist_config(config,raw);db.commit()
            result=self.client.post(API+path,headers=self.headers,json={'email':True,'whatsapp':True,'recipient_email':'approved@example.com','recipient_phone':'51998896625','real_test':True})
            self.assertEqual(result.status_code,200,result.text)
            self.assertTrue(all(r['status']=='sent' for r in result.json()['data']))
            self.assertTrue(mail.call_args.args[2].startswith('Bienvenido'));self.assertIn('abissol.org/?consulta=',mail.call_args.kwargs['html'])
            self.assertFalse(whatsapp.call_args.args[2].startswith('PRUEBA —'))
            duplicate=self.client.post(API+path,headers=self.headers,json={'email':True,'recipient_email':'approved@example.com','real_test':True})
            self.assertEqual(duplicate.status_code,409)
            with self.sessions() as db:
                db.get(MedicalIssuance,sale['id']).status='cancelled';db.commit()
            self.assertEqual(self.client.get(API+'/public/search',params={'code':sale['token']}).json()['data'][0]['welcome_letter_url'],'')
