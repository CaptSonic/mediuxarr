import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.base import MediaItem, MediuxAvailabilityCache
from app.providers.mediux import MediuxProvider
from app.schemas import MediuxSet


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def cache_is_fresh(cache: MediuxAvailabilityCache, now: datetime | None = None) -> bool:
    max_age = timedelta(hours=get_settings().mediux_cache_hours)
    return (now or datetime.now(UTC)) - _as_utc(cache.checked_at) < max_age


def cached_sets(cache: MediuxAvailabilityCache) -> list[MediuxSet]:
    return [MediuxSet.model_validate(entry) for entry in cache.sets]


def items_needing_refresh(
    db: Session,
    items: list[MediaItem],
    *,
    force: bool = False,
) -> list[MediaItem]:
    eligible = [item for item in items if item.tmdb_id]
    if not eligible:
        return []
    caches = {
        cache.media_item_id: cache
        for cache in db.scalars(
            select(MediuxAvailabilityCache).where(
                MediuxAvailabilityCache.media_item_id.in_([item.id for item in eligible])
            )
        ).all()
    }
    return [
        item
        for item in eligible
        if force
        or item.id not in caches
        or caches[item.id].tmdb_id != item.tmdb_id
        or caches[item.id].media_type != item.media_type
        or not cache_is_fresh(caches[item.id])
    ]


async def refresh_media_availability(
    db: Session,
    provider: MediuxProvider,
    items: list[MediaItem],
    *,
    force: bool = False,
) -> int:
    pending = items_needing_refresh(db, items, force=force)
    caches = {
        cache.media_item_id: cache
        for cache in db.scalars(
            select(MediuxAvailabilityCache).where(
                MediuxAvailabilityCache.media_item_id.in_([item.id for item in pending])
            )
        ).all()
    }
    semaphore = asyncio.Semaphore(get_settings().mediux_refresh_concurrency)

    async def fetch(item: MediaItem) -> tuple[MediaItem, list[MediuxSet]]:
        async with semaphore:
            sets = await provider.sets_for_item(item.media_type, item.tmdb_id or "")
            return item, [artwork_set for artwork_set in sets if artwork_set.assets]

    results = await asyncio.gather(*(fetch(item) for item in pending))
    checked_at = datetime.now(UTC)
    for item, sets in results:
        cache = caches.get(item.id)
        if cache is None:
            cache = MediuxAvailabilityCache(media_item_id=item.id)
            db.add(cache)
        cache.media_type = item.media_type
        cache.tmdb_id = item.tmdb_id or ""
        cache.has_assets = bool(sets)
        cache.sets = [artwork_set.model_dump(mode="json") for artwork_set in sets]
        cache.checked_at = checked_at
    if results:
        db.commit()
    return len(results)


async def sets_for_item(
    db: Session,
    provider: MediuxProvider,
    item: MediaItem,
) -> list[MediuxSet]:
    cache = db.get(MediuxAvailabilityCache, item.id)
    if (
        cache is None
        or cache.tmdb_id != item.tmdb_id
        or cache.media_type != item.media_type
        or not cache_is_fresh(cache)
    ):
        await refresh_media_availability(db, provider, [item], force=True)
        cache = db.get(MediuxAvailabilityCache, item.id)
    return cached_sets(cache) if cache else []
