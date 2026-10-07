import base64
import copy
import hashlib
import io
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from lxml import etree as E
import test_medical as medical
from app.models import Usuario, Rol, AccessGrant, Menu
from app.models.legacy import MedicalBillingConfiguration
from app.models.fiscal import FiscalJob
from app.models.medical import MedicalInvoice, MedicalIssuance
from app.services import sunat, medical_billing as billing
from app.utils.secrets import encrypt_secret
from app.utils.time import utc_now
import json


def certificate():
    key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'TEST 20100066603')])
    cert = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1).not_valid_before(datetime.now(timezone.utc)-timedelta(days=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=1)).sign(key,hashes.SHA256())
    return key,cert


def config():
    return dict(enabled_in_v2=True,environment='beta',provider='sunat_soap',v2_series='BV02',v2_counter=0,ruc='20100066603',company_name='EMISOR DE PRUEBA',trade_name='PRUEBA',address='DIRECCION DE PRUEBA',ubigeo='150101',department='LIMA',province='LIMA',district='LIMA',sol_user='MODDATOS',sol_password='moddatos',series=[])


def cdr(number, code='0',ruc='20100066603'):
    xml=f'''<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2" xmlns:cac="{sunat.NS['cac']}" xmlns:cbc="{sunat.NS['cbc']}"><cac:ReceiverParty><cac:PartyIdentification><cbc:ID>{ruc}</cbc:ID></cac:PartyIdentification></cac:ReceiverParty><cac:DocumentResponse><cac:Response><cbc:ResponseCode>{code}</cbc:ResponseCode><cbc:Description>Resultado de prueba</cbc:Description></cac:Response><cac:DocumentReference><cbc:ID>{number}</cbc:ID></cac:DocumentReference></cac:DocumentResponse></ApplicationResponse>'''
    return sunat.package_xml('R-'+number,xml.encode())


class SunatContractTests(unittest.TestCase):
    def test_distribution_signature_zip_and_cdr(self):
        key, cert = certificate()
        for plan,total,count in [('Hampi Esencial',55,2),('Hampi Plus',255,3)]:
            items=sunat.plan_items(plan,total)
            self.assertEqual(len(items),count)
            self.assertEqual(sum(Decimal(i['total']) for i in items),Decimal(total))
            self.assertTrue(all(i['affectation_igv_type']=='30' and i['tax_amount']=='0.00' for i in items))
            invoice=SimpleNamespace(full_number='BV02-1',issue_date=utc_now().date(),total=Decimal(total),document_number='12345678',customer='PRUEBA & COMPAÑÍA',details={'customer_document_type':'DNI'})
            root=sunat.build_invoice(config(),invoice,items)
            xml,digest=sunat.sign_xml(root,key,cert)
            parsed=sunat.parse_xml(xml)
            signature=parsed.find('.//{'+sunat.DS+'}Signature')
            signed_info=signature.find('{'+sunat.DS+'}SignedInfo')
            value=base64.b64decode(signature.findtext('{'+sunat.DS+'}SignatureValue'))
            cert.public_key().verify(value,E.tostring(signed_info,method='c14n'),padding.PKCS1v15(),hashes.SHA1())
            signature.getparent().remove(signature)
            self.assertEqual(digest,base64.b64encode(hashlib.sha1(E.tostring(parsed,method='c14n')).digest()).decode())
            with zipfile.ZipFile(io.BytesIO(sunat.package_xml('20100066603-03-BV02-1',xml))) as archive:
                self.assertEqual(archive.namelist(),['20100066603-03-BV02-1.xml'])
            self.assertEqual(sunat.cdr_result(cdr('BV02-1'),'BV02-1','20100066603')['status'],'accepted')
            self.assertEqual(sunat.cdr_result(cdr('BV02-1','2335'),'BV02-1','20100066603')['status'],'rejected')
        with self.assertRaises(sunat.FiscalError):sunat.plan_items('Hampi Esencial',56)
        with self.assertRaises(sunat.FiscalError):sunat.plan_items('Sin distribución',55)
        with self.assertRaises(sunat.FiscalError):sunat.cdr_result(cdr('BV02-2'),'BV02-1','20100066603')
        with self.assertRaises(sunat.FiscalError):sunat.cdr_result(cdr('BV02-1'),'BV02-1','99999999999')
        with self.assertRaises(sunat.FiscalError):sunat.parse_xml(b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]><x>&a;</x>')


class FiscalFlowTests(unittest.TestCase):
    setUp=medical.MedicalTests.setUp
    cleanup=medical.MedicalTests.cleanup
    login=medical.MedicalTests.login
    prepare=medical.MedicalTests.prepare
    post=medical.MedicalTests.post
    issuance=medical.MedicalTests.issuance

    def enable(self):
        self.prepare()
        with self.sessions() as db:
            db.add(MedicalBillingConfiguration(payload_encrypted=encrypt_secret(json.dumps(config()))))
            db.commit()

    def test_only_programmer_can_read_write_configuration(self):
        self.enable()
        _,headers=self.login('reader')
        with self.sessions() as db:
            reader=db.get(Usuario,self.reader_id)
            reader.roles=[db.query(Rol).filter_by(nombre='Administrador').one()]
            menu=db.query(Menu).filter_by(slug='medical-billing').one()
            db.add(AccessGrant(usuario_id=reader.id,menu_id=menu.id,access_level='gestor'))
            db.commit()
        path=medical.API+'/billing/configuration'
        self.assertEqual(self.client.get(path,headers=headers).status_code,403)
        data={k:v for k,v in config().items() if k in ('environment','v2_series','company_name','trade_name','ruc','address','ubigeo','department','province','district')}
        data['enabled']=False
        self.assertEqual(self.client.put(path,headers=headers,json=data).status_code,403)
        response=self.client.get(path,headers=self.headers)
        self.assertEqual(response.status_code,200)
        self.assertNotIn('sol_password',response.json())
        self.assertNotIn('certificate_password',response.json())

    def test_payment_creates_one_job_and_rejects_distribution_mismatch(self):
        self.enable()
        emission=self.issuance(payment_status='pending')
        with self.sessions() as db:
            self.assertEqual(db.query(FiscalJob).count(),1)
            self.assertEqual(db.query(MedicalInvoice).one().payment_status,"pending")
        self.post(f'/emissions/{emission["id"]}/payment',{'payment_status':'collected_by_seller','reference':'PRUEBA'})
        with self.sessions() as db:
            row=db.get(MedicalIssuance,emission['id'])
            billing.enqueue_boleta(db,row)
            db.commit()
            self.assertEqual(db.query(FiscalJob).count(),1)
            invoice=db.query(MedicalInvoice).one()
            self.assertEqual(invoice.full_number,'BV02-1')
            self.assertEqual(invoice.total,Decimal('55'))
        self.issuance(document_number='87654321')
        with self.sessions() as db:self.assertEqual([j.number for j in db.query(FiscalJob).order_by(FiscalJob.id)],[1,2])

    def test_mismatched_price_rolls_back_sale_and_counter(self):
        self.enable()
        from app.models.medical import MedicalPlan
        with self.sessions() as db:
            db.get(MedicalPlan,self.plan_id).price=Decimal('56')
            db.commit()
        self.post('/emissions',dict(plan_id=self.plan_id,emitter_id=self.profile_id,document_type='DNI',document_number='12345678',customer='PRUEBA',starts_on=(utc_now().date()+timedelta(days=2)).isoformat(),payment_status='collected_by_seller',payment_method='cash'),422)
        with self.sessions() as db:
            self.assertEqual(db.query(MedicalIssuance).count(),0)
            self.assertEqual(db.query(FiscalJob).count(),0)
            self.assertEqual(billing.configuration(db)[1]['v2_counter'],0)

    def test_imported_emission_is_not_reissued(self):
        self.enable()
        with self.sessions() as db:
            cfg,raw=billing.configuration(db)
            raw['enabled_in_v2']=False
            billing.persist_config(cfg,raw)
            db.commit()
        emission=self.issuance(payment_status='pending')
        with self.sessions() as db:
            cfg,raw=billing.configuration(db)
            raw['enabled_in_v2']=True
            billing.persist_config(cfg,raw)
            row=db.get(MedicalIssuance,emission['id'])
            row.legacy_id=999
            row.payment_status='collected_by_seller'
            self.assertIsNone(billing.enqueue_boleta(db,row))
            db.commit()
            self.assertEqual(db.query(FiscalJob).count(),0)

    def test_factura_credit_terms_and_independent_series(self):
        self.enable()
        from zoneinfo import ZoneInfo
        due=(datetime.now(ZoneInfo('America/Lima')).date()+timedelta(days=30)).isoformat()
        preference=dict(invoice_type_code='01',customer_document_type='RUC',customer_document_number='20100066603',customer_name='EMPRESA DE PRUEBA',customer_address='CALLE DE PRUEBA 123',customer_ubigeo='150101',due_date=due)
        with self.sessions() as db:
            cfg,raw=billing.configuration(db)
            raw.update(v2_invoice_series='FV02',v2_invoice_counter=0)
            billing.persist_config(cfg,raw)
            db.commit()
        self.issuance(billing=preference,payment_status='pending')
        self.issuance(document_number='87654321')
        with tempfile.TemporaryDirectory() as directory, patch.object(billing,'STORAGE',Path(directory)), patch.object(billing,'validate_configuration',return_value=certificate()), patch.object(sunat,'send_bill',return_value=cdr('FV02-1')) as send:
            with self.sessions() as db:
                invoice=db.query(MedicalInvoice).filter_by(document_type='factura').one()
                self.assertEqual(invoice.full_number,'FV02-1')
                self.assertEqual(db.query(MedicalInvoice).filter_by(document_type='boleta').one().full_number,'BV02-1')
                job=db.query(FiscalJob).filter_by(invoice_id=invoice.id).one()
                billing.process_job(db,job.id)
                self.assertEqual(job.state,'accepted',job.error)
                self.assertEqual(send.call_args.args[1],'20100066603-01-FV02-1')
                xml=sunat.parse_xml(billing.artifact_path(invoice,'XML').read_bytes())
                self.assertEqual(xml.findtext('cbc:InvoiceTypeCode',namespaces=sunat.NS),'01')
                terms=xml.findall('cac:PaymentTerms',sunat.NS)
                self.assertEqual([p.findtext('cbc:PaymentMeansID',namespaces=sunat.NS) for p in terms],['Credito','Cuota001'])
                self.assertEqual(terms[1].findtext('cbc:PaymentDueDate',namespaces=sunat.NS),due)
                self.assertTrue(billing.artifact_path(invoice,'PDF').read_bytes().startswith(b'%PDF'))
                billing.process_job(db,job.id)
                self.assertEqual(send.call_count,1)

    def test_factura_requires_due_date_before_reserving_number(self):
        self.enable()
        payload=dict(plan_id=self.plan_id,emitter_id=self.profile_id,document_type='DNI',document_number='12345678',customer='PRUEBA',starts_on=(utc_now().date()+timedelta(days=2)).isoformat(),payment_status='pending',payment_method='cash',billing=dict(invoice_type_code='01',customer_document_type='RUC',customer_document_number='20100066603',customer_name='EMPRESA',customer_address='CALLE 123',customer_ubigeo='150101'))
        self.post('/emissions',payload,422)
        with self.sessions() as db:
            self.assertEqual(db.query(MedicalIssuance).count(),0)
            self.assertEqual(db.query(FiscalJob).count(),0)

    def test_timeout_recovers_cdr_without_resending_or_renumbering(self):
        self.enable()
        self.issuance()
        with tempfile.TemporaryDirectory() as directory, patch.object(billing,'STORAGE',Path(directory)), patch.object(billing,'validate_configuration',return_value=certificate()), patch.object(sunat,'send_bill',side_effect=TimeoutError('private detail')) as send:
            with self.sessions() as db:
                job=db.query(FiscalJob).one()
                ident=job.id
                billing.process_job(db,ident)
                self.assertEqual(job.state,'uncertain')
                self.assertNotIn('private detail',job.error)
                job.next_attempt_at=utc_now()-timedelta(seconds=1)
                db.commit()
                invoice=db.get(MedicalInvoice,job.invoice_id)
                xml=billing.artifact_path(invoice,'XML').read_bytes()
            with patch.object(sunat,'query_cdr',return_value=cdr('BV02-1')):
                with self.sessions() as db:
                    billing.process_job(db,ident)
                    job=db.get(FiscalJob,ident)
                    self.assertEqual(job.state,'accepted')
                    invoice=db.get(MedicalInvoice,job.invoice_id)
                    self.assertEqual(billing.artifact_path(invoice,'XML').read_bytes(),xml)
                    self.assertIn('CDR',invoice.details['files'])
                    billing.process_job(db,ident)
            self.assertEqual(send.call_count,1)

    def test_rejected_cdr_never_becomes_accepted(self):
        self.enable()
        self.issuance()
        with tempfile.TemporaryDirectory() as directory, patch.object(billing,'STORAGE',Path(directory)), patch.object(billing,'validate_configuration',return_value=certificate()), patch.object(sunat,'send_bill',return_value=cdr('BV02-1','2335')):
            with self.sessions() as db:
                job=db.query(FiscalJob).one()
                billing.process_job(db,job.id)
                self.assertEqual(job.state,'rejected')
                self.assertEqual(db.get(MedicalInvoice,job.invoice_id).sunat_status,'rejected')

    def test_queue_can_cross_midnight_without_redating(self):
        self.enable()
        from zoneinfo import ZoneInfo
        today=datetime.now(ZoneInfo('America/Lima')).date()
        with tempfile.TemporaryDirectory() as directory, patch.object(billing,'STORAGE',Path(directory)), patch.object(billing,'validate_configuration',return_value=certificate()):
            for days,expected in [(1,'accepted'),(2,'blocked')]:
                self.issuance(document_number=f'1234567{days}')
                with self.sessions() as db:
                    job=db.query(FiscalJob).order_by(FiscalJob.id.desc()).first()
                    invoice=db.get(MedicalInvoice,job.invoice_id)
                    original=today-timedelta(days=days)
                    invoice.issue_date=original
                    db.commit()
                    with patch.object(sunat,'send_bill',return_value=cdr(invoice.full_number)) as send:
                        billing.process_job(db,job.id)
                        self.assertEqual(job.state,expected)
                        self.assertEqual(invoice.issue_date,original)
                        self.assertEqual(send.call_count,1 if days==1 else 0)
