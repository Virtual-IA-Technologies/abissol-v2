import unittest
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch
from xml.etree import ElementTree
import test_medical as medical
from app.models import AccessGrant, Menu, Usuario
from app.models.medical import MedicalSource, MedicalIssuance, MedicalDispatch, MedicalLiquidation, MedicalBusinessSetting
from app.models.settings import SmtpSetting

API = medical.API


class WorkspaceTests(unittest.TestCase):
    setUp = medical.MedicalTests.setUp
    cleanup = medical.MedicalTests.cleanup
    login = medical.MedicalTests.login
    prepare = medical.MedicalTests.prepare
    post = medical.MedicalTests.post
    issuance = medical.MedicalTests.issuance

    def setup_emission(self, **changes):
        self.prepare()
        return self.issuance(**changes)

    def period(self, emission, kind="seller"):
        return {"kind":kind, "responsible_id":self.profile_id if kind=="seller" else None,
                "starts_on":emission["sale_date"],"ends_on":emission["sale_date"]}

    def test_preview_selected_membership_and_type_filters(self):
        emission = self.setup_emission()
        second = self.issuance(document_number="87654321")
        upcoming = self.client.get(API+"/emissions",params={"state":"upcoming"},headers=self.headers).json()
        self.assertEqual(upcoming["summary"]["upcoming"],2)
        self.assertEqual(upcoming["total"],2)
        self.assertEqual(self.client.get(API+"/emissions",params={"state":"active"},headers=self.headers).json()["total"],0)
        period = self.period(emission)
        preview = self.post("/liquidations/preview",period)
        self.assertEqual(preview["total"],2)
        with self.sessions() as db:
            self.assertEqual(db.query(MedicalLiquidation).count(),0)
        row = self.post("/liquidations",{**period,"issuance_ids":[emission["id"]]})
        self.assertEqual(row["deposit_required"],"55.00")
        self.assertTrue(row["code"].startswith("LQ-"))
        self.post("/liquidations",{**period,"issuance_ids":[emission["id"]]},409)
        self.assertEqual(self.post("/liquidations/preview",period)["items"][0]["id"],second["id"])
        for kind in ("meta","platform"):
            monthly=self.post("/liquidations",self.period(emission,kind))
            self.assertIsNone(monthly["responsible_id"])
            listed=self.client.get(API+"/liquidations",params={"kind":kind},headers=self.headers).json()
            self.assertEqual([r["id"] for r in listed["items"]],[monthly["id"]])

    def test_afocat_deposit_and_unpaid_monthly_eligibility(self):
        emission=self.setup_emission()
        with self.sessions() as db:
            db.get(MedicalSource,self.source_id).kind="afocat"
            db.commit()
        preview=self.post("/liquidations/preview",self.period(emission))
        self.assertEqual(preview["deposit_total"],"12.00")
        pending=self.issuance(document_number="87654321",payment_status="pending")
        self.assertEqual(self.post("/liquidations/preview",self.period(pending))["total"],1)
        self.assertEqual(self.post("/liquidations/preview",self.period(pending,"meta"))["total"],2)

    def configure(self):
        with self.sessions() as db:
            db.add(SmtpSetting(host="smtp.example.com",from_email="test@example.com",is_active=True))
            db.add(MedicalBusinessSetting(id=1,values={"metafin_email":"meta@example.com"}))
            db.commit()

    def test_meta_export_send_deduplication_and_monthly_files(self):
        emission=self.setup_emission(customer="=SUM(A1:A2)")
        self.configure()
        selection={"issuance_ids":[emission["id"]]}
        exported=self.client.post(API+"/meta-dispatches/export",json=selection,headers=self.headers)
        self.assertEqual(exported.status_code,200)
        with ZipFile(BytesIO(exported.content)) as archive:
            xml=ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
            ns={"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            self.assertEqual(len(xml.findall(".//s:row",ns)),2)
            self.assertEqual(len(xml.findall(".//s:f",ns)),0)
            self.assertIn("=SUM(A1:A2)",archive.read("xl/worksheets/sheet1.xml").decode())
        with patch("app.routes.medical_workspaces.send_email") as send:
            self.assertEqual(self.post("/meta-dispatches/send",selection)["status"],"sent")
            self.post("/meta-dispatches/send",selection,409)
            self.assertEqual(send.call_count,1)
            self.post("/meta-dispatches/send",{**selection,"force":True})
            self.assertEqual(send.call_count,2)
        self.assertEqual(self.client.get(API+"/meta-dispatches",headers=self.headers).json()["total"],0)
        monthly=self.post("/liquidations",self.period(emission,"meta"))
        for kind,signature in [("xlsx",b"PK"),("letter",b"%PDF")]:
            result=self.client.get(API+f'/liquidations/{monthly["id"]}/meta-file/{kind}',headers=self.headers)
            self.assertEqual(result.status_code,200)
            self.assertTrue(result.content.startswith(signature))
        with patch("app.routes.medical_workspaces.send_email") as send:
            self.post(f'/liquidations/{monthly["id"]}/meta-send',{})
            self.assertEqual(len(send.call_args.kwargs["attachments"]),2)
        with self.sessions() as db:
            self.assertEqual(db.get(MedicalIssuance,emission["id"]).payment_status,"collected_by_seller")

    def test_uncertain_delivery_requires_explicit_resend(self):
        emission=self.setup_emission();self.configure()
        with patch("app.routes.medical_workspaces.send_email",side_effect=TimeoutError):
            result=self.post("/meta-dispatches/send",{"issuance_ids":[emission["id"]]})
        self.assertEqual(result["status"],"uncertain")
        self.post("/meta-dispatches/send",{"issuance_ids":[emission["id"]]},409)

    def test_restricted_user_cannot_access_meta_or_settings(self):
        emission=self.setup_emission()
        _,headers=self.login("reader")
        with self.sessions() as db:
            for slug in ("medical-emissions","medical-liquidations"):
                menu=db.query(Menu).filter_by(slug=slug).one()
                db.add(AccessGrant(usuario_id=self.reader_id,menu_id=menu.id,access_level="editor"))
            db.commit()
        for path in ("/meta-dispatches","/emission-settings"):
            self.assertEqual(self.client.get(API+path,headers=headers).status_code,403)
        self.post("/liquidations/preview",self.period(emission,"meta"),403,headers=headers)
        self.assertEqual(self.client.put(API+"/emission-settings",json={"metafin_email":"test@example.com","insured_email_template":"{unknown}"},headers=self.headers).status_code,422)
        result=self.client.put(API+"/emission-settings",json={"metafin_email":"test@example.com","insured_email_template":"Hola {nombre}"},headers=self.headers)
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.client.get(API+"/emission-settings",headers=self.headers).json()["insured_email_template"],"Hola {nombre}")
