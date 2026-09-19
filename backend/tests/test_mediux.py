import httpx
import pytest

from app.providers.mediux import MediuxError, MediuxProvider


def test_image_url_contains_stable_version_and_quality():
    provider = MediuxProvider("https://images.mediux.io", "secret")
    url = provider.asset_url("abc", "2026-09-17T12:34:56Z", "thumb")
    assert url == "https://images.mediux.io/assets/abc?v=20260917123456&key=thumb"


def test_show_assets_are_normalized():
    provider = MediuxProvider("https://images.mediux.io", "secret")
    result = provider._set(
        {
            "id": "set-1",
            "set_title": "Example",
            "date_updated": "2026-09-17T12:00:00Z",
            "user_created": {"username": "artist"},
            "show_poster": [],
            "show_backdrop": [],
            "season_posters": [
                {
                    "id": "sp",
                    "modified_on": "2026-09-17T12:00:00Z",
                    "season": {"season_number": 1},
                }
            ],
            "titlecards": [
                {
                    "id": "tc",
                    "modified_on": "2026-09-17T12:00:00Z",
                    "episode": {
                        "episode_title": "Pilot",
                        "episode_number": 1,
                        "season_id": {"season_number": 1},
                    },
                }
            ],
        },
        "show",
    )
    assert result.assets[0].asset_type == "season_poster"
    assert result.assets[0].season_number == 1
    assert result.assets[1].asset_type == "titlecard"
    assert result.assets[1].episode_number == 1


def test_nullable_mediux_dates_are_normalized():
    provider = MediuxProvider("https://images.mediux.io", "secret")

    result = provider._set(
        {
            "id": "set-with-null-dates",
            "set_title": "Nullable dates",
            "date_updated": None,
            "movie_poster": [
                {
                    "id": "poster-with-null-date",
                    "modified_on": None,
                }
            ],
            "movie_backdrop": [],
        },
        "movie",
    )

    assert result.date_updated == ""
    assert result.assets[0].modified_on == ""
    assert result.assets[0].preview_url.endswith("/assets/poster-with-null-date?v=&key=thumb")


@pytest.mark.asyncio
async def test_graphql_timeout_becomes_mediux_error(monkeypatch):
    async def post(*args, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    provider = MediuxProvider("https://images.mediux.io", "secret")

    with pytest.raises(MediuxError, match="Zeitüberschreitung"):
        await provider.sets_for_item("movie", "100")


@pytest.mark.asyncio
async def test_graphql_invalid_json_becomes_mediux_error(monkeypatch):
    async def post(*args, **kwargs):
        return httpx.Response(200, content=b"not-json")

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    provider = MediuxProvider("https://images.mediux.io", "secret")

    with pytest.raises(MediuxError, match="ungültige Antwort"):
        await provider.sets_for_item("movie", "100")


@pytest.mark.asyncio
async def test_graphql_uses_partial_data_when_a_field_is_not_accessible(monkeypatch):
    async def post(*args, **kwargs):
        return httpx.Response(
            200,
            json={
                "data": {"movies_by_id": None},
                "errors": [
                    {
                        "message": "You don't have permission to access this.",
                        "path": ["movies_by_id"],
                    }
                ],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    provider = MediuxProvider("https://images.mediux.io", "secret")

    assert await provider.sets_for_item("movie", "100") == []


@pytest.mark.asyncio
async def test_graphql_permission_error_without_data_remains_fatal(monkeypatch):
    async def post(*args, **kwargs):
        return httpx.Response(
            200,
            json={
                "data": None,
                "errors": [{"message": "You don't have permission to access this."}],
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    provider = MediuxProvider("https://images.mediux.io", "secret")

    with pytest.raises(MediuxError, match="permission"):
        await provider.sets_for_item("movie", "100")
