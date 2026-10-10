import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from decimal import Decimal
from datetime import date
from types import SimpleNamespace
import pymupdf
import test_medical as medical
from app.models.medical import MedicalIssuance,MedicalInvoice,MedicalDispatch
from app.services import medical_rendering as render,medical_documents as archive,medical_billing as fiscal

API=medical.API
class InformationTests(unittest.TestCase):
    setUp=medical.MedicalTests.setUp
    cleanup=medical.MedicalTests.cleanup
    login=medical.MedicalTests.login
    prepare=medical.MedicalTests.prepare
    post=medical.MedicalTests.post
    issuance=medical.MedicalTests.issuance

    def test_same_archived_letter_qr_public_page_and_email_attachments(self):
        self.prepare();sale=self.issuance()
        with self.sessions() as db:
            archive.archive(db,source='plan',ident=self.plan_id,key='conditions',actor=self.admin_id,path=[('abissol','ABISSOL'),('abissol:plan','Planes')],filename='condiciones.pdf',content=b'%PDF-1.7 condiciones de prueba');db.commit()
        path='/validate/'+sale['token']
        html=self.client.get(API+path,headers={'accept':'text/html'})
        self.assertEqual(html.status_code,200);self.assertIn('Vigencia por iniciar',html.text);self.assertIn('12****78',html.text)
        self.assertIn('Descargar carta de bienvenida',html.text)
        self.assertEqual(self.client.get(API+'/validate/assets/abissol-logo.png').status_code,200)
        self.assertEqual(self.client.get(API+'/validate/assets/secret.png').status_code,404)
        private=self.client.get(API+f'/emissions/{sale["id"]}/letter',headers=self.headers)
        public=self.client.get(API+path+'/letter');self.assertEqual(private.content,public.content)
        with pymupdf.open(stream=public.content,filetype='pdf') as pdf:
            text=''.join(p.get_text() for p in pdf)
            self.assertIn('CARTA DE BIENVENIDA',text.upper());self.assertIn('META ASSISTANCE',text);self.assertIn('https://abissol.org/?consulta=',text.replace('\n',''))
        with patch('app.routes.medical.send_email') as send:
            result=self.post('/dispatches',{'issuance_id':sale['id'],'channel':'email'})
            self.assertEqual(result['status'],'sent')
            attachments=send.call_args.kwargs['attachments']
            self.assertEqual(attachments[0][1],public.content);self.assertEqual(len(attachments),2)
            self.assertIn('Resumen de membresía',send.call_args.kwargs['html'])
            self.assertNotIn("' .",send.call_args.kwargs['html'])
        with self.sessions() as db:db.get(MedicalIssuance,sale['id']).status='cancelled';db.commit()
        self.assertEqual(self.client.get(API+path+'/letter').status_code,409)
        self.assertIn('Programa anulado',self.client.get(API+path,headers={'accept':'text/html'}).text)
        self.assertEqual(self.client.get(API+'/validate/invalid/letter').status_code,404)

    def test_a4_ticket_same_tax_qr_and_credit_details(self):
        self.prepare()
        invoice=SimpleNamespace(customer='PRUEBA & COMPAÑÍA',document_number='20100070970',document_type='factura',full_number='FV99-1',issue_date=date(2026,10,7),total=Decimal('255'),details={'issuer':{'ruc':'20100070970','company_name':'EMISOR DE PRUEBA','address':'DIRECCIÓN DE PRUEBA'},'environment':'beta','customer_document_type':'RUC','customer_address':'DIRECCIÓN CLIENTE','customer_ubigeo':'150101','payment_terms':'Credito','due_date':'2026-11-07','items':[{'description':'Hampi Plus','total':'199'},{'description':'Admisión','total':'43'},{'description':'Mantenimiento','total':'13'}]})
        with patch('app.services.medical_rendering.qrcode.make',wraps=render.qrcode.make) as qr:
            for ticket in [False,True]:
                pdf=render.invoice(invoice,'DIGEST-TEST',ticket)
                with pymupdf.open(stream=pdf,filetype='pdf') as doc:
                    self.assertEqual(len(doc),1)
                    self.assertAlmostEqual(doc[0].rect.width,226.77 if ticket else 595.28,places=1)
                    text=''.join(p.get_text() for p in doc)
                    for term in ['FV99-1','255.00','DIGEST-TEST','2026-11-07','BETA']:self.assertIn(term,text)
                    self.assertTrue(doc[0].get_images())
            self.assertEqual(qr.call_args.args[0],'20100070970|01|FV99|1|0.00|255.00|2026-10-07|6|20100070970|DIGEST-TEST')

    def test_invoice_email_original_files_reservation_and_scope(self):
        self.prepare();sale=self.issuance()
        with TemporaryDirectory() as tmp,patch('app.services.medical_billing.STORAGE',Path(tmp)):
            with self.sessions() as db:
                invoice=MedicalInvoice(issuance_id=sale['id'],document_type='boleta',customer='Prueba',document_number='12345678',total=55,created_by=self.admin_id,full_number='BV02-TEST',status='issued',details={'environment':'production'})
                db.add(invoice);db.flush();ident=invoice.id
                invoice.details={'environment':'production','files':{kind:fiscal.write_artifact(invoice,kind,content) for kind,content in [('PDF',b'%PDF-1.7 original'),('XML',b'<Invoice/>')]}};db.commit()
            payload={'recipient':'test@example.com','files':['PDF','XML']}
            with patch('app.routes.medical.send_email') as send:
                self.post(f'/billing/{ident}/send-client',payload)
                self.assertEqual(send.call_count,1)
                self.assertEqual(send.call_args.kwargs['attachments'][0][1],b'%PDF-1.7 original')
                history=self.client.get(API+'/dispatches',headers=self.headers)
                self.assertEqual(history.status_code,200)
                self.assertEqual(history.json()['items'][0]['invoice_number'],'BV02-TEST')
                self.post(f'/billing/{ident}/send-client',payload,409)
                self.assertEqual(send.call_count,1)
            with patch('app.routes.medical.send_email',side_effect=TimeoutError):
                uncertain=self.post(f'/billing/{ident}/send-client',{**payload,'force':True});self.assertEqual(uncertain['status'],'uncertain')
            with self.sessions() as db:
                self.assertEqual(db.query(MedicalInvoice).count(),1)
                self.assertEqual(db.query(MedicalDispatch).filter_by(invoice_id=ident).count(),2)
            _,reader=self.login('reader')
            self.post(f'/billing/{ident}/send-client',payload,403,reader)
