import base64
import hashlib
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _secret_key() -> str:
    settings = get_settings()
    configured = settings.secret_key.strip()
    if configured:
        return configured

    settings.config_dir.mkdir(parents=True, exist_ok=True)
    key_path = settings.config_dir / ".secret_key"
    try:
        return key_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        generated = secrets.token_urlsafe(48)
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
                key_file.write(generated)
            return generated
        except FileExistsError:
            return key_path.read_text(encoding="utf-8").strip()


def _fernet() -> Fernet:
    secret = _secret_key().encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
