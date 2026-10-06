import json
from string import Formatter
from pydantic import Field, EmailStr, TypeAdapter, field_validator
from ..schemas.medical import Payload
from ..models.medical import MedicalBusinessSetting
from ..models.legacy import LegacyRecord
from ..utils.secrets import decrypt_secret

DEFAULT_MESSAGE = "Hola {nombre}. Bienvenido a ABISSOL. Programa {plan}, certificado {certificado}. Vigencia {inicio} al {fin}. Verificación: {enlace}. Condicionado: {condicionado}"


class BusinessSettingsInput(Payload):
    metafin_email: str = Field(default="", max_length=180)
    daily_dispatch_time: str = Field(default="08:30", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    insured_email_template: str = Field(default="", max_length=5000)
    insured_whatsapp_template: str = Field(default="", max_length=4000)

    @field_validator("metafin_email")
    @classmethod
    def recipients(cls, value):
        return ", ".join(str(TypeAdapter(EmailStr).validate_python(item.strip())) for item in value.replace(";", ",").split(",") if item.strip())

    @field_validator("insured_email_template", "insured_whatsapp_template")
    @classmethod
    def template(cls, value):
        for _, key, spec, conversion in Formatter().parse(value):
            if key is not None and (key not in {"nombre", "plan", "certificado", "inicio", "fin", "enlace", "condicionado"} or spec or conversion):
                raise ValueError("Variable no admitida en la plantilla")
        return value


def business_settings(db):
    row = db.get(MedicalBusinessSetting, 1)
    if row:
        return BusinessSettingsInput.model_validate(row.values).model_dump()
    values = {}
    for legacy in db.query(LegacyRecord).filter_by(source_table="medical_settings"):
        item = json.loads(decrypt_secret(legacy.payload_encrypted))
        key = str(item.get("key", "")).removeprefix("medical.")
        if key in BusinessSettingsInput.model_fields and item.get("value") is not None:
            values[key] = item["value"]
    return BusinessSettingsInput.model_validate(values).model_dump()


def insured_message(db, emission, channel, url):
    template = business_settings(db)["insured_email_template" if channel == "email" else "insured_whatsapp_template"] or DEFAULT_MESSAGE
    return template.format(nombre=emission.customer, plan=emission.plan_name, certificado=emission.code,
                           inicio=emission.starts_on, fin=emission.ends_on, enlace=url, condicionado=emission.conditions_url or "Consultar con ABISSOL")
