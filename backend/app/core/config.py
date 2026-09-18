from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_prefix="MEDIUXARR_",
        extra="ignore",
    )

    app_name: str = "mediuxarr"
    config_dir: Path = Path("./data")
    kometa_asset_dir: Path = Path("./kometa-assets")
    frontend_dir: Path = Path("../frontend/dist")
    secret_key: str = ""
    cors_origins: str = "http://localhost:5173"
    mediux_api_token: str = ""
    mediux_api_url: str = "https://images.mediux.io"
    request_timeout: float = Field(default=60.0, ge=5, le=300)
    max_image_bytes: int = Field(default=30 * 1024 * 1024, ge=1024)

    @property
    def database_url(self) -> str:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.config_dir / 'mediuxarr.db').resolve().as_posix()}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
