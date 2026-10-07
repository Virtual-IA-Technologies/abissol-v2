import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import pymupdf
import test_medical as medical
import test_medical_integration as integration
from test_fiscal import config
from app.models.legacy import MedicalBillingConfiguration
from app.models.medical import MedicalInvoice,MedicalPlan,MedicalIssuance,MedicalIntegrationCredential
from app.models.fiscal import FiscalJob
from app.services import medical_billing as fiscal,medical_testing as testing
from app.utils.secrets import encrypt_secret

class LocalTestModeTests(unittest.TestCase):
    setUp=medical.MedicalTests.setUp
    cleanup=medical.MedicalTests.cleanup
    login=medical.MedicalTests.login
    prepare=medical.MedicalTests.prepare
    post=medical.MedicalTests.post
    issuance=medical.MedicalTests.issuance
    setup_connector=integration.IntegrationTests.setup_connector
    send=integration.IntegrationTests.send

    def enable(self):
        with self.sessions() as db:
            db.add(MedicalBillingConfiguration(payload_encrypted=encrypt_secret(json.dumps(config()))))
            batch=testing.activate(db,True);db.commit()
            self.counter=db.get(MedicalPlan,self.plan_id).counter
            return batch

    def test_portal_preview_no_numbering_no_send_and_persistent_mark(self):
        self.prepare();batch=self.enable()
        with TemporaryDirectory() as tmp,patch.object(fiscal,'STORAGE',Path(tmp)),patch('app.services.sunat.send_bill') as sunat,patch('app.routes.medical.send_email') as email:
            sale=self.issuance();self.assertEqual(sale['test_batch'],batch);self.assertTrue(sale['code'].startswith('PRUEBA-'))
            with self.sessions() as db:
                invoice=db.query(MedicalInvoice).one();ident=invoice.id
                self.assertTrue(invoice.full_number.startswith('TB00-'));self.assertEqual(invoice.sunat_status,'test_not_sent')
                self.assertEqual(db.query(FiscalJob).count(),0);self.assertEqual(db.get(MedicalPlan,self.plan_id).counter,self.counter)
                self.assertEqual(fiscal.configuration(db)[1]['v2_counter'],0)
                self.assertNotIn(b'SignatureValue',fiscal.artifact_path(invoice,'XML').read_bytes())
                with pymupdf.open(fiscal.artifact_path(invoice,'PDF')) as pdf:self.assertIn('PRUEBA LOCAL',''.join(p.get_text() for p in pdf))
                testing.activate(db,False);db.commit()
                # Even later global activation cannot turn this record into a fiscal job.
                row,raw=fiscal.configuration(db);raw['enabled_in_v2']=True;fiscal.persist_config(row,raw);db.commit()
                fiscal.enqueue_boleta(db,db.get(MedicalIssuance,sale['id']));db.commit();self.assertEqual(db.query(FiscalJob).count(),0)
            dispatch=self.post('/dispatches',{'issuance_id':sale['id'],'channel':'email'});self.assertEqual(dispatch['status'],'simulated')
            dispatch=self.post(f'/billing/{ident}/send-client',{'recipient':'test@example.com','files':['PDF']});self.assertEqual(dispatch['status'],'simulated')
            validation=self.client.get(medical.API+'/validate/'+sale['token']).json();self.assertTrue(validation['is_test']);self.assertFalse(validation['valid_now'])
            sunat.assert_not_called();email.assert_not_called()

    def test_external_test_only_credential_idempotency_and_closed_mode(self):
        payload=self.setup_connector();batch=self.enable()
        with self.sessions() as db:db.query(MedicalIntegrationCredential).one().test_only=True;db.commit()
        with TemporaryDirectory() as tmp,patch.object(fiscal,'STORAGE',Path(tmp)),patch('app.services.sunat.send_bill') as send:
            first=self.send({**payload,'metadata':{'is_test':True}});self.assertEqual(first['data']['test_batch'],batch)
            second=self.send(payload);self.assertTrue(second['idempotent'])
            ident=first['data']['invoice_id']
            result=self.client.post(integration.API+f'/billing/{ident}/send-sunat',headers=self.connector_headers)
            self.assertEqual(result.status_code,200);self.assertFalse(result.json()['sent'])
            with self.sessions() as db:
                self.assertEqual(db.query(MedicalIssuance).count(),1);self.assertEqual(db.query(FiscalJob).count(),0)
                self.assertEqual(db.get(MedicalPlan,self.plan_id).counter,self.counter)
                testing.activate(db,False);db.commit()
            self.send({**payload,'external_reference':'second'},expected=409)
            send.assert_not_called()
