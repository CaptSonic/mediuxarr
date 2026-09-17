from app.db.base import AppSettings
from app.services import settings as settings_service


class FakeSession:
    def __init__(self, row: AppSettings):
        self.row = row

    def get(self, model, key):
        assert model is AppSettings
        assert key == 1
        return self.row


def test_connection_values_uses_environment_mediux_token(monkeypatch):
    row = AppSettings(id=1, kometa_asset_dir="/kometa-assets")
    fake_settings = type("FakeSettings", (), {"mediux_api_token": "environment-token"})()
    monkeypatch.setattr(settings_service, "get_settings", lambda: fake_settings)

    _, _, mediux_token = settings_service.connection_values(FakeSession(row))

    assert mediux_token == "environment-token"


def test_stored_mediux_token_has_precedence(monkeypatch):
    row = AppSettings(
        id=1,
        mediux_token_encrypted="encrypted-token",
        kometa_asset_dir="/kometa-assets",
    )
    fake_settings = type("FakeSettings", (), {"mediux_api_token": "environment-token"})()
    monkeypatch.setattr(settings_service, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(
        settings_service, "decrypt_secret", lambda value: "stored-token" if value else ""
    )

    _, _, mediux_token = settings_service.connection_values(FakeSession(row))

    assert mediux_token == "stored-token"
