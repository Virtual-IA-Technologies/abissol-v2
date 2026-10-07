import hashlib
import secrets
import unittest
from unittest.mock import patch
from datetime import timedelta
import test_medical as medical
from app.models.medical import MedicalIntegrationCredential,MedicalSource,MedicalProfile,MedicalIssuance,MedicalPlan

API='/abissol/api/v1/integrations/medical'


class IntegrationTests(unittest.TestCase):
    setUp=medical.MedicalTests.setUp
    cleanup=medical.MedicalTests.cleanup
    login=medical.MedicalTests.login
    prepare=medical.MedicalTests.prepare
    post=medical.MedicalTests.post
    issuance=medical.MedicalTests.issuance

    def setup_connector(self):
        self.prepare()
        token=secrets.token_urlsafe(48)
        with self.sessions() as db:
            source=db.get(MedicalSource,self.source_id)
            source.external_key,source.kind='externa_alp','afocat'
            profile=db.get(MedicalProfile,self.profile_id)
            profile.external_user_id='100'
            db.add(MedicalIntegrationCredential(source_id=source.id,actor_id=self.admin_id,token_hash=hashlib.sha256(token.encode()).hexdigest(),active=True))
            db.commit()
        self.connector_headers={'Authorization':'Bearer '+token}
        return dict(plan_id=self.plan_id,billing={'invoice_type_code':'03'},external_source='externa_alp',external_reference='alp-cat-test-1',external_emitter_id=100,external_responsible_id=100,
            contractor_document_type='DNI',contractor_document_number='12345678',contractor_name='Persona',contractor_paternal_last_name='De',contractor_maternal_last_name='Prueba')

    def send(self,payload,path='/emissions',expected=200):
        result=self.client.post(API+path,json=payload,headers=self.connector_headers)
        self.assertEqual(result.status_code,expected,result.text)
        return result.json()

    def test_external_contract_retry_and_source_permissions(self):
        payload=self.setup_connector()
        first=self.send(payload)
        self.assertFalse(first['idempotent'])
        self.assertGreater(first['data']['id'],1_000_000_000)
        self.assertEqual(first['data']['seller_commission_amount'],'0.00')
        self.assertEqual(self.send(payload)['data']['id'],first['data']['id'])
        self.send({**payload,'contractor_document_number':'87654321'},expected=409)
        self.send({**payload,'external_source':'other'},expected=403)
        self.send({**payload,'external_reference':'another','external_emitter_id':101},expected=422)
        self.assertEqual(self.client.get(API+'/plans').status_code,401)
        self.assertEqual(self.client.get(medical.API+'/emissions',headers=self.connector_headers).status_code,401)
        with self.sessions() as db:
            self.assertEqual(db.query(MedicalIssuance).count(),1)
        ident=first['data']['id']
        result=self.client.get(API+f'/emissions/{ident}/letter',headers=self.connector_headers)
        self.assertEqual(result.status_code,200)
        self.assertTrue(result.content.startswith(b'%PDF'))

    def test_validate_rolls_back_and_bad_document_is_422(self):
        payload=self.setup_connector()
        with self.sessions() as db: before=db.get(MedicalPlan,self.plan_id).counter
        self.assertTrue(self.send(payload,'/emissions/validate')['validated_only'])
        with self.sessions() as db:
            self.assertEqual(db.query(MedicalIssuance).count(),0)
            self.assertEqual(db.get(MedicalPlan,self.plan_id).counter,before)
        self.send({**payload,'contractor_document_number':'123456'},expected=422)

    def test_fiscal_choice_is_reserved_once_and_files_are_scoped(self):
        from test_fiscal import config,certificate,cdr
        from app.models.legacy import MedicalBillingConfiguration
        from app.models.medical import MedicalInvoice
        from app.services import medical_billing as fiscal,sunat
        from app.utils.secrets import encrypt_secret
        import json,tempfile
        from pathlib import Path
        payload=self.setup_connector()
        raw=config();raw.update(v2_invoice_series='FV02',v2_invoice_counter=0)
        with self.sessions() as db:
            db.add(MedicalBillingConfiguration(payload_encrypted=encrypt_secret(json.dumps(raw))));db.commit()
        preference=dict(invoice_type_code='01',customer_document_type='RUC',customer_document_number='20100066603',customer_name='EMPRESA',customer_address='CALLE 123',customer_ubigeo='150101')
        payload['billing']=preference
        emission=self.send(payload)['data']
        self.send({**payload,'billing':{'invoice_type_code':'03'}},expected=409)
        invoice=self.send(preference,f'/billing/from-issuance/{emission["id"]}')['data']
        self.assertEqual(invoice['invoice_type_code'],'01')
        self.assertEqual(invoice['full_number'],'FV02-1')
        self.send({'invoice_type_code':'03'},f'/billing/from-issuance/{emission["id"]}',409)
        with tempfile.TemporaryDirectory() as directory,patch.object(fiscal,'STORAGE',Path(directory)),patch.object(fiscal,'validate_configuration',return_value=certificate()),patch.object(sunat,'send_bill',return_value=cdr('FV02-1')) as send:
            self.send({},f'/billing/{invoice["id"]}/generate')
            self.assertEqual(send.call_count,0)
            self.send({},f'/billing/{invoice["id"]}/send-sunat')
            self.send({},f'/billing/{invoice["id"]}/send-sunat')
            self.assertEqual(send.call_count,1)
            result=self.client.get(API+f'/billing/{invoice["id"]}/file/PDF',headers=self.connector_headers)
            self.assertEqual(result.status_code,200,result.text[:100])
            self.assertTrue(result.content.startswith(b'%PDF'))
        with self.sessions() as db:self.assertEqual(db.query(MedicalInvoice).count(),1)
        self.assertEqual(self.client.get(API+'/billing/departments',headers=self.connector_headers).status_code,200)

    def test_portal_and_connector_share_overlap_guard(self):
        payload=self.setup_connector()
        first=self.issuance()
        self.send(payload,expected=409)
        self.send({**payload,'starts_at':(medical.datetime.fromisoformat(first['ends_on']).date()+timedelta(days=1)).isoformat()})
        with self.sessions() as db:self.assertEqual(db.query(MedicalIssuance).count(),2)

    def test_emitter_commission_and_sync_do_not_grant_portal_access(self):
        payload=self.setup_connector()
        source={'external_key':'externa_alp','code':'ALP','name':'La Primera'}
        users=[{'external_user_id':100,'name':'Oficina','role':3,'active':True},
               {'external_user_id':101,'name':'Vendedor','role':4,'active':True,'responsible_external_user_id':100,'commission_esencial':'7.00'}]
        self.send({'source':source,'users':users},'/external-users/sync')
        first=self.send({**payload,'external_emitter_id':101})
        self.assertEqual(first['data']['seller_commission_amount'],'7.00')
        with self.sessions() as db:
            em=db.query(MedicalProfile).filter_by(external_user_id='101').one()
            self.assertIsNone(em.user_id)
        self.send({'source':{**source,'external_key':'other'},'users':users},'/external-users/sync',403)
        self.send({'source':source,'users':[{**users[1],'role':3}]},'/external-users/sync',409)
        listed=self.client.get(API+'/emissions',headers=self.connector_headers).json()
        self.assertEqual(listed['total'],1)
        period={'period_start':first['data']['sale_date'],'period_end':first['data']['sale_date']}
        result=self.client.get(API+'/liquidations/pending-issuances',params=period,headers=self.connector_headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['data']['items'][0]['deposit'],'12.00')

    def test_other_source_cannot_read_emission(self):
        payload=self.setup_connector()
        first=self.send(payload)
        other=secrets.token_urlsafe(48)
        with self.sessions() as db:
            source=MedicalSource(code='OTHER',name='Other',kind='afocat',external_key='other',active=True)
            db.add(source);db.flush()
            db.add(MedicalIntegrationCredential(source_id=source.id,actor_id=self.admin_id,token_hash=hashlib.sha256(other.encode()).hexdigest(),active=True))
            db.commit()
        headers={'Authorization':'Bearer '+other}
        self.assertEqual(self.client.get(API+f'/emissions/{first["data"]["id"]}',headers=headers).status_code,404)
        self.assertEqual(self.client.get(API+'/emissions',headers=headers).json()['total'],0)

    def test_external_sends_require_explicit_retry(self):
        payload=self.setup_connector()
        ident=self.send(payload)['data']['id']
        delivery={'email':True,'recipient_email':'test@example.com'}
        with patch('app.routes.medical.send_email') as send:
            self.send(delivery,f'/emissions/{ident}/resend')
            self.send(delivery,f'/emissions/{ident}/resend',409)
            self.assertEqual(send.call_count,1)
            self.send({**delivery,'force':True},f'/emissions/{ident}/resend')
            self.assertEqual(send.call_count,2)
