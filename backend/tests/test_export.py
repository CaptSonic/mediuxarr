from pathlib import Path

from PIL import Image

from app.db.base import MediaItem
from app.schemas import ExportAssetRequest
from app.services.export import PreparedAsset, _atomic_write, _safe_asset_name, _stem, build_plan


def asset(asset_type: str, season: int | None = None, episode: int | None = None):
    return ExportAssetRequest(
        asset_id="asset-1",
        asset_type=asset_type,
        modified_on="2026-09-17T12:00:00Z",
        season_number=season,
        episode_number=episode,
    )


def test_kometa_stems():
    assert _stem(asset("poster")) == "poster"
    assert _stem(asset("background")) == "background"
    assert _stem(asset("season_poster", 0)) == "Season00"
    assert _stem(asset("season_poster", 4)) == "Season04"
    assert _stem(asset("titlecard", 2, 7)) == "S02E07"


def test_asset_name_rejects_path_traversal():
    for value in ("..", "show/name", "show\\name", "bad:name"):
        try:
            _safe_asset_name(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{value} should be rejected")


def test_plan_detects_existing_alternative_extension(tmp_path: Path):
    folder = tmp_path / "Example (2024)"
    folder.mkdir()
    conflict = folder / "poster.png"
    conflict.write_bytes(b"old")
    request = asset("poster")
    prepared = PreparedAsset(request, b"new", ".jpg", folder / "poster.jpg", [conflict])
    item = MediaItem(
        id=1,
        library_id=1,
        rating_key="1",
        media_type="movie",
        title="Example",
        asset_name="Example (2024)",
    )
    plan = build_plan(item, "set-1", [prepared])
    assert plan.requires_confirmation is True
    assert plan.entries[0].action == "replace"


def test_atomic_write_replaces_other_extension(tmp_path: Path):
    folder = tmp_path / "Example (2024)"
    folder.mkdir()
    old = folder / "poster.png"
    old.write_bytes(b"old")
    image_path = tmp_path / "source.jpg"
    Image.new("RGB", (4, 4), "purple").save(image_path)
    request = asset("poster")
    target = folder / "poster.jpg"
    prepared = PreparedAsset(request, image_path.read_bytes(), ".jpg", target, [old])
    result = _atomic_write(prepared, True)
    assert result.status == "replaced"
    assert target.exists()
    assert not old.exists()
