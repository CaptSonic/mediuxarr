from pathlib import Path

from app.core import security


def test_secret_key_is_generated_once(monkeypatch, tmp_path: Path):
    settings = type("FakeSettings", (), {"secret_key": "", "config_dir": tmp_path})()
    monkeypatch.setattr(security, "get_settings", lambda: settings)

    first = security._secret_key()
    second = security._secret_key()

    assert first == second
    assert len(first) >= 48
    assert (tmp_path / ".secret_key").read_text(encoding="utf-8") == first


def test_configured_secret_key_takes_precedence(monkeypatch, tmp_path: Path):
    settings = type(
        "FakeSettings",
        (),
        {"secret_key": "configured-key", "config_dir": tmp_path},
    )()
    monkeypatch.setattr(security, "get_settings", lambda: settings)

    assert security._secret_key() == "configured-key"
    assert not (tmp_path / ".secret_key").exists()
