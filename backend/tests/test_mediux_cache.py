from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base, Library, MediaItem, MediuxAvailabilityCache
from app.schemas import MediuxAsset, MediuxSet
from app.services.mediux_cache import (
    items_needing_refresh,
    refresh_media_availability,
    sets_for_item,
)


class FakeMediuxProvider:
    def __init__(self, responses: dict[str, list[MediuxSet]]):
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    async def sets_for_item(self, media_type: str, tmdb_id: str) -> list[MediuxSet]:
        self.calls.append((media_type, tmdb_id))
        return self.responses.get(tmdb_id, [])


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        library = Library(id=1, plex_key="1", title="Test", media_type="movie", selected=True)
        session.add(library)
        session.add_all(
            [
                MediaItem(
                    id=1,
                    library_id=1,
                    rating_key="movie-1",
                    media_type="movie",
                    title="Available",
                    tmdb_id="100",
                    asset_name="Available (2026)",
                ),
                MediaItem(
                    id=2,
                    library_id=1,
                    rating_key="movie-2",
                    media_type="movie",
                    title="Unavailable",
                    tmdb_id="200",
                    asset_name="Unavailable (2026)",
                ),
                MediaItem(
                    id=3,
                    library_id=1,
                    rating_key="movie-3",
                    media_type="movie",
                    title="Unmatched",
                    asset_name="Unmatched (2026)",
                ),
            ]
        )
        session.commit()
        yield session


def artwork_set() -> MediuxSet:
    return MediuxSet(
        id="set-1",
        title="Set",
        creator="artist",
        date_updated="2026-09-19T12:00:00Z",
        assets=[
            MediuxAsset(
                id="poster-1",
                asset_type="poster",
                modified_on="2026-09-19T12:00:00Z",
                preview_url="https://example.test/poster-1",
            )
        ],
    )


@pytest.mark.asyncio
async def test_refresh_caches_positive_and_negative_results(db: Session):
    provider = FakeMediuxProvider({"100": [artwork_set()]})
    items = list(db.query(MediaItem).order_by(MediaItem.id))

    checked = await refresh_media_availability(db, provider, items)

    assert checked == 2
    assert provider.calls == [("movie", "100"), ("movie", "200")]
    assert db.get(MediuxAvailabilityCache, 1).has_assets is True
    assert db.get(MediuxAvailabilityCache, 2).has_assets is False
    assert db.get(MediuxAvailabilityCache, 3) is None


@pytest.mark.asyncio
async def test_fresh_cache_is_reused_for_sets(db: Session):
    cached = MediuxAvailabilityCache(
        media_item_id=1,
        media_type="movie",
        tmdb_id="100",
        has_assets=True,
        sets=[artwork_set().model_dump(mode="json")],
        checked_at=datetime.now(UTC),
    )
    db.add(cached)
    db.commit()
    provider = FakeMediuxProvider({})

    sets = await sets_for_item(db, provider, db.get(MediaItem, 1))

    assert provider.calls == []
    assert sets[0].id == "set-1"
    assert sets[0].assets[0].id == "poster-1"


def test_fresh_cache_does_not_need_provider_refresh(db: Session):
    db.add(
        MediuxAvailabilityCache(
            media_item_id=1,
            media_type="movie",
            tmdb_id="100",
            has_assets=True,
            sets=[artwork_set().model_dump(mode="json")],
            checked_at=datetime.now(UTC),
        )
    )
    db.commit()

    assert items_needing_refresh(db, [db.get(MediaItem, 1)]) == []


@pytest.mark.asyncio
async def test_forced_refresh_replaces_cached_availability(db: Session):
    db.add(
        MediuxAvailabilityCache(
            media_item_id=1,
            media_type="movie",
            tmdb_id="100",
            has_assets=True,
            sets=[artwork_set().model_dump(mode="json")],
            checked_at=datetime.now(UTC),
        )
    )
    db.commit()
    provider = FakeMediuxProvider({"100": []})

    checked = await refresh_media_availability(db, provider, [db.get(MediaItem, 1)], force=True)

    cache = db.get(MediuxAvailabilityCache, 1)
    assert checked == 1
    assert cache.has_assets is False
    assert cache.sets == []
