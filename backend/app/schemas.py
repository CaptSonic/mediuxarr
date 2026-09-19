from typing import Literal

from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    plex_url: str = ""
    plex_token_set: bool = False
    mediux_token_set: bool = False
    kometa_asset_dir: str


class SettingsUpdate(BaseModel):
    plex_url: str = ""
    plex_token: str | None = None
    mediux_token: str | None = None
    kometa_asset_dir: str


class ConnectionResult(BaseModel):
    success: bool
    message: str


class LibraryRead(BaseModel):
    id: int
    plex_key: str
    title: str
    media_type: str
    selected: bool


class LibrarySelection(BaseModel):
    library_ids: list[int]


class MediaItemRead(BaseModel):
    id: int
    library_id: int
    library_title: str
    rating_key: str
    media_type: str
    title: str
    year: int | None
    tmdb_id: str | None
    tvdb_id: str | None
    imdb_id: str | None
    media_path: str | None
    asset_name: str
    last_exported_set_id: str | None
    mediux_checked_at: str | None = None


class MediuxRefreshResult(BaseModel):
    checked: int
    available: int


class MediuxAsset(BaseModel):
    id: str
    asset_type: Literal["poster", "background", "season_poster", "titlecard"]
    modified_on: str
    filesize: str | None = None
    src: str | None = None
    blurhash: str | None = None
    language: str | None = None
    season_number: int | None = None
    episode_number: int | None = None
    title: str | None = None
    preview_url: str


class MediuxSet(BaseModel):
    id: str
    title: str
    creator: str
    date_updated: str
    popularity: int = 0
    popularity_global: int = 0
    assets: list[MediuxAsset]


class ExportAssetRequest(BaseModel):
    asset_id: str
    asset_type: Literal["poster", "background", "season_poster", "titlecard"]
    modified_on: str
    season_number: int | None = None
    episode_number: int | None = None


class ExportPlanRequest(BaseModel):
    set_id: str
    assets: list[ExportAssetRequest] = Field(min_length=1)


class ExportPlanEntry(BaseModel):
    asset_id: str
    asset_type: str
    target_path: str
    exists: bool
    action: Literal["create", "replace"]


class ExportPlan(BaseModel):
    media_item_id: int
    set_id: str
    entries: list[ExportPlanEntry]
    requires_confirmation: bool


class ExportExecuteRequest(ExportPlanRequest):
    confirm_overwrite: bool = False


class ExportResultEntry(BaseModel):
    asset_id: str
    target_path: str
    status: Literal["created", "replaced", "unchanged", "failed"]
    message: str | None = None


class ExportResult(BaseModel):
    job_id: int
    status: Literal["completed", "partial", "failed"]
    entries: list[ExportResultEntry]
