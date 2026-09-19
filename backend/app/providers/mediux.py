from datetime import datetime
from urllib.parse import urlencode

import httpx

from app.schemas import MediuxAsset, MediuxSet

MOVIE_QUERY = """
query getMovieItemSetsByTMDBID($tmdb_id: ID!) {
  movies_by_id(id: $tmdb_id) {
    id
    movie_sets(
      filter: {_or: [
        {movie_poster: {id: {_neq: null}}},
        {movie_backdrop: {id: {_neq: null}}}
      ]}
    ) {
      id set_title date_updated popularity popularity_global
      user_created { username }
      movie_poster { id modified_on filesize src blurhash language { display_name } }
      movie_backdrop { id modified_on filesize src blurhash language { display_name } }
    }
  }
}
"""

SHOW_QUERY = """
query getShowItemSetsByTMDBID($tmdb_id: ID!) {
  shows_by_id(id: $tmdb_id) {
    id
    show_sets(filter: {_or: [
      {show_poster: {id: {_nnull: true}}},
      {show_backdrop: {id: {_nnull: true}}},
      {season_posters: {id: {_nnull: true}}},
      {titlecards: {id: {_nnull: true}}}
    ]}) {
      id set_title date_updated popularity popularity_global
      user_created { username }
      show_poster { id modified_on filesize src blurhash language { display_name } }
      show_backdrop { id modified_on filesize src blurhash language { display_name } }
      season_posters {
        id modified_on filesize src blurhash
        language { display_name }
        season { season_number }
      }
      titlecards {
        id modified_on filesize src blurhash language { display_name }
        episode { episode_title episode_number season_id { season_number } }
      }
    }
  }
}
"""


class MediuxError(RuntimeError):
    pass


class MediuxProvider:
    def __init__(self, api_url: str, token: str, timeout: float = 60):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "mediuxarr/0.1",
            "X-Request": "mediuxarr",
        }

    async def test_connection(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(f"{self.api_url}/users/me", headers=self.headers)
        except httpx.TimeoutException as exc:
            raise MediuxError("Zeitüberschreitung bei der Verbindung zu MediUX") from exc
        except httpx.HTTPError as exc:
            raise MediuxError(f"MediUX konnte nicht erreicht werden: {exc}") from exc
        if response.status_code != 200:
            raise MediuxError(f"MediUX antwortete mit HTTP {response.status_code}")
        return "MediUX-Token ist gültig"

    async def _graphql(self, query: str, variables: dict) -> dict:
        headers = {**self.headers, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.post(
                    f"{self.api_url}/graphql",
                    headers=headers,
                    json={"query": query, "variables": variables},
                )
        except httpx.TimeoutException as exc:
            raise MediuxError("Zeitüberschreitung bei der MediUX-Abfrage") from exc
        except httpx.HTTPError as exc:
            raise MediuxError(f"MediUX konnte nicht erreicht werden: {exc}") from exc
        if response.status_code != 200:
            raise MediuxError(f"MediUX GraphQL antwortete mit HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise MediuxError("MediUX lieferte eine ungültige Antwort") from exc
        if payload.get("errors"):
            message = payload["errors"][0].get("message", "Unbekannter GraphQL-Fehler")
            raise MediuxError(message)
        return payload.get("data", {})

    @staticmethod
    def _version(modified_on: str) -> str:
        normalized = modified_on.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).strftime("%Y%m%d%H%M%S")
        except ValueError:
            return ""

    def asset_url(self, asset_id: str, modified_on: str, quality: str = "thumb") -> str:
        query = {"v": self._version(modified_on)}
        if quality == "thumb":
            query["key"] = "thumb"
        elif quality == "optimized":
            query["key"] = "jpg"
        return f"{self.api_url}/assets/{asset_id}?{urlencode(query)}"

    def _asset(self, raw: dict, asset_type: str) -> MediuxAsset | None:
        if not raw or not raw.get("id"):
            return None
        season_number = None
        episode_number = None
        title = None
        if raw.get("season"):
            season_number = raw["season"].get("season_number")
        if raw.get("episode"):
            episode = raw["episode"]
            title = episode.get("episode_title")
            episode_number = episode.get("episode_number")
            season_number = (episode.get("season_id") or {}).get("season_number")
        modified_on = raw.get("modified_on", "")
        return MediuxAsset(
            id=str(raw["id"]),
            asset_type=asset_type,
            modified_on=modified_on,
            filesize=raw.get("filesize"),
            src=raw.get("src"),
            blurhash=raw.get("blurhash"),
            language=(raw.get("language") or {}).get("display_name"),
            season_number=season_number,
            episode_number=episode_number,
            title=title,
            preview_url=self.asset_url(str(raw["id"]), modified_on, "thumb"),
        )

    def _set(self, raw: dict, media_type: str) -> MediuxSet:
        assets: list[MediuxAsset] = []
        fields = (
            [("movie_poster", "poster"), ("movie_backdrop", "background")]
            if media_type == "movie"
            else [
                ("show_poster", "poster"),
                ("show_backdrop", "background"),
                ("season_posters", "season_poster"),
                ("titlecards", "titlecard"),
            ]
        )
        for field, asset_type in fields:
            for raw_asset in raw.get(field) or []:
                asset = self._asset(raw_asset, asset_type)
                if asset:
                    assets.append(asset)
        return MediuxSet(
            id=str(raw["id"]),
            title=raw.get("set_title") or "Unbenanntes Set",
            creator=(raw.get("user_created") or {}).get("username") or "Unbekannt",
            date_updated=raw.get("date_updated", ""),
            popularity=raw.get("popularity") or 0,
            popularity_global=raw.get("popularity_global") or 0,
            assets=assets,
        )

    async def sets_for_item(self, media_type: str, tmdb_id: str) -> list[MediuxSet]:
        if media_type == "movie":
            data = await self._graphql(MOVIE_QUERY, {"tmdb_id": tmdb_id})
            item = data.get("movies_by_id") or {}
            raw_sets = item.get("movie_sets") or []
        else:
            data = await self._graphql(SHOW_QUERY, {"tmdb_id": tmdb_id})
            item = data.get("shows_by_id") or {}
            raw_sets = item.get("show_sets") or []
        if item and str(item.get("id")) != str(tmdb_id):
            raise MediuxError("MediUX lieferte eine abweichende TMDb-ID")
        return [self._set(raw_set, media_type) for raw_set in raw_sets]

    async def download_asset(self, asset_id: str, modified_on: str) -> tuple[bytes, str]:
        url = self.asset_url(asset_id, modified_on, "original")
        headers = {**self.headers, "Accept": "image/*"}
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
        if response.status_code != 200:
            raise MediuxError(f"Bilddownload antwortete mit HTTP {response.status_code}")
        return response.content, response.headers.get("content-type", "").split(";", 1)[0].lower()
