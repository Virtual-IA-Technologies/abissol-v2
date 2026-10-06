import unittest
import json
from io import BytesIO
from zipfile import ZipFile
from unittest.mock import patch
from xml.etree import ElementTree
from sqlalchemy import event
import test_medical as medical
from app.models import AccessGrant, Menu, Usuario
from app.models.medical import MedicalSource, MedicalIssuance, MedicalDispatch, MedicalLiquidation, MedicalBusinessSetting
from app.models.settings import SmtpSetting
from app.models.legacy import LegacyRecord
from app.utils.secrets import encrypt_secret
from app.services.medical_exports import meta_xlsx

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

    def test_meta_summary_history_and_dispatch_codes(self):
        emission = self.setup_emission()
        with self.sessions() as db:
            for state in ("sent", "failed", "uncertain"):
                db.add(MedicalDispatch(issuance_id=emission["id"], kind="meta_daily_report", channel="email", recipient="meta@example.com", status=state, created_by=self.admin_id))
            db.commit()
        for state, total in (("all",1),("pending",0),("sent",1),("failed",1),("uncertain",1)):
            response = self.client.get(API + "/meta-dispatches", params={"status":state}, headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
            result=response.json()
            self.assertEqual(result["total"],total)
            self.assertEqual(result["summary"],{"pending":0,"sent":1,"failed":1})
            if total:
                self.assertEqual(result["items"][0]["dispatch_status"],"uncertain")
        result=self.client.get(API + "/dispatches",headers=self.headers)
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()["items"][0]["issuance_code"],emission["code"])

    def test_preview_query_count_does_not_grow_with_emissions(self):
        emission = self.setup_emission()
        statements=[]
        def capture(conn,cursor,statement,parameters,context,many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)
        event.listen(self.engine,"before_cursor_execute",capture)
        try:
            self.post("/liquidations/preview",self.period(emission))
            baseline=len(statements)
            for number in ("87654321","12348765","56781234"):
                self.issuance(document_number=number)
            statements.clear()
            self.assertEqual(self.post("/liquidations/preview",self.period(emission))["total"],4)
            self.assertEqual(len(statements),baseline)
        finally:
            event.remove(self.engine,"before_cursor_execute",capture)

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
            self.assertEqual(len(xml.findall(".//s:row",ns)[0]),11)
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
            if kind == "xlsx":
                with ZipFile(BytesIO(result.content)) as archive:
                    xml=ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))
                    self.assertEqual(len(xml.findall(".//s:row",ns)[0]),8)
                    self.assertEqual(xml.findall(".//s:row",ns)[1][5].find("s:is/s:t",ns).text,"ESENCIAL")
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

    def test_original_names_are_preserved_for_meta(self):
        emission=self.setup_emission()
        with self.sessions() as db:
            row=db.get(MedicalIssuance,emission["id"])
            row.legacy_id=42
            db.add(LegacyRecord(source_table="medical_issuances",source_key="42",checksum="0"*64,
                payload_encrypted=encrypt_secret(json.dumps({"contractor_name":"ANA", "contractor_paternal_last_name":"PEREZ", "contractor_maternal_last_name":"LOPEZ"}))))
            db.flush()
            content=meta_xlsx([row],db,monthly=True)
            with ZipFile(BytesIO(content)) as archive:
                self.assertIn("PEREZ LOPEZ ANA",archive.read("xl/worksheets/sheet1.xml").decode())

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
