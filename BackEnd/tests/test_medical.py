"""Pruebas de negocio con SQLite aislado; no envían comunicaciones reales."""
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo
import test_platform as platform
from app.models import AccessGrant, Menu, Usuario
from app.models.medical import MedicalPlan, MedicalIssuance, MedicalLiquidationItem, MedicalVoucher

API = platform.API + "/medical"

class MedicalTests(unittest.TestCase):
    setUp = platform.PlatformTests.setUp
    cleanup = platform.PlatformTests.cleanup
    login = platform.PlatformTests.login

    def prepare(self):
        _, self.headers = self.login()
        with self.sessions() as db:
            admin = db.query(Usuario).filter_by(username="admin").one()
            reader = db.query(Usuario).filter_by(username="reader").one()
            self.admin_id, self.reader_id = admin.id, reader.id
        refs = self.client.get(API + "/lookups?section=network", headers=self.headers).json()
        self.source_id = refs["sources"][0]["id"]
        self.plan_id = self.client.get(API + "/plans", headers=self.headers).json()["items"][0]["id"]
        self.profile_id = self.post("/profiles", {"user_id": self.admin_id, "source_id": self.source_id, "kind": "responsible"})["id"]

    def post(self, path, payload, status=200, headers=None):
        response = self.client.post(API + path, json=payload, headers=headers or self.headers)
        self.assertEqual(response.status_code, status, response.text)
        return response.json()

    def issuance(self, **changes):
        values = dict(plan_id=self.plan_id, emitter_id=self.profile_id, document_type="DNI", document_number="12345678", customer="Persona de prueba", email="test@example.com", starts_on=(datetime.now(ZoneInfo("America/Lima")).date()+timedelta(days=1)).isoformat(), payment_method="cash", payment_status="collected_by_seller")
        values.update(changes)
        return self.post("/emissions", values)

    def test_snapshots_dates_public_validation_and_pdf(self):
        self.prepare()
        first = self.issuance()
        self.assertEqual(first["price"], "55.00")
        with self.sessions() as db:
            p = db.get(MedicalPlan, self.plan_id)
            p.price, p.validity_days = Decimal("60"), 30
            db.commit()
        second = self.issuance()
        self.assertNotEqual(first["code"], second["code"])
        self.assertEqual(second["price"], "60.00")
        self.assertEqual((datetime.fromisoformat(second["ends_on"]) - datetime.fromisoformat(second["starts_on"])).days, 29)
        with self.sessions() as db:
            self.assertEqual(db.get(MedicalIssuance, first["id"]).price, Decimal("55"))
        public = self.client.get(API + "/validate/" + first["token"])
        self.assertEqual(public.status_code, 200)
        self.assertNotIn("customer", public.json())
        self.assertNotIn("document_number", public.json())
        self.assertNotIn("email", public.json())
        self.assertFalse(public.json()["valid_now"])
        pdf = self.client.get(API + f'/emissions/{first["id"]}/letter', headers=self.headers)
        self.assertEqual(pdf.status_code, 200, pdf.text[:100] if pdf.status_code != 200 else "")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_scope_and_menu_permissions(self):
        self.prepare()
        row = self.issuance()
        _, reader_headers = self.login("reader")
        self.assertEqual(self.client.get(API + "/emissions", headers=reader_headers).status_code, 403)
        with self.sessions() as db:
            for slug in ["medical-emissions", "medical-reports", "medical-liquidations", "medical-billing"]:
                menu = db.query(Menu).filter_by(slug=slug).one()
                db.add(AccessGrant(usuario_id=self.reader_id, menu_id=menu.id, access_level="editor"))
            db.commit()
        self.assertEqual(self.client.get(API + "/emissions", headers=reader_headers).json()["total"], 0)
        self.assertEqual(self.client.get(API + f'/emissions/{row["id"]}/letter', headers=reader_headers).status_code, 404)
        self.assertEqual(self.client.get(API + "/reports", headers=reader_headers).json()["count"], 0)
        self.assertEqual(self.client.get(API + "/issuance-options?section=billing", headers=reader_headers).json(), [])
        self.post("/billing", {"issuance_id": row["id"], "document_type": "boleta", "customer": "Prueba", "document_number": "12345678"}, 404, reader_headers)

    def test_liquidation_reconciliation_and_unique_membership(self):
        self.prepare()
        emission = self.issuance()
        period = {"kind": "seller", "responsible_id": self.profile_id, "starts_on": emission["sale_date"], "ends_on": emission["sale_date"]}
        liq = self.post("/liquidations", period)
        self.assertEqual(liq["deposit_required"], "55.00")
        self.post("/liquidations", period, 422)
        self.post(f'/liquidations/{liq["id"]}/approve', {"reason": "Aprobar prueba"}, 409)
        self.post(f'/liquidations/{liq["id"]}/submit', {"reason": "Presentar prueba"}, 422)
        with TemporaryDirectory() as directory, patch("app.routes.medical.STORAGE", Path(directory)):
            response = self.client.post(API + f'/liquidations/{liq["id"]}/vouchers', data={"reference": "TEST-001", "amount": "55", "paid_on": emission["sale_date"]}, files={"file": ("deposito.pdf", b"%PDF-1.7 prueba", "application/pdf")}, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("storage_key", response.json())
            voucher_id = response.json()["id"]
            with self.sessions() as db:
                legacy = db.get(MedicalVoucher, voucher_id)
                legacy.active_reference = legacy.active_digest = None
                db.commit()
            for reference, content in [('test-001', b'%PDF-1.7 otro'), ('NEW-REF', b'%PDF-1.7 prueba')]:
                duplicate = self.client.post(API + f'/liquidations/{liq["id"]}/vouchers', data={"reference": reference, "amount": "55", "paid_on": emission["sale_date"]}, files={"file": ("deposito.pdf", content, "application/pdf")}, headers=self.headers)
                self.assertEqual(duplicate.status_code, 409)
            self.post(f"/vouchers/{voucher_id}/void", {"reason": "Corregir comprobante"})
            replacement = self.client.post(API + f'/liquidations/{liq["id"]}/vouchers', data={"reference": "TEST-001", "amount": "55", "paid_on": emission["sale_date"]}, files={"file": ("deposito.pdf", b"%PDF-1.7 prueba", "application/pdf")}, headers=self.headers)
            self.assertEqual(replacement.status_code, 200, replacement.text)
            for action, target in [("submit", "submitted"), ("approve", "approved"), ("pay", "paid")]:
                result = self.post(f'/liquidations/{liq["id"]}/{action}', {"reason": "Conciliación de prueba"})
                self.assertEqual(result["status"], target)
            self.post(f'/vouchers/{replacement.json()["id"]}/void', {"reason": "Retirar conciliado"}, 409)
        self.post(f'/liquidations/{liq["id"]}/cancel', {"reason": "Cancelar prueba"}, 409)
        with self.sessions() as db:
            self.assertEqual(db.get(MedicalIssuance, emission["id"]).payment_status, "settled")

    def test_cancel_releases_liquidation_not_emission_history(self):
        self.prepare()
        emission = self.issuance()
        payload = {"kind": "seller", "responsible_id": self.profile_id, "starts_on": emission["sale_date"], "ends_on": emission["sale_date"]}
        liq = self.post("/liquidations", payload)
        self.post(f'/liquidations/{liq["id"]}/cancel', {"reason": "Rehacer período"})
        self.post("/liquidations", payload)
        with self.sessions() as db:
            self.assertEqual(db.query(MedicalLiquidationItem).count(), 2)
            self.assertEqual(db.query(MedicalLiquidationItem).filter(MedicalLiquidationItem.active_key.is_not(None)).count(), 1)

    def test_billing_draft_and_outbound_delivery(self):
        self.prepare()
        row = self.issuance()
        payload = {"issuance_id": row["id"], "document_type": "boleta", "customer": "Cliente prueba", "document_number": "12345678"}
        invoice = self.post("/billing", payload)
        self.assertEqual(invoice["status"], "draft")
        self.assertEqual(invoice["sunat_status"], "not_sent")
        self.post("/billing", payload, 409)
        with patch("app.routes.medical.send_email", side_effect=RuntimeError("secret-provider-token")):
            dispatch = self.post("/dispatches", {"issuance_id": row["id"], "channel": "email"})
        self.assertEqual(dispatch["status"], "failed")
        self.assertNotIn("secret-provider-token", dispatch["error"])
        with patch("app.routes.medical.send_email") as sender:
            retried = self.post(f'/dispatches/{dispatch["id"]}/retry', {})
            self.assertEqual(retried["status"], "sent")
            self.assertEqual(retried["attempts"], 2)
            sender.assert_called_once()
        self.post(f'/dispatches/{dispatch["id"]}/retry', {}, 409)

    def test_collection_cannot_be_recorded_twice(self):
        self.prepare()
        row = self.issuance(payment_status="pending")
        self.post(f'/emissions/{row["id"]}/payment', {"payment_status": "paid_to_abissol", "reference": "BANCO-TEST"})
        self.post(f'/emissions/{row["id"]}/payment', {"payment_status": "paid_to_abissol", "reference": "BANCO-TEST"}, 409)
        self.post(f'/emissions/{row["id"]}/cancel', {"reason": "Cancelar cobro"}, 409)
        report = self.client.get(API + "/reports", headers=self.headers).json()
        self.assertEqual(Decimal(report["pending"]), 0)
        self.assertEqual(Decimal(report["collected"]), 55)
