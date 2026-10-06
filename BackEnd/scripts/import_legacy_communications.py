"""Copy effective Laravel channel settings on the server; never send messages.

Run from BackEnd with the project interpreter. Defaults to a redacted preview.
Credentials stay on the server and are encrypted with V2's key before storage.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def enabled(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def effective_channels(system, medical, env):
    # MailConfigHelper overrides environment only when mail_config is enabled.
    override = enabled(system.get("mail_enabled", "0"))

    def mail(key, fallback=""):
        return system.get("mail_" + key, fallback) if override else env.get("MAIL_" + key.upper(), fallback)

    encryption = str(mail("encryption", "ssl" if override else "tls") or "").lower()
    if str(mail("mailer", "smtp")).lower() != "smtp":
        raise ValueError("El transporte del origen no es SMTP")
    if encryption not in {"", "null", "none", "tls", "ssl"}:
        raise ValueError("Cifrado SMTP no compatible")
    smtp = dict(host=mail("host"), port=int(mail("port", 465 if override else 587)),
                username=mail("username") or None, password=mail("password"),
                from_email=mail("from_address"), from_name=mail("from_name", "ABISSOL"),
                use_tls=encryption == "tls", use_ssl=encryption == "ssl", is_active=True)
    if not smtp["host"] or not smtp["from_email"] or not 1 <= smtp["port"] <= 65535:
        raise ValueError("SMTP incompleto en el origen")
    if smtp["username"] and not smtp["password"]:
        raise ValueError("SMTP sin clave en el origen")

    def setting(keys, fallback):
        # MedicalEmissionController searches all medical keys before system keys.
        for source in (medical, system):
            for key in keys:
                if source.get(key) not in (None, ""):
                    return source[key]
        return fallback

    def whatsapp(suffix, alias, env_alias, default=""):
        return setting(["wablas_" + suffix, "medical.wablas_" + suffix,
                        "whatsapp_" + alias, "medical.whatsapp_" + alias],
                       env.get("WHATSAPP_" + env_alias, env.get("WABLAS_" + suffix.upper(), default)))

    wa = dict(provider="wablas", endpoint=str(whatsapp("endpoint", "api_url", "API_URL", "https://texas.wablas.com/api/send-message")).strip(),
              token=str(whatsapp("token", "token", "TOKEN")).strip(),
              secret_key=str(whatsapp("secret_key", "secret_key", "SECRET_KEY")).strip(),
              country_code=str(whatsapp("default_country_code", "default_country_code", "DEFAULT_COUNTRY_CODE", "51")).strip(),
              is_active=enabled(whatsapp("enabled", "enabled", "ENABLED", True)), otp_enabled=False)
    endpoint = urlparse(wa["endpoint"])
    if endpoint.scheme != "https" or not (endpoint.hostname or "").endswith(".wablas.com") or endpoint.path not in {"/api/send-message", "/api/v2/send-message"}:
        raise ValueError("Revisar endpoint Wablas del origen")
    if wa["is_active"] and (not wa["token"] or not wa["secret_key"]):
        raise ValueError("WhatsApp activo sin credenciales completas")
    if not wa["country_code"].isdigit() or len(wa["country_code"]) > 5:
        raise ValueError("Codigo de pais invalido")
    return smtp, wa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--legacy-env", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    if args.apply and not args.backup_dir:
        parser.error("--apply requiere --backup-dir")
    import pymysql
    from dotenv import dotenv_values
    env = dotenv_values(args.legacy_env, encoding="latin-1")
    with pymysql.connect(read_default_file="/root/.my.cnf", database=env["DB_DATABASE"]) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT setting_key, setting_value FROM system_settings WHERE group_name = 'mail_config' OR setting_key LIKE 'wablas_%' OR setting_key LIKE 'whatsapp_%' OR setting_key LIKE 'medical.%'")
            system = dict(cursor.fetchall())
            cursor.execute("SELECT `key`, `value` FROM medical_settings")
            medical = dict(cursor.fetchall())
    smtp, wa = effective_channels(system, medical, env)
    summary = {"smtp_active": smtp["is_active"], "smtp_password_configured": bool(smtp["password"]),
               "whatsapp_active": wa["is_active"], "whatsapp_credentials_configured": bool(wa["token"] and wa["secret_key"]), "otp_enabled": False}
    if not args.apply:
        print(json.dumps({"preview": summary}))
        return
    from app.database import SessionLocal
    from app.models.settings import SmtpSetting, WhatsappSetting
    from app.models.audit import AuditLog
    from app.utils.secrets import encrypt_secret
    import app.models  # Register model relationships.
    with SessionLocal() as db:
        rows = [db.query(model).order_by(model.id).first() for model in (SmtpSetting, WhatsappSetting)]
        backup = {model.__tablename__: {column.name: getattr(row, column.name) for column in model.__table__.columns} if row else None
                  for model, row in zip((SmtpSetting, WhatsappSetting), rows)}
        args.backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = args.backup_dir / ("communications-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + ".json")
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as target:
            json.dump(backup, target, default=str)
        for model, row, values, secrets in [(SmtpSetting, rows[0], smtp, {"password": "password_encrypted"}),
                                           (WhatsappSetting, rows[1], wa, {"token": "token_encrypted", "secret_key": "secret_key_encrypted"})]:
            if row is None:
                row = model()
                db.add(row)
            for key, value in values.items():
                setattr(row, secrets.get(key, key), encrypt_secret(value) if key in secrets and value else (None if key in secrets else value))
        db.add(AuditLog(accion="import", modulo="medical-dispatches", entidad="communication_settings",
                        detalle="Canales importados desde Laravel; OTP deshabilitado; sin envio de mensajes",
                        datos_despues=json.dumps(summary)))
        db.commit()
    print(json.dumps({"applied": summary, "backup_created": True}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Database/provider exceptions may contain credentials: emit only their type.
        print("Importacion detenida: " + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
