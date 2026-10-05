import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from ..models.settings import WhatsappSetting
from ..utils.secrets import decrypt_secret


class WhatsappNotConfigured(RuntimeError):
    pass


class WhatsappDeliveryError(RuntimeError):
    pass


def _safe_provider_message(result, *secrets: str) -> str:
    if not isinstance(result, dict):
        return ""
    message = str(result.get("message") or "").strip()
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[PROTEGIDO]")
    return message[:180]


def get_whatsapp_setting(db: Session) -> WhatsappSetting:
    setting = db.query(WhatsappSetting).order_by(WhatsappSetting.id).first()
    if not setting or not setting.is_active:
        raise WhatsappNotConfigured("Configura y activa WhatsApp antes de enviar mensajes")
    if not setting.token_encrypted or not setting.secret_key_encrypted:
        raise WhatsappNotConfigured("Faltan el token o la clave secreta de WhatsApp")
    return setting


def normalize_whatsapp_phone(phone: str, country_code: str) -> str:
    digits = "".join(character for character in phone if character.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith(country_code) and len(digits) > len(country_code) + 6:
        return digits
    if 7 <= len(digits) <= 9:
        return country_code + digits
    raise ValueError("Ingresa un numero local de 7 a 9 digitos o uno internacional con codigo de pais")


def send_whatsapp(db: Session, phone: str, message: str) -> dict:
    setting = get_whatsapp_setting(db)
    target = normalize_whatsapp_phone(phone, setting.country_code)
    try:
        token = decrypt_secret(setting.token_encrypted)
        secret_key = decrypt_secret(setting.secret_key_encrypted)
    except (RuntimeError, UnicodeError, ValueError) as exc:
        raise WhatsappNotConfigured(
            "No se pudieron leer las credenciales de WhatsApp; vuelve a guardar el token y la clave secreta"
        ) from exc
    endpoint_path = urlparse(setting.endpoint).path.rstrip("/").lower()
    if endpoint_path.endswith("/api/v2/send-message"):
        payload = json.dumps({"data": [{"phone": target, "message": message}]}).encode("utf-8")
        content_type = "application/json"
    elif endpoint_path.endswith("/api/send-message"):
        payload = urlencode({
            "phone": target,
            "message": message,
            "flag": "instant",
            "priority": "high",
        }).encode("utf-8")
        content_type = "application/x-www-form-urlencoded"
    else:
        raise WhatsappNotConfigured(
            "El endpoint debe terminar en /api/send-message o /api/v2/send-message"
        )
    request = Request(
        setting.endpoint,
        data=payload,
        headers={
            "Authorization": f"{token}.{secret_key}",
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "ABISSOL-V4/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
            result = json.loads(raw) if raw else {}
    except HTTPError as exc:
        try:
            error_result = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            error_result = {}
        provider_message = _safe_provider_message(error_result, token, secret_key, f"{token}.{secret_key}")
        detail = f": {provider_message}" if provider_message else ""
        raise WhatsappDeliveryError(f"WhatsApp rechazo la solicitud (HTTP {exc.code}){detail}") from exc
    except (URLError, OSError) as exc:
        raise WhatsappDeliveryError("No se pudo conectar con el proveedor de WhatsApp") from exc
    except (TimeoutError, json.JSONDecodeError, UnicodeError) as exc:
        raise WhatsappDeliveryError("El proveedor de WhatsApp no devolvio una respuesta valida") from exc

    if isinstance(result, dict) and result.get("status") in (False, "false", 0, "0"):
        provider_message = _safe_provider_message(result, token, secret_key, f"{token}.{secret_key}")
        detail = f": {provider_message}" if provider_message else ""
        raise WhatsappDeliveryError(f"El proveedor de WhatsApp rechazo el mensaje{detail}")
    return result if isinstance(result, dict) else {"result": result}
