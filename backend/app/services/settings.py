from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret
from app.db.base import AppSettings
from app.schemas import SettingsRead, SettingsUpdate


def get_or_create_settings(db: Session) -> AppSettings:
    settings = db.get(AppSettings, 1)
    if settings is None:
        defaults = get_settings()
        settings = AppSettings(id=1, kometa_asset_dir=str(defaults.kometa_asset_dir.resolve()))
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def read_settings(db: Session) -> SettingsRead:
    row = get_or_create_settings(db)
    configured_mediux_token = decrypt_secret(row.mediux_token_encrypted)
    return SettingsRead(
        plex_url=row.plex_url,
        plex_token_set=bool(decrypt_secret(row.plex_token_encrypted)),
        mediux_token_set=bool(configured_mediux_token or get_settings().mediux_api_token),
        kometa_asset_dir=row.kometa_asset_dir,
    )


def update_settings(db: Session, payload: SettingsUpdate) -> SettingsRead:
    row = get_or_create_settings(db)
    row.plex_url = payload.plex_url.strip().rstrip("/")
    row.kometa_asset_dir = str(Path(payload.kometa_asset_dir).expanduser().resolve())
    if payload.plex_token is not None and payload.plex_token.strip():
        row.plex_token_encrypted = encrypt_secret(payload.plex_token.strip())
    if payload.mediux_token is not None and payload.mediux_token.strip():
        row.mediux_token_encrypted = encrypt_secret(payload.mediux_token.strip())
    db.commit()
    return read_settings(db)


def connection_values(db: Session) -> tuple[AppSettings, str, str]:
    row = get_or_create_settings(db)
    stored_mediux_token = decrypt_secret(row.mediux_token_encrypted)
    return (
        row,
        decrypt_secret(row.plex_token_encrypted),
        stored_mediux_token or get_settings().mediux_api_token.strip(),
    )
