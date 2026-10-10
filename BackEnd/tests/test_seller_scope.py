import unittest
from types import SimpleNamespace
from fastapi import HTTPException
import test_medical as medical
from app.models import Usuario
from app.models.medical import MedicalProfile, MedicalLiquidationItem, MedicalInvoice
from app.services import medical_documents as archive
from app.services.commercial_roles import seed_commercial_roles
from app.routes import medical as m
from app.services.documents import visible

class SellerScopeTests(unittest.TestCase):
    setUp=medical.MedicalTests.setUp
    cleanup=medical.MedicalTests.cleanup
    login=medical.MedicalTests.login
    prepare=medical.MedicalTests.prepare
    post=medical.MedicalTests.post
    issuance=medical.MedicalTests.issuance

    def test_permission_migration_is_idempotent_and_preserves_denials(self):
        import importlib.util
        from pathlib import Path
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from app.models import AccessGrant, Menu
        with self.sessions() as db:
            roles=seed_commercial_roles(db)
            menu=db.query(Menu).filter_by(slug='medical-liquidations').one()
            db.query(AccessGrant).filter_by(role_id=roles['emitter'].id,menu_id=menu.id).delete()
            grant=db.query(AccessGrant).filter_by(role_id=roles['responsible'].id,menu_id=menu.id).one()
            grant.access_level='none'
            emitter_id,responsible_id,menu_id=roles['emitter'].id,roles['responsible'].id,menu.id
            db.commit()
        spec=importlib.util.spec_from_file_location('seller_migration',Path(__file__).parents[1]/'migrations/versions/0016_seller_access.py')
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        with self.engine.begin() as connection:
            migration.op=Operations(MigrationContext.configure(connection))
            migration.upgrade();migration.upgrade()
        with self.sessions() as db:
            self.assertEqual(db.query(AccessGrant).filter_by(role_id=emitter_id,menu_id=menu_id).one().access_level,'editor')
            self.assertEqual(db.query(AccessGrant).filter_by(role_id=responsible_id,menu_id=menu_id).one().access_level,'none')

    def test_dependent_sees_and_settles_only_own_records(self):
        self.prepare()
        with self.sessions() as db:
            roles=seed_commercial_roles(db)
            reader=db.get(Usuario,self.reader_id);reader.roles.append(roles['emitter'])
            child=MedicalProfile(user_id=self.reader_id,source_id=self.source_id,kind='emitter',manager_id=self.profile_id,display_name='Sucursal',active=True)
            db.add(child);db.commit();child_id=child.id
        parent=self.issuance()
        own=self.issuance(emitter_id=child_id,document_number='87654321')
        with self.sessions() as db:
            for sale in [parent,own]:
                invoice=MedicalInvoice(issuance_id=sale['id'],document_type='boleta',customer=sale['customer'],document_number=sale['document_number'],total=55,created_by=self.admin_id,full_number=f"TEST-{sale['id']}")
                db.add(invoice);db.flush()
                document=archive.archive(db,source='invoice',ident=invoice.id,key='PDF',actor=self.admin_id,path=[('test-invoices','Comprobantes')],filename=invoice.full_number+'.pdf',content=b'%PDF-1.7 isolated fixture')
                if sale==parent:foreign_document=document.id
            db.commit()
        _,headers=self.login('reader')
        result=self.client.get(medical.API+'/emissions',headers=headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual([r['id'] for r in result.json()['items']],[own['id']])
        pending=self.client.get(medical.API+'/seller-pending',headers=headers)
        self.assertEqual(pending.status_code,200,pending.text)
        self.assertEqual([r['id'] for r in pending.json()['items']],[own['id']])
        reports=self.client.get(medical.API+'/reports',headers=headers).json()
        self.assertEqual(reports['count'],1);self.assertEqual(reports['unliquidated'],'55.00')
        invoices=self.client.get(medical.API+'/billing',headers=headers).json()
        self.assertEqual([i['issuance_id'] for i in invoices['items']],[own['id']])
        self.assertEqual(self.client.get(f'/abissol/api/v1/documentos/{foreign_document}/archivo/1',headers=headers).status_code,404)
        refs=self.client.get(medical.API+'/lookups?section=liquidations',headers=headers).json()
        self.assertEqual([r['id'] for r in refs['profiles']],[self.profile_id])
        period=dict(kind='seller',responsible_id=self.profile_id,starts_on=own['sale_date'],ends_on=own['sale_date'])
        self.post('/liquidations/preview',{**period,'issuance_ids':[parent['id']]},409,headers)
        liquidation=self.post('/liquidations',{**period,'issuance_ids':[own['id']]},headers=headers)
        self.assertEqual(self.client.get(medical.API+f"/liquidations/{liquidation['id']}",headers=headers).status_code,200)
        other=self.post('/liquidations',{**period,'issuance_ids':[parent['id']]})
        self.assertEqual(self.client.get(medical.API+f"/liquidations/{other['id']}",headers=headers).status_code,404)
        statement=self.client.get(medical.API+'/seller-statements',headers=headers)
        self.assertEqual(statement.status_code,200,statement.text)
        self.assertEqual(statement.json()['items'][0]['sales'],'55.00')
        with self.sessions() as db:
            reader=db.get(Usuario,self.reader_id)
            docs=visible(db,reader).all()
            self.assertEqual(len(docs),2)
            supervisor=SimpleNamespace(id=self.admin_id,active_roles=lambda:[])
            self.assertEqual({r.id for r in m.scope(db,supervisor)}, {parent['id'],own['id']})
            self.assertEqual({r.id for r in m.liquidation_scope(db,supervisor)}, {liquidation['id'],other['id']})
            # A parent voucher mixing own and child sales must never reveal parent data to child.
            db.add(MedicalLiquidationItem(liquidation_id=liquidation['id'],issuance_id=parent['id'],sale=55,commission=0,deposit=55))
            db.commit()
            self.assertEqual(m.liquidation_scope(db,reader).count(),0)
        self.assertEqual(self.client.get(medical.API+f"/emissions/{parent['id']}/letter",headers=headers).status_code,404)
