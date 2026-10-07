import unittest
from pathlib import Path
import test_medical as medical
from app.models import AccessGrant,Menu,Usuario
from app.models.medical import MedicalIssuance,MedicalProfile
from app.models.documents import Document,DocumentBinding,DocumentVersion
from app.services import medical_documents as archive,documents

API='/abissol/api/v1/documentos'


class ArchiveTests(unittest.TestCase):
    setUp=medical.MedicalTests.setUp
    cleanup=medical.MedicalTests.cleanup
    login=medical.MedicalTests.login
    prepare=medical.MedicalTests.prepare
    post=medical.MedicalTests.post
    issuance=medical.MedicalTests.issuance

    def listing(self,headers=None,**params):
        result=self.client.get(API,params=params,headers=headers or self.headers)
        self.assertEqual(result.status_code,200,result.text)
        return result.json()

    def test_automatic_certificate_and_immutable_folder(self):
        self.prepare();sale=self.issuance()
        rows=self.listing()['items'];self.assertEqual(len(rows),1)
        doc=rows[0];self.assertTrue(doc['managed']);self.assertFalse(doc['owned'])
        folder=doc['folder_id']
        tree=self.client.get(API+'/carpetas',headers=self.headers).json()
        self.assertTrue(all(f['managed'] for f in tree))
        self.assertIn('ABISSOL',[f['name'] for f in tree])
        result=self.client.get(API+f'/{doc["id"]}/archivo/1',headers=self.headers)
        self.assertTrue(result.content.startswith(b'%PDF'))
        for path,payload in [(f'/{doc["id"]}/copiar',{'folder_id':None,'revision':doc['revision']}),
            (f'/{doc["id"]}/compartir',{'recipient':'reader','revision':doc['revision']}),
            ('/carpetas',{'name':'Inyectada','parent_id':folder})]:
            self.assertEqual(self.client.post(API+path,json=payload,headers=self.headers).status_code,403)
        self.assertEqual(self.client.delete(API+f'/carpetas/{folder}',headers=self.headers).status_code,403)
        self.assertEqual(self.client.post(API+f'/{doc["id"]}/papelera?revision={doc["revision"]}',headers=self.headers).status_code,403)
        with self.sessions() as db:
            archive.emission(db,db.get(MedicalIssuance,sale['id']));db.commit()
            self.assertEqual(db.query(DocumentVersion).count(),1)

    def test_business_scope_and_revocation_apply_to_folders_and_direct_urls(self):
        self.prepare();sale=self.issuance();doc=self.listing()['items'][0]
        _,headers=self.login('reader')
        with self.sessions() as db:
            for slug in ('documentos','medical-emissions'):
                menu=db.query(Menu).filter_by(slug=slug).one()
                db.add(AccessGrant(usuario_id=self.reader_id,menu_id=menu.id,access_level='lector'))
            db.commit()
        self.assertEqual(self.listing(headers)['total'],0)
        self.assertEqual(self.client.get(API+'/carpetas',headers=headers).json(),[])
        self.assertEqual(self.client.get(API+f'/{doc["id"]}/archivo/1',headers=headers).status_code,404)
        with self.sessions() as db:
            db.get(MedicalProfile,self.profile_id).user_id=self.reader_id;db.commit()
        self.assertEqual(self.listing(headers)['total'],1)
        self.assertTrue(self.client.get(API+'/carpetas',headers=headers).json())
        with self.sessions() as db:
            menu=db.query(Menu).filter_by(slug='medical-emissions').one()
            db.query(AccessGrant).filter_by(usuario_id=self.reader_id,menu_id=menu.id).delete();db.commit()
        self.assertEqual(self.listing(headers)['total'],0)
        self.assertEqual(self.client.get(API+f'/{doc["id"]}',headers=headers).status_code,404)

    def test_hash_versions_and_rollback_keep_original(self):
        self.prepare()
        kwargs=dict(source='plan',ident=self.plan_id,key='example',actor=self.admin_id,path=[('abissol','ABISSOL'),('abissol:plan','Planes')],filename='condiciones.txt')
        with self.sessions() as db:
            doc=archive.archive(db,**kwargs,content=b'original');db.commit();ident=doc.id
            archive.archive(db,**kwargs,content=b'original');db.commit()
            self.assertEqual(db.query(DocumentVersion).count(),1)
            archive.archive(db,**kwargs,content=b'actualizado');db.commit()
            self.assertEqual(db.query(DocumentVersion).count(),2)
            existing=set(documents.STORAGE.iterdir())
            archive.archive(db,**{**kwargs,'key':'rollback'},content=b'no guardar');db.rollback()
            self.assertEqual(set(documents.STORAGE.iterdir()),existing)
            self.assertEqual(db.query(DocumentBinding).count(),1)
            self.assertEqual(db.get(Document,ident).current_version,2)

    def test_personal_upload_stays_private_and_mutable(self):
        self.prepare()
        result=self.client.post(API,files={'file':('personal.txt',b'privado','text/plain')},headers=self.headers)
        self.assertEqual(result.status_code,201,result.text)
        doc=result.json();self.assertTrue(doc['owned']);self.assertFalse(doc['managed'])
        result=self.client.put(API+f'/{doc["id"]}',json={'title':'renombrado.txt','description':'Privado','folder_id':None,'revision':doc['revision']},headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)

    def test_source_replacement_preserves_archived_version(self):
        self.prepare()
        source=documents.STORAGE/'source.txt';source.parent.mkdir(parents=True,exist_ok=True)
        source.write_bytes(b'original')
        kwargs=dict(source='plan',ident=self.plan_id,key='original',actor=self.admin_id,path=[('abissol','ABISSOL')],filename='condiciones.txt',file_path=source)
        with self.sessions() as db:
            doc=archive.archive(db,**kwargs);db.commit()
            version=db.query(DocumentVersion).filter_by(document_id=doc.id,number=1).one()
            stored=documents.file_path(version.storage_key)
            replacement=source.with_suffix('.tmp');replacement.write_bytes(b'updated');replacement.replace(source)
            self.assertEqual(stored.read_bytes(),b'original')
            archive.archive(db,**kwargs);db.commit()
            archive.archive(db,**kwargs);db.commit()
            self.assertEqual(db.query(DocumentVersion).filter_by(document_id=doc.id).count(),2)
            source.unlink()
            self.assertEqual(stored.read_bytes(),b'original')
