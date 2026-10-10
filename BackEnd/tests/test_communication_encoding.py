import unittest
from types import SimpleNamespace
from unittest.mock import patch
from app.services.medical_settings import BusinessSettingsInput
from app.services.email import send_email

class CommunicationTests(unittest.TestCase):
    def test_utf8_template_and_broken_text(self):
        text='Verificación: {enlace}\nBienvenida, señora {nombre}.'
        self.assertEqual(BusinessSettingsInput(insured_whatsapp_template=text).insured_whatsapp_template,text)
        with self.assertRaises(ValueError):BusinessSettingsInput(insured_whatsapp_template='Verificaci??n: {enlace}')

    def test_smtp_keeps_cc_and_unicode(self):
        setting=SimpleNamespace(host='smtp.example.com',port=587,from_email='contacto@example.com',from_name='Asociación de Bienestar',use_ssl=False,use_tls=True,username='')
        with patch('app.services.email.get_smtp_setting',return_value=setting),patch('app.services.email.smtplib.SMTP') as smtp:
            send_email(None,'office@example.com','Liquidación','Verificación completada.',cc='copy@example.com')
            message=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            self.assertEqual(str(message['To']),'office@example.com')
            self.assertEqual(str(message['Cc']),'copy@example.com')
            self.assertIn('Verificación',message.get_content())
