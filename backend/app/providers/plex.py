import asyncio
import re
from pathlib import PurePosixPath
from typing import Any

from plexapi.server import PlexServer

GUID_RE = re.compile(r"^(?P<provider>[a-zA-Z0-9_]+)://(?P<id>.+)$")


def _guid_map(item: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    for guid in getattr(item, "guids", []) or []:
        value = getattr(guid, "id", "")
        match = GUID_RE.match(value)
        if match:
            provider = match.group("provider").lower()
            if provider == "themoviedb":
                provider = "tmdb"
            result[provider] = match.group("id")
    return result


def _first_media_file(item: Any) -> str | None:
    try:
        return str(item.media[0].parts[0].file)
    except (AttributeError, IndexError, TypeError):
        return None


def _path_name(value: str) -> str:
    return PurePosixPath(value.replace("\\", "/")).name


def _fallback_asset_name(title: str, year: int | None) -> str:
    return f"{title} ({year})" if year else title


def _asset_name(item: Any, media_type: str, media_path: str | None) -> str:
    if media_type == "movie" and media_path:
        parent = PurePosixPath(media_path.replace("\\", "/")).parent.name
        if parent:
            return parent
    if media_type == "show":
        locations = getattr(item, "locations", []) or []
        if locations:
            name = _path_name(str(locations[0]))
            if name:
                return name
    return _fallback_asset_name(item.title, getattr(item, "year", None))


class PlexProvider:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _connect(self) -> PlexServer:
        return PlexServer(self.base_url, self.token, timeout=30)

    async def test_connection(self) -> str:
        def run() -> str:
            server = self._connect()
            return f"Verbunden mit {server.friendlyName} ({server.version})"

        return await asyncio.to_thread(run)

    async def libraries(self) -> list[dict[str, str]]:
        def run() -> list[dict[str, str]]:
            server = self._connect()
            return [
                {"plex_key": str(section.key), "title": section.title, "media_type": section.type}
                for section in server.library.sections()
                if section.type in {"movie", "show"}
            ]

        return await asyncio.to_thread(run)

    async def scan_library(self, plex_key: str) -> list[dict[str, Any]]:
        def run() -> list[dict[str, Any]]:
            server = self._connect()
            section = server.library.sectionByID(int(plex_key))
            results: list[dict[str, Any]] = []
            for item in section.all():
                item.reload(includeGuids=1)
                media_type = item.type
                guids = _guid_map(item)
                details: dict[str, Any] = {}
                media_path: str | None = None
                if media_type == "movie":
                    media_path = _first_media_file(item)
                elif media_type == "show":
                    locations = getattr(item, "locations", []) or []
                    media_path = str(locations[0]) if locations else None
                    seasons: dict[str, list[int]] = {}
                    for episode in item.episodes():
                        season_number = int(getattr(episode, "parentIndex", 0))
                        episode_number = int(getattr(episode, "index", 0))
                        seasons.setdefault(str(season_number), []).append(episode_number)
                    details["seasons"] = {
                        number: sorted(set(episodes)) for number, episodes in seasons.items()
                    }
                results.append(
                    {
                        "rating_key": str(item.ratingKey),
                        "media_type": media_type,
                        "title": item.title,
                        "year": getattr(item, "year", None),
                        "tmdb_id": guids.get("tmdb"),
                        "tvdb_id": guids.get("tvdb"),
                        "imdb_id": guids.get("imdb"),
                        "media_path": media_path,
                        "asset_name": _asset_name(item, media_type, media_path),
                        "details": details,
                    }
                )
            return results

        return await asyncio.to_thread(run)
