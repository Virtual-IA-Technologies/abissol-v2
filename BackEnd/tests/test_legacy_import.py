"""Migración probada con datos sintéticos; nunca necesita Laravel ni SUNAT."""
import json
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import test_platform as platform
from app.models import Usuario, AccessGrant, Menu
from app.models.medical import MedicalInvoice, MedicalIssuance, MedicalProfile, MedicalPlan
from app.models.legacy import LegacyRecord
from app.routes.auth import hash_password, verify_password
from app.services.legacy_import import Importer, ImportFailure

API = platform.API + '/medical'


def row(fields, **values):
    return dict.fromkeys(fields.split()) | values


class LegacyImportTests(unittest.TestCase):
    setUp = platform.PlatformTests.setUp
    cleanup = platform.PlatformTests.cleanup
    login = platform.PlatformTests.login

    def fixture(self):
        now = datetime(2026, 9, 1)
        password = hash_password(self.password).replace('$2b$', '$2y$', 1)
        users = [dict(id=10, name='Administrador anterior', username='previous-admin', email='admin@example.com', phone='999999999', password=password, created_at=now, medical_source_id=1),
                 dict(id=20, name='Persona con nombre completo que supera cincuenta caracteres para conservar', username='seller-fixture', email='seller@example.com', phone='999999999', password=password, created_at=now, medical_source_id=1)]
        issuance = row('contractor_paternal_last_name contractor_maternal_last_name contractor_last_name contractor_email contractor_phone cancellation_reason external_source external_reference deleted_at welcome_letter_path',
            id=5, plan_id=1, source_id=1, seller_id=7, seller_user_id=20, emitter_seller_id=7, emitter_user_id=20,
            status='pending_payment', internal_code='A-000007', public_token='x'*48, contractor_name='Titular sintético',
            contractor_document_type='DNI', contractor_document_number='12345678', sale_date=now, starts_at=now, ends_at=now,
            sale_price='55.00', provider_cost='12.00', seller_commission_amount='15.00', platform_commission_amount='0.50',
            payment_status='collected_by_seller', payment_method='cash', paid_amount='55.00', created_by=10, created_at=now)
        invoices = [row('deleted_at pdf_a4_path pdf_ticket_path xml_path zip_path cdr_path', id=i, medical_issuance_id=5,
                       invoice_type=kind, full_number=number, issue_date=now, customer_name='Titular sintético', customer_document_number='12345678',
                       total='55.00', internal_status='sent', sunat_status='accepted', payment_status='paid', created_by=10, created_at=now)
                    for i, kind, number in [(1, 'Boleta', 'B001-1'), (2, 'Nota de crédito', 'BC01-1')]]
        return dict(users=users, roles=[dict(id=1,name='seller')], model_has_roles=[dict(role_id=1,model_id=20,model_type='App\\Models\\User')],
            medical_sources=[dict(id=1,code='ABISSOL',name='ABISSOL',source_type='internal',external_key=None,status='active',deleted_at=None)],
            medical_plans=[dict(id=1,code='HAMPI_ESENCIAL',name='Hampi Esencial',series_prefix='A',current_number=7,sale_price='55',provider_cost='12',platform_fee='0.00',platform_commission='0.50',meta_commission_percent='10',validity_days=365,is_active=True,deleted_at=None)],
            medical_settings=[dict(id=1,key='medical.default_seller_commission_hampi_esencial_amount',value='15')],
            medical_sellers=[dict(id=7,user_id=20,source_id=1,responsible_seller_id=None,source_role='both',status='active',deleted_at=None,external_user_id=None)],
            medical_issuances=[issuance], medical_liquidations=[], medical_liquidation_items=[], medical_liquidation_vouchers=[],
            billing_invoices=invoices,billing_invoice_items=[],documents=[],medical_dispatches=[],billing_invoice_series=[],
            billing_invoice_settings=[dict(id=1, company_name='Emisor sintético', sol_user='private-user',sol_password='private-password',certificate_password='private-cert-password')])

    def test_accounts_money_idempotence_and_source_change_guard(self):
        data = self.fixture()
        with TemporaryDirectory() as directory, self.sessions() as db:
            admin = db.query(Usuario).filter_by(username='admin').one()
            original_hash = admin.contrasena
            result = Importer(db, data, directory, directory, admin.id).run()
            db.commit()
            seller = db.query(Usuario).filter_by(username='seller-fixture').one()
            self.assertTrue(verify_password(self.password, seller.contrasena))
            self.assertEqual(admin.contrasena, original_hash)
            self.assertIsNone(seller.telefono)
            self.assertEqual(seller.legacy_contact_phone, '999999999')
            self.assertGreater(len(seller.nombre), 50)
            emission = db.query(MedicalIssuance).one()
            self.assertEqual((emission.status, emission.legacy_status, emission.price, emission.paid_amount), ('issued','pending_payment',Decimal('55'),Decimal('55')))
            self.assertEqual(db.query(MedicalInvoice).count(), 2)
            self.assertEqual({r.sunat_status for r in db.query(MedicalInvoice)}, {'accepted'})
            self.assertEqual(result['linked_existing_users'], 1)
            profile = db.query(MedicalProfile).filter_by(user_id=seller.id).one()
            profile.display_name = 'Nombre actualizado en V2'
            db.commit()
            second = Importer(db, data, directory, directory, admin.id).run()
            self.assertEqual(second['new_records'], 0)
            self.assertEqual(db.query(MedicalInvoice).count(), 2)
            self.assertEqual(profile.display_name, 'Nombre actualizado en V2')
            from app.bootstrap import seed_platform
            seed_platform(db)
            self.assertEqual(db.query(MedicalPlan).count(), 2)  # Esencial importado + Plus base
            raw = db.query(LegacyRecord).filter_by(source_table='users',source_key='20').one()
            self.assertNotIn('seller@example.com', raw.payload_encrypted)
            db.commit()
            data['medical_issuances'][0]['sale_price'] = '999.00'
            with self.assertRaises(ImportFailure):
                Importer(db, data, directory, directory, admin.id).run()
            db.rollback()
            self.assertEqual(db.query(MedicalIssuance).one().price, Decimal('55'))

    def test_historical_fiscal_access_and_secret_redaction(self):
        with TemporaryDirectory() as directory, self.sessions() as db:
            admin = db.query(Usuario).filter_by(username='admin').one()
            Importer(db, self.fixture(), directory, directory, admin.id).run()
            reader = db.query(Usuario).filter_by(username='reader').one()
            for slug in ('medical-billing', 'medical-emissions'):
                menu = db.query(Menu).filter_by(slug=slug).one()
                db.add(AccessGrant(usuario_id=reader.id,menu_id=menu.id,access_level='gestor'))
            db.commit()
        _, headers = self.login()
        plan = next(p for p in self.client.get(API+'/plans',headers=headers).json()['items'] if p['code']=='HAMPI_ESENCIAL')
        from app.schemas.medical import PlanInput
        fields = PlanInput.model_fields.keys()
        result = self.client.put(API+f'/plans/{plan["id"]}',headers=headers,json={k:v for k,v in plan.items() if k in fields})
        self.assertEqual(result.status_code,200,result.text)
        config = self.client.get(API+'/billing/configuration',headers=headers)
        self.assertEqual(config.status_code,200)
        self.assertFalse(config.json()['enabled'])
        self.assertNotIn('private-password',config.text)
        self.assertNotIn('private-user',config.text)
        invoice = self.client.get(API+'/billing',headers=headers).json()['items'][0]
        self.assertEqual(self.client.get(API+f'/billing/{invoice["id"]}/detail',headers=headers).status_code,200)
        self.assertEqual(self.client.post(API+'/billing',headers=headers,json=dict(issuance_id=invoice['issuance_id'],document_type='boleta',customer='Test',document_number='12345678')).status_code,409)
        public = self.client.get(API+'/validate/'+'x'*48)
        self.assertEqual(public.status_code,200)
        self.assertNotIn('customer',public.json())
        _, limited = self.login('reader')
        self.assertEqual(self.client.get(API+'/billing',headers=limited).json()['total'],0)
        self.assertEqual(self.client.get(API+'/billing/configuration',headers=limited).status_code,403)
        self.assertEqual(self.client.get(API+f'/billing/{invoice["id"]}/detail',headers=limited).status_code,404)

    def test_files_stay_private_and_cannot_escape_source_storage(self):
        with TemporaryDirectory() as directory, self.sessions() as db:
            root = Path(directory)
            source = root/'source'
            allowed = source/'storage/app/public'
            allowed.mkdir(parents=True)
            (allowed/'original.pdf').write_bytes(b'%PDF-test')
            (root/'outside.txt').write_text('not-importable')
            importer = Importer(db, {}, source, root/'destination', 1, copy_files=True)
            self.assertIsNone(importer.copy(str(root/'outside.txt')))
            self.assertIsNone(importer.copy('../../../../outside.txt'))
            file = importer.copy('original.pdf')
            self.assertEqual(file.size,9)
            self.assertEqual((root/'destination/legacy_abissol'/file.storage_key).read_bytes(), b'%PDF-test')
