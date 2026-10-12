import unittest
import test_medical as medical
from app.models.medical import MedicalIssuance,MedicalInvoice
from app.models.documents import Document,DocumentBinding,DocumentFolder,DocumentVersion
from app.models.legacy import LegacyRecord
from app.utils.secrets import encrypt_secret
from app.services import medical_documents as archive


class AffiliateFolderTests(unittest.TestCase):
    setUp=medical.MedicalTests.setUp
    cleanup=medical.MedicalTests.cleanup
    login=medical.MedicalTests.login
    prepare=medical.MedicalTests.prepare
    post=medical.MedicalTests.post
    issuance=medical.MedicalTests.issuance

    def test_identity_invoice_buyer_and_metadata_only_backfill(self):
        self.prepare()
        first=self.issuance()
        second=self.issuance(document_number='87654321')
        with self.sessions() as db:
            a=db.get(MedicalIssuance,first['id']);b=db.get(MedicalIssuance,second['id'])
            self.assertNotEqual(archive.affiliate_path(a)[2][0],archive.affiliate_path(b)[2][0])
            a.customer='Nombre corregido'
            self.assertEqual(archive.affiliate_path(a)[2][0],archive.affiliate_path(type('Renewal',(),{**first,'customer':'Nombre original','id':999})())[2][0])
            invoice=MedicalInvoice(issuance_id=a.id,document_type='factura',customer='EMPRESA COMPRADORA',document_number='20123456789',total=55,full_number='F001-1',created_by=self.admin_id)
            db.add(invoice);db.flush()
            doc=archive.archive(db,source='invoice',ident=invoice.id,key='PDF',actor=self.admin_id,path=[('old','Anterior')],filename='factura.pdf',content=b'%PDF original')
            self.assertEqual(archive.invoice_path(db,invoice)[2][0],archive.affiliate_path(a)[2][0])
            imported=Document(owner_id=self.admin_id,folder_id=doc.folder_id,title='Original',is_system=False,current_version=1)
            db.add(imported);db.flush()
            db.add(LegacyRecord(source_table='medical_issuances',source_key='111',target_id=a.id,checksum='a'*64,payload_encrypted=encrypt_secret('{}')))
            db.add(LegacyRecord(source_table='documents',source_key='222',target_id=imported.id,checksum='b'*64,payload_encrypted=encrypt_secret('{"entity_type":"medical_issuance","entity_id":111}')))
            for bound in db.query(DocumentBinding).filter_by(source_type='emission'):
                db.get(Document,bound.document_id).folder_id=doc.folder_id
            db.commit()
            before=[(v.id,v.storage_key,v.sha256) for v in db.query(DocumentVersion).order_by(DocumentVersion.id)]
            result=archive.organize_affiliates(db,self.admin_id);db.commit()
            self.assertEqual(result['moved'],4)
            self.assertEqual(db.get(Document,imported.id).folder_id,db.query(DocumentFolder).filter_by(system_key='abissol:affiliate:emission:'+str(a.id)).one().id)
            self.assertFalse(imported.is_system)
            self.assertEqual(archive.organize_affiliates(db,self.admin_id)['moved'],0)
            self.assertEqual(before,[(v.id,v.storage_key,v.sha256) for v in db.query(DocumentVersion).order_by(DocumentVersion.id)])
            archive.archive(db,source='invoice',ident=invoice.id,key='PDF',actor=self.admin_id,path=archive.invoice_path(db,invoice),filename='factura.pdf',content=b'%PDF original')
            db.commit()
            self.assertEqual(len(before),db.query(DocumentVersion).count())
