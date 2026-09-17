import hashlib
import os
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import ExportJob, MediaItem, utcnow
from app.providers.mediux import MediuxProvider
from app.schemas import (
    ExportAssetRequest,
    ExportPlan,
    ExportPlanEntry,
    ExportResult,
    ExportResultEntry,
)

SUPPORTED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@dataclass
class PreparedAsset:
    request: ExportAssetRequest
    data: bytes
    extension: str
    target: Path
    conflicts: list[Path]


def _safe_asset_name(value: str) -> str:
    value = value.strip().rstrip(". ")
    if not value or value in {".", ".."}:
        raise ValueError("Ungültiger Kometa-Asset-Name")
    if any(char in value for char in '<>:"/\\|?*'):
        raise ValueError("Der Plex-Medienordner enthält ungültige Zeichen für den Asset-Pfad")
    return value


def _stem(asset: ExportAssetRequest) -> str:
    if asset.asset_type == "poster":
        return "poster"
    if asset.asset_type == "background":
        return "background"
    if asset.asset_type == "season_poster" and asset.season_number is not None:
        return f"Season{asset.season_number:02d}"
    if (
        asset.asset_type == "titlecard"
        and asset.season_number is not None
        and asset.episode_number is not None
    ):
        return f"S{asset.season_number:02d}E{asset.episode_number:02d}"
    raise ValueError(f"Unvollständige Zuordnung für Asset {asset.asset_id}")


def _valid_for_item(item: MediaItem, asset: ExportAssetRequest) -> bool:
    if item.media_type == "movie":
        return asset.asset_type in {"poster", "background"}
    if asset.asset_type in {"poster", "background"}:
        return True
    seasons = item.details.get("seasons", {}) if item.details else {}
    season = str(asset.season_number)
    if asset.asset_type == "season_poster":
        return season in seasons
    if asset.asset_type == "titlecard":
        return season in seasons and asset.episode_number in seasons[season]
    return False


def _validate_image(data: bytes, content_type: str) -> str:
    settings = get_settings()
    if not data or len(data) > settings.max_image_bytes:
        raise ValueError("Bild ist leer oder überschreitet das Größenlimit")
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
            detected = Image.MIME.get(image.format or "", "").lower()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("MediUX lieferte keine gültige Bilddatei") from exc
    mime = detected or content_type
    if mime not in MIME_EXTENSIONS:
        raise ValueError(f"Nicht unterstütztes Bildformat: {mime or 'unbekannt'}")
    return MIME_EXTENSIONS[mime]


def _candidate_paths(folder: Path, stem: str) -> list[Path]:
    return [folder / f"{stem}{extension}" for extension in SUPPORTED_EXTENSIONS]


async def prepare_assets(
    item: MediaItem,
    assets: list[ExportAssetRequest],
    provider: MediuxProvider,
    kometa_root: Path,
) -> list[PreparedAsset]:
    folder = kometa_root / _safe_asset_name(item.asset_name)
    prepared: list[PreparedAsset] = []
    for asset in assets:
        if not _valid_for_item(item, asset):
            raise ValueError(f"Asset {asset.asset_id} passt nicht zu den vorhandenen Plex-Medien")
        data, content_type = await provider.download_asset(asset.asset_id, asset.modified_on)
        extension = _validate_image(data, content_type)
        stem = _stem(asset)
        target = folder / f"{stem}{extension}"
        conflicts = [path for path in _candidate_paths(folder, stem) if path.exists()]
        prepared.append(PreparedAsset(asset, data, extension, target, conflicts))
    return prepared


def build_plan(item: MediaItem, set_id: str, prepared: list[PreparedAsset]) -> ExportPlan:
    entries = [
        ExportPlanEntry(
            asset_id=entry.request.asset_id,
            asset_type=entry.request.asset_type,
            target_path=str(entry.target),
            exists=bool(entry.conflicts),
            action="replace" if entry.conflicts else "create",
        )
        for entry in prepared
    ]
    return ExportPlan(
        media_item_id=item.id,
        set_id=set_id,
        entries=entries,
        requires_confirmation=any(entry.exists for entry in entries),
    )


def _atomic_write(entry: PreparedAsset, allow_overwrite: bool) -> ExportResultEntry:
    if entry.conflicts and not allow_overwrite:
        raise FileExistsError(f"Vorhandenes Asset erfordert Bestätigung: {entry.target}")
    entry.target.parent.mkdir(parents=True, exist_ok=True)
    current_hash = hashlib.sha256(entry.data).digest()
    if entry.target.exists() and hashlib.sha256(entry.target.read_bytes()).digest() == current_hash:
        return ExportResultEntry(
            asset_id=entry.request.asset_id,
            target_path=str(entry.target),
            status="unchanged",
            message="Datei ist bereits identisch",
        )
    status = "replaced" if entry.conflicts else "created"
    handle, temp_name = tempfile.mkstemp(prefix=".mediuxarr-", dir=entry.target.parent)
    try:
        with os.fdopen(handle, "wb") as temp_file:
            temp_file.write(entry.data)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        for conflict in entry.conflicts:
            if conflict != entry.target and conflict.exists():
                conflict.unlink()
        os.replace(temp_name, entry.target)
    except Exception:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise
    return ExportResultEntry(
        asset_id=entry.request.asset_id,
        target_path=str(entry.target),
        status=status,
    )


def execute_export(
    db: Session,
    item: MediaItem,
    set_id: str,
    prepared: list[PreparedAsset],
    confirm_overwrite: bool,
) -> ExportResult:
    job = ExportJob(media_item_id=item.id, mediux_set_id=set_id, status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    results: list[ExportResultEntry] = []
    for entry in prepared:
        try:
            results.append(_atomic_write(entry, confirm_overwrite))
        except Exception as exc:
            results.append(
                ExportResultEntry(
                    asset_id=entry.request.asset_id,
                    target_path=str(entry.target),
                    status="failed",
                    message=str(exc),
                )
            )
    failed = sum(result.status == "failed" for result in results)
    status = "failed" if failed == len(results) else "partial" if failed else "completed"
    job.status = status
    job.results = [result.model_dump() for result in results]
    job.completed_at = utcnow()
    item.last_exported_set_id = set_id if status != "failed" else item.last_exported_set_id
    db.commit()
    return ExportResult(job_id=job.id, status=status, entries=results)
