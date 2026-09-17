from app.providers.mediux import MediuxProvider


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
