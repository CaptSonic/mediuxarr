from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.base import Library, MediaItem
from app.db.session import get_db
from app.providers.mediux import MediuxError, MediuxProvider
from app.providers.plex import PlexProvider
from app.schemas import (
    ConnectionResult,
    ExportExecuteRequest,
    ExportPlan,
    ExportPlanRequest,
    ExportResult,
    LibraryRead,
    LibrarySelection,
    MediaItemRead,
    MediuxSet,
    SettingsRead,
    SettingsUpdate,
)
from app.services.export import build_plan, execute_export, prepare_assets
from app.services.scan import scan_selected_libraries, sync_libraries
from app.services.settings import connection_values, read_settings, update_settings

router = APIRouter(prefix="/api")


def _plex_provider(db: Session) -> PlexProvider:
    row, plex_token, _ = connection_values(db)
    if not row.plex_url or not plex_token:
        raise HTTPException(400, "Plex-Verbindung ist nicht vollständig konfiguriert")
    return PlexProvider(row.plex_url, plex_token)


def _mediux_provider(db: Session) -> MediuxProvider:
    _, _, mediux_token = connection_values(db)
    if not mediux_token:
        raise HTTPException(400, "MediUX-Token ist nicht konfiguriert")
    settings = get_settings()
    return MediuxProvider(settings.mediux_api_url, mediux_token, settings.request_timeout)


def _media_response(item: MediaItem) -> MediaItemRead:
    return MediaItemRead(
        id=item.id,
        library_id=item.library_id,
        library_title=item.library.title,
        rating_key=item.rating_key,
        media_type=item.media_type,
        title=item.title,
        year=item.year,
        tmdb_id=item.tmdb_id,
        tvdb_id=item.tvdb_id,
        imdb_id=item.imdb_id,
        media_path=item.media_path,
        asset_name=item.asset_name,
        last_exported_set_id=item.last_exported_set_id,
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/settings", response_model=SettingsRead)
def settings_get(db: Session = Depends(get_db)) -> SettingsRead:
    return read_settings(db)


@router.put("/settings", response_model=SettingsRead)
def settings_put(payload: SettingsUpdate, db: Session = Depends(get_db)) -> SettingsRead:
    return update_settings(db, payload)


@router.post("/settings/test-plex", response_model=ConnectionResult)
async def test_plex(db: Session = Depends(get_db)) -> ConnectionResult:
    try:
        message = await _plex_provider(db).test_connection()
        return ConnectionResult(success=True, message=message)
    except Exception as exc:
        raise HTTPException(502, f"Plex-Verbindung fehlgeschlagen: {exc}") from exc


@router.post("/settings/test-mediux", response_model=ConnectionResult)
async def test_mediux(db: Session = Depends(get_db)) -> ConnectionResult:
    try:
        message = await _mediux_provider(db).test_connection()
        return ConnectionResult(success=True, message=message)
    except Exception as exc:
        raise HTTPException(502, f"MediUX-Verbindung fehlgeschlagen: {exc}") from exc


@router.post("/libraries/sync", response_model=list[LibraryRead])
async def libraries_sync(db: Session = Depends(get_db)) -> list[LibraryRead]:
    try:
        libraries = await sync_libraries(db, _plex_provider(db))
    except Exception as exc:
        raise HTTPException(502, f"Plex-Bibliotheken konnten nicht geladen werden: {exc}") from exc
    return [LibraryRead.model_validate(library, from_attributes=True) for library in libraries]


@router.get("/libraries", response_model=list[LibraryRead])
def libraries_get(db: Session = Depends(get_db)) -> list[LibraryRead]:
    libraries = db.scalars(select(Library).order_by(Library.title)).all()
    return [LibraryRead.model_validate(library, from_attributes=True) for library in libraries]


@router.put("/libraries/selection", response_model=list[LibraryRead])
def libraries_select(payload: LibrarySelection, db: Session = Depends(get_db)) -> list[LibraryRead]:
    libraries = list(db.scalars(select(Library)).all())
    selected = set(payload.library_ids)
    for library in libraries:
        library.selected = library.id in selected
    db.commit()
    return [LibraryRead.model_validate(library, from_attributes=True) for library in libraries]


@router.post("/scan")
async def scan(db: Session = Depends(get_db)) -> dict[str, int | str]:
    try:
        count = await scan_selected_libraries(db, _plex_provider(db))
        return {"status": "completed", "items": count}
    except Exception as exc:
        raise HTTPException(502, f"Bibliotheksscan fehlgeschlagen: {exc}") from exc


@router.get("/media", response_model=list[MediaItemRead])
def media_get(
    search: str = "",
    media_type: str | None = None,
    library_id: int | None = None,
    only_matched: bool = False,
    db: Session = Depends(get_db),
) -> list[MediaItemRead]:
    query = select(MediaItem).options(selectinload(MediaItem.library)).join(MediaItem.library)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.where(or_(MediaItem.title.ilike(term), MediaItem.asset_name.ilike(term)))
    if media_type:
        query = query.where(MediaItem.media_type == media_type)
    if library_id:
        query = query.where(MediaItem.library_id == library_id)
    if only_matched:
        query = query.where(MediaItem.tmdb_id.is_not(None))
    items = db.scalars(query.order_by(MediaItem.title, MediaItem.year)).all()
    return [_media_response(item) for item in items]


@router.get("/media/{media_item_id}", response_model=MediaItemRead)
def media_item_get(media_item_id: int, db: Session = Depends(get_db)) -> MediaItemRead:
    item = db.scalar(
        select(MediaItem)
        .options(selectinload(MediaItem.library))
        .where(MediaItem.id == media_item_id)
    )
    if not item:
        raise HTTPException(404, "Medium wurde nicht gefunden")
    return _media_response(item)


@router.get("/media/{media_item_id}/sets", response_model=list[MediuxSet])
async def media_sets(media_item_id: int, db: Session = Depends(get_db)) -> list[MediuxSet]:
    item = db.get(MediaItem, media_item_id)
    if not item:
        raise HTTPException(404, "Medium wurde nicht gefunden")
    if not item.tmdb_id:
        raise HTTPException(422, "Das Medium besitzt keine TMDb-ID")
    try:
        sets = await _mediux_provider(db).sets_for_item(item.media_type, item.tmdb_id)
    except MediuxError as exc:
        raise HTTPException(502, str(exc)) from exc
    for artwork_set in sets:
        for asset in artwork_set.assets:
            asset.preview_url = (
                f"/api/mediux/assets/{quote(asset.id, safe='')}/preview"
                f"?modified_on={quote(asset.modified_on, safe='')}"
            )
    return sets


@router.get("/mediux/assets/{asset_id}/preview")
async def asset_preview(
    asset_id: str,
    modified_on: str = Query(...),
    db: Session = Depends(get_db),
) -> Response:
    provider = _mediux_provider(db)
    url = provider.asset_url(asset_id, modified_on, "thumb")
    try:
        import httpx

        async with httpx.AsyncClient(timeout=get_settings().request_timeout) as client:
            response = await client.get(url, headers={**provider.headers, "Accept": "image/*"})
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(502, "Vorschaubild konnte nicht geladen werden") from exc
    media_type = response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
    return Response(
        response.content,
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


async def _prepare(
    media_item_id: int,
    payload: ExportPlanRequest,
    db: Session,
):
    item = db.get(MediaItem, media_item_id)
    if not item:
        raise HTTPException(404, "Medium wurde nicht gefunden")
    row, _, _ = connection_values(db)
    root = Path(row.kometa_asset_dir).expanduser().resolve()
    try:
        prepared = await prepare_assets(item, payload.assets, _mediux_provider(db), root)
    except (ValueError, MediuxError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return item, prepared


@router.post("/media/{media_item_id}/export/plan", response_model=ExportPlan)
async def export_plan(
    media_item_id: int,
    payload: ExportPlanRequest,
    db: Session = Depends(get_db),
) -> ExportPlan:
    item, prepared = await _prepare(media_item_id, payload, db)
    return build_plan(item, payload.set_id, prepared)


@router.post("/media/{media_item_id}/export", response_model=ExportResult)
async def export_execute(
    media_item_id: int,
    payload: ExportExecuteRequest,
    db: Session = Depends(get_db),
) -> ExportResult:
    item, prepared = await _prepare(media_item_id, payload, db)
    plan = build_plan(item, payload.set_id, prepared)
    if plan.requires_confirmation and not payload.confirm_overwrite:
        raise HTTPException(409, "Vorhandene Kometa-Assets erfordern eine Bestätigung")
    return execute_export(db, item, payload.set_id, prepared, payload.confirm_overwrite)
