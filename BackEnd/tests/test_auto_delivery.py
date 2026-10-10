from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from test_medical_testing import LocalTestModeTests
from app.models.medical import MedicalDispatch
from app.services import medical_billing as fiscal,medical_auto_delivery as auto
from test_medical_integration import API

class AutomaticDeliveryTests(LocalTestModeTests):
    def enable_delivery(self):
        with self.sessions() as db:
            row,raw=fiscal.configuration(db)
            raw.update(automatic_documents_enabled=True,test_delivery_emails=['test@example.com'],test_delivery_phones=['51998896625'])
            fiscal.persist_config(row,raw);db.commit()

    def test_portal_queue_documents_once_and_simulates_other_recipients(self):
        self.prepare();self.enable();self.enable_delivery()
        with TemporaryDirectory() as tmp,patch.object(fiscal,'STORAGE',Path(tmp)),patch('app.routes.medical.send_email') as mail,patch('app.routes.medical.send_whatsapp') as whatsapp:
            self.issuance(phone='51999111222')
            with self.sessions() as db:
                rows=db.query(MedicalDispatch).filter_by(kind=auto.KIND).all()
                self.assertEqual([(r.channel,r.status) for r in rows],[('email','pending'),('whatsapp','simulated')])
                ident=rows[0].id
            mail.assert_not_called()
            with self.sessions() as db:auto.process(db,ident)
            with self.sessions() as db:auto.process(db,ident)
            mail.assert_called_once();whatsapp.assert_not_called()
            names=[a[0] for a in mail.call_args.kwargs['attachments']]
            self.assertIn('carta-bienvenida-abissol.pdf',names)
            self.assertTrue(any(n.startswith('TB00-') for n in names))

    def test_external_idempotency_and_validation_rollback(self):
        payload=self.setup_connector();self.enable();self.enable_delivery()
        payload.update(contractor_email='test@example.com',contractor_phone='51998896625')
        with TemporaryDirectory() as tmp,patch.object(fiscal,'STORAGE',Path(tmp)),patch('app.routes.medical.send_email') as mail,patch('app.routes.medical.send_whatsapp') as whatsapp:
            response=self.client.post(API+'/emissions/validate',headers=self.connector_headers,json=payload)
            self.assertEqual(response.status_code,200,response.text)
            with self.sessions() as db:self.assertEqual(db.query(MedicalDispatch).count(),0)
            self.send(payload);self.send(payload)
            with self.sessions() as db:
                rows=db.query(MedicalDispatch).filter_by(kind=auto.KIND).all()
                self.assertEqual(len(rows),2);ids=[r.id for r in rows]
            for ident in ids:
                with self.sessions() as db:auto.process(db,ident)
            mail.assert_called_once();whatsapp.assert_called_once()
            self.assertIn('\n\nCarta de bienvenida:\nhttps://',whatsapp.call_args.args[2])
