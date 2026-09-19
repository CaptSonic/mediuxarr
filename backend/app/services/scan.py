from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.base import Library, MediaItem, MediuxAvailabilityCache
from app.providers.plex import PlexProvider


async def sync_libraries(db: Session, provider: PlexProvider) -> list[Library]:
    remote = await provider.libraries()
    known = {library.plex_key: library for library in db.scalars(select(Library)).all()}
    remote_keys: set[str] = set()
    for entry in remote:
        remote_keys.add(entry["plex_key"])
        library = known.get(entry["plex_key"])
        if library is None:
            library = Library(**entry)
            db.add(library)
        else:
            library.title = entry["title"]
            library.media_type = entry["media_type"]
    for key, library in known.items():
        if key not in remote_keys:
            db.delete(library)
    db.commit()
    return list(db.scalars(select(Library).order_by(Library.title)).all())


async def scan_selected_libraries(db: Session, provider: PlexProvider) -> int:
    libraries = list(db.scalars(select(Library).where(Library.selected.is_(True))).all())
    total = 0
    for library in libraries:
        scanned = await provider.scan_library(library.plex_key)
        existing = {
            item.rating_key: item
            for item in db.scalars(
                select(MediaItem).where(MediaItem.library_id == library.id)
            ).all()
        }
        seen: set[str] = set()
        for data in scanned:
            seen.add(data["rating_key"])
            item = existing.get(data["rating_key"])
            if item is None:
                item = MediaItem(library_id=library.id, **data)
                db.add(item)
            else:
                for key, value in data.items():
                    setattr(item, key, value)
                item.updated_at = datetime.now(UTC)
            total += 1
        stale_ids = [item.id for key, item in existing.items() if key not in seen]
        if stale_ids:
            db.execute(
                delete(MediuxAvailabilityCache).where(
                    MediuxAvailabilityCache.media_item_id.in_(stale_ids)
                )
            )
            db.execute(delete(MediaItem).where(MediaItem.id.in_(stale_ids)))
        library.scanned_at = datetime.now(UTC)
        db.commit()
    return total
