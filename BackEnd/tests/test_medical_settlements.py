import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from sqlalchemy import event
import test_medical as medical
from app.models.medical import MedicalLiquidation,MedicalVoucher,MedicalProfile
from app.models import AccessGrant,Menu

API=medical.API
class SettlementTests(unittest.TestCase):
    setUp=medical.MedicalTests.setUp
    cleanup=medical.MedicalTests.cleanup
    login=medical.MedicalTests.login
    prepare=medical.MedicalTests.prepare
    post=medical.MedicalTests.post
    issuance=medical.MedicalTests.issuance

    def setup_sale(self):
        self.prepare();sale=self.issuance()
        self.day=sale['sale_date']
        self.liq=self.post('/liquidations',{'kind':'seller','responsible_id':self.profile_id,'starts_on':self.day,'ends_on':self.day})
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup)
        patcher=patch('app.routes.medical.STORAGE',Path(temp.name));patcher.start();self.addCleanup(patcher.stop)

    def voucher(self,amount,reference='OP-001',bank='BCP',purpose='deposit',status=200,headers=None,content=None,**extra):
        response=self.client.post(API+f'/liquidations/{self.liq["id"]}/vouchers',data={'reference':reference,'bank':bank,'account':'123456789','amount':str(amount),'paid_on':self.day,'purpose':purpose,'note':'Sustento de prueba',**extra},files={'file':('deposito.pdf',content or b'%PDF-1.7 '+reference.encode()+bank.encode()+purpose.encode(),'application/pdf')},headers=headers or self.headers)
        self.assertEqual(response.status_code,status,response.text)
        return response.json()

    def action(self,name,status=200):return self.post(f'/liquidations/{self.liq["id"]}/{name}',{'reason':'Revisión de prueba'},status)
    def verify(self,voucher,status=200,headers=None):return self.post(f'/vouchers/{voucher["id"]}/verify',{'reason':'Verificado contra banco'},status,headers)
    def detail(self):return self.client.get(API+f'/liquidations/{self.liq["id"]}',headers=self.headers).json()

    def test_partial_deposits_close_and_later_commission(self):
        self.setup_sale();first=self.voucher(20);self.action('submit');self.action('approve');self.action('pay',422)
        self.verify(first);self.verify(first,409)
        self.assertEqual(Decimal(self.detail()['balance_due']),35)
        second=self.voucher(35,reference='OP-002');self.action('pay',422);self.verify(second);self.action('pay')
        self.assertEqual(self.detail()['commission_state'],'pending')
        self.voucher(1,reference='OP-003',status=409)
        receipt=self.client.get(API+f'/liquidations/{self.liq["id"]}/receipt',headers=self.headers)
        self.assertTrue(receipt.content.startswith(b'%PDF'))
        commission=Decimal(self.liq['commission_total'])
        paid=self.voucher(commission,reference='COM-001',purpose='commission_payment');self.verify(paid)
        self.assertEqual(self.detail()['commission_state'],'settled')
        self.voucher(1,reference='COM-002',purpose='commission_payment',status=422)
        statement=self.client.get(API+'/seller-statements',headers=self.headers).json()['items'][0]
        self.assertEqual(Decimal(statement['balance_due']),0);self.assertEqual(Decimal(statement['commission_due']),0)
        self.assertEqual(Decimal(statement['deposited']),55);self.assertEqual(Decimal(statement['commission_paid']),commission)

    def test_bank_identity_offset_and_caps(self):
        self.setup_sale();first=self.voucher(20)
        self.voucher(10,bank=' bcp ',reference='op-001',status=409)
        self.voucher(10,reference='OP-001',bank='BBVA')
        self.voucher(1,reference='OTHER',content=b'%PDF-1.7 OP-001BCPdeposit',status=409)
        commission=Decimal(self.liq['commission_total'])
        offset=self.voucher(commission,reference='ACUERDO-001',purpose='commission_offset')
        self.verify(offset);self.verify(first)
        self.assertEqual(Decimal(self.detail()['commission_due']),0)
        self.voucher(1,reference='ACUERDO-002',purpose='commission_offset',status=422)
        self.voucher(55,reference='EXCESS',status=422)
        self.action('cancel',409)
        self.post(f'/vouchers/{offset["id"]}/void',{'reason':'Revertir acuerdo de prueba'})
        self.assertEqual(Decimal(self.detail()['commission_due']),commission)

    def test_scope_historical_readonly_and_query_count(self):
        self.setup_sale();deposit=self.voucher(10)
        _,reader=self.login('reader')
        with self.sessions() as db:
            menu=db.query(Menu).filter_by(slug='medical-liquidations').one()
            db.add(AccessGrant(usuario_id=self.reader_id,menu_id=menu.id,access_level='editor'));db.commit()
        self.assertEqual(self.client.get(API+'/seller-statements',headers=reader).status_code,403)
        self.voucher(1,reference='FOREIGN',headers=reader,status=404)
        with self.sessions() as db:
            db.get(MedicalProfile,self.profile_id).user_id=self.reader_id;db.commit()
        self.verify(deposit,403,reader)
        self.voucher(1,reference='OFFSET',purpose='commission_offset',headers=reader,status=403)
        own=self.client.get(API+'/seller-statements',headers=reader);self.assertEqual(own.status_code,200)
        with self.sessions() as db:
            db.get(MedicalLiquidation,self.liq['id']).legacy_id=999;db.commit()
        self.voucher(1,reference='HISTORY',status=409);self.verify(deposit,409)
        self.post(f'/vouchers/{deposit["id"]}/void',{'reason':'Intento histórico'},409)
        self.action('submit',409)
        values=self.client.get(API+'/seller-statements',headers=reader).json()['items'][0]
        self.assertEqual(values['historical_count'],1);self.assertEqual(Decimal(values['balance_due']),0)
        calls=[]
        def trace(*args):calls.append(args[2])
        event.listen(self.engine,'before_cursor_execute',trace)
        self.client.get(API+'/seller-statements',headers=self.headers);before=len(calls)
        event.remove(self.engine,'before_cursor_execute',trace)
        with self.sessions() as db:
            for i in range(12):db.add(MedicalLiquidation(kind='seller',responsible_id=self.profile_id,starts_on=self.day,ends_on=self.day,created_by=self.admin_id,deposit_required=0,commission_total=0,sales_total=0))
            # SQLite Date requires date objects.
            from datetime import date
            for row in db.new:row.starts_on=row.ends_on=date.fromisoformat(self.day)
            db.commit()
        calls.clear();event.listen(self.engine,'before_cursor_execute',trace)
        response=self.client.get(API+'/seller-statements',headers=self.headers)
        event.remove(self.engine,'before_cursor_execute',trace)
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(len(calls),before)

    def test_failed_transaction_removes_only_new_files(self):
        self.setup_sale()
        from app.services import documents
        from app.routes import medical as m
        before=set(documents.STORAGE.iterdir())
        with patch('app.routes.medical.audit_change',side_effect=RuntimeError('Simulated audit failure')):
            with self.assertRaises(RuntimeError):self.voucher(10)
        self.assertEqual(set(documents.STORAGE.iterdir()),before)
        self.assertEqual(list(m.STORAGE.iterdir()),[])
        with self.sessions() as db:self.assertEqual(db.query(MedicalVoucher).count(),0)
