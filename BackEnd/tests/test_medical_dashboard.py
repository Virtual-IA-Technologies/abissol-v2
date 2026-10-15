import unittest
from datetime import timedelta
from decimal import Decimal
import test_medical as medical
from app.models import Usuario, AccessGrant, Menu
from app.models.medical import MedicalProfile, MedicalIssuance, MedicalLiquidation, MedicalLiquidationItem, MedicalVoucher
from app.services.commercial_roles import seed_commercial_roles


class DashboardTests(unittest.TestCase):
    setUp = medical.MedicalTests.setUp
    cleanup = medical.MedicalTests.cleanup
    login = medical.MedicalTests.login
    prepare = medical.MedicalTests.prepare
    post = medical.MedicalTests.post
    issuance = medical.MedicalTests.issuance

    def test_scope_history_test_exclusion_and_permissions(self):
        self.prepare()
        with self.sessions() as db:
            roles = seed_commercial_roles(db)
            child_user = db.get(Usuario, self.reader_id)
            child_user.roles.append(roles['emitter'])
            child = MedicalProfile(user_id=self.reader_id, source_id=self.source_id, kind='emitter', manager_id=self.profile_id, display_name='Sucursal', active=True)
            db.add(child); db.commit(); child_id = child.id
        parent = self.issuance()
        own = self.issuance(emitter_id=child_id, document_number='87654321')
        with self.sessions() as db:
            e = db.get(MedicalIssuance, own['id'])
            liq = MedicalLiquidation(kind='seller',responsible_id=self.profile_id,legacy_id=999,code='LEGACY-999',starts_on=e.sale_date,ends_on=e.sale_date,status='pending',sales_total=55,commission_total=15,deposit_required=55,created_by=self.admin_id)
            db.add(liq);db.flush()
            db.add(MedicalLiquidationItem(liquidation_id=liq.id,issuance_id=e.id,active_key=f'seller:{e.id}',sale=55,commission=15,deposit=55))
            db.add(MedicalVoucher(liquidation_id=liq.id,reference='original',amount=55,paid_on=e.sale_date,filename='voucher.jpg',storage_key='fixture',digest='a'*64,active=True))
            # An old sale is excluded from the period, but remains a pending deposit.
            db.get(MedicalIssuance,parent['id']).sale_date=e.sale_date-timedelta(days=100)
            db.commit()
        _, headers = self.login('reader')
        response = self.client.get(medical.API+'/dashboard',headers=headers)
        self.assertEqual(response.status_code,200,response.text)
        data=response.json()
        self.assertEqual(data['emissions']['count'],1)
        self.assertEqual(Decimal(data['emissions']['sales']),55)
        self.assertEqual(data['emissions']['pending_count'],0)
        self.assertEqual(data['liquidations']['review']['count'],1)
        self.assertEqual(data['liquidations']['paid']['count'],0)
        admin=self.client.get(medical.API+'/dashboard',headers=self.headers).json()
        self.assertEqual(admin['emissions']['count'],1)
        self.assertEqual(admin['emissions']['pending_count'],1)
        with self.sessions() as db:
            db.get(MedicalIssuance,own['id']).test_batch='TEST'
            for slug in ['medical-emissions','medical-liquidations']:
                menu=db.query(Menu).filter_by(slug=slug).one()
                db.add(AccessGrant(usuario_id=self.reader_id,menu_id=menu.id,access_level='none'))
            db.commit()
        admin=self.client.get(medical.API+'/dashboard',headers=self.headers).json()
        self.assertEqual(admin['emissions']['count'],0)
        hidden=self.client.get(medical.API+'/dashboard',headers=headers).json()
        self.assertIsNone(hidden['emissions']);self.assertIsNone(hidden['liquidations'])
        self.assertEqual(self.client.get(medical.API+'/dashboard?months=13',headers=self.headers).status_code,422)
        self.assertEqual(self.client.get(medical.API+'/dashboard').status_code,401)
