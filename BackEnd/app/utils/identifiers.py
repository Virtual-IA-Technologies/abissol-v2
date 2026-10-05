import re

from fastapi import HTTPException


USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not USERNAME_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=422,
            detail="El usuario debe tener entre 3 y 40 caracteres y usar solo letras, números, punto, guion o guion bajo",
        )
    return username


def normalize_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    raw = value.strip()
    digits = "".join(character for character in raw if character.isdigit())
    # Compatibilidad de entrada: +51 999 999 999 se reduce al numero local.
    if raw.startswith("+") and digits.startswith("51") and len(digits) == 11:
        digits = digits[2:]
    if not 7 <= len(digits) <= 9:
        raise HTTPException(status_code=422, detail="El teléfono debe contener solo el número local de 7 a 9 dígitos")
    return digits
