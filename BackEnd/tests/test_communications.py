import unittest
from unittest.mock import patch

import test_medical as medical
from app.models import AccessGrant, Menu, Rol, Usuario
from scripts.import_legacy_communications import effective_channels


class CommunicationTests(unittest.TestCase):
    setUp = medical.MedicalTests.setUp
    cleanup = medical.MedicalTests.cleanup
    login = medical.MedicalTests.login
    prepare = medical.MedicalTests.prepare
    post = medical.MedicalTests.post

    def test_configuration_is_programmer_only_even_with_admin_grants(self):
        self.prepare()
        _, headers = self.login("reader")
        with self.sessions() as db:
            reader = db.get(Usuario, self.reader_id)
            reader.roles = [db.query(Rol).filter_by(nombre="Administrador").one()]
            for slug in ("smtp", "whatsapp", "medical-dispatches"):
                menu = db.query(Menu).filter_by(slug=slug).one()
                db.add(AccessGrant(usuario_id=reader.id, menu_id=menu.id, access_level="gestor"))
            db.commit()
        for slug in ("smtp", "whatsapp"):
            path = medical.platform.API + f"/{slug}-settings"
            self.assertEqual(self.client.get(path, headers=headers).status_code, 403)
            self.assertEqual(self.client.put(path, json={}, headers=headers).status_code, 403)
            self.assertEqual(self.client.post(path + "/test", json={}, headers=headers).status_code, 403)
            response = self.client.get(path, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertFalse({"password", "token", "secret_key", "password_encrypted", "token_encrypted"} & response.json().keys())
        self.assertFalse(self.client.get(medical.API + "/lookups?section=dispatches", headers=headers).json()["can_configure_communications"])
        self.assertTrue(self.client.get(medical.API + "/lookups?section=dispatches", headers=self.headers).json()["can_configure_communications"])

    def test_source_precedence_and_otp_stays_disabled(self):
        system = {"mail_enabled": "1", "mail_mailer": "smtp", "mail_host": "smtp.example.com",
                  "mail_port": "465", "mail_encryption": "ssl", "mail_username": "user",
                  "mail_password": "synthetic", "mail_from_address": "test@example.com",
                  "wablas_token": "system-token", "wablas_secret_key": "system-secret", "wablas_enabled": "1"}
        smtp, wa = effective_channels(system, {"medical.wablas_token": "medical-token"}, {"MAIL_HOST": "wrong.example.com", "WHATSAPP_ENABLED": "false"})
        self.assertEqual(smtp["host"], "smtp.example.com")
        self.assertTrue(smtp["use_ssl"])
        self.assertFalse(smtp["use_tls"])
        self.assertEqual(wa["token"], "medical-token")
        self.assertTrue(wa["is_active"])
        self.assertFalse(wa["otp_enabled"])
        system["mail_enabled"] = "0"
        smtp, _ = effective_channels(system, {}, {"MAIL_HOST": "env.example.com", "MAIL_FROM_ADDRESS": "test@example.com", "MAIL_ENCRYPTION": "tls", "MAIL_PORT": "587"})
        self.assertEqual(smtp["host"], "env.example.com")
        self.assertTrue(smtp["use_tls"])
        self.assertFalse(smtp["use_ssl"])

    def test_provider_credentials_are_used_without_real_messages(self):
        self.prepare()
        path = medical.platform.API
        response = self.client.put(path + "/whatsapp-settings", headers=self.headers, json={
            "endpoint": "https://texas.wablas.com/api/send-message", "country_code": "51",
            "token": "synthetic-token", "secret_key": "synthetic-secret", "is_active": True,
            "otp_message": "Codigo {code}", "otp_enabled": False,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["token_configured"])
        with patch("app.services.whatsapp.urlopen") as send:
            send.return_value.__enter__.return_value.read.return_value = b'{"status":true}'
            response = self.client.post(path + "/whatsapp-settings/test", headers=self.headers,
                                        json={"phone": "999999999", "message": "Synthetic test"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(send.call_count, 1)
            request = send.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "synthetic-token.synthetic-secret")
            self.assertIn(b"phone=51999999999", request.data)


if __name__ == "__main__":
    unittest.main()
