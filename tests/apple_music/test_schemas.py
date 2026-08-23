from datetime import date

import pytest
from pydantic import ValidationError

from amdl.apple_music.schemas import (
    AppleMusicAlbumAttributes,
    AppleMusicLicenseResponse,
    AppleMusicPlaybackResponse,
    AppleMusicTrackAttributes,
)


class TestAttributeValidators:
    @staticmethod
    def test_album_attributes_strips_single_and_ep_suffix() -> None:
        raw = {
            "name": "Testing Title - Single",
            "artistName": "Artist",
            "releaseDate": "2026-01-01",
            "artwork": {"url": "http://example.com/art.jpg"},
        }
        attrs = AppleMusicAlbumAttributes.model_validate(raw)
        assert attrs.name == "Testing Title"

        raw["name"] = "Testing Title - EP"
        attrs_ep = AppleMusicAlbumAttributes.model_validate(raw)
        assert attrs_ep.name == "Testing Title"

    @staticmethod
    def test_track_attributes_strips_album_name_suffixes() -> None:
        raw = {
            "name": "Track Name",
            "artistName": "Artist",
            "albumName": "Project Name - Single",
            "trackNumber": 1,
            "releaseDate": "2026-01-01",
            "artwork": {"url": "http://example.com/art.jpg"},
            "playParams": {"id": "123"},
        }
        attrs = AppleMusicTrackAttributes.model_validate(raw)
        assert attrs.album_name == "Project Name"

    @staticmethod
    def test_album_attributes_normalizes_year_only_release_date() -> None:
        raw = {
            "name": "Test Album",
            "artistName": "Artist",
            "releaseDate": "2026",
            "artwork": {"url": "http://example.com/art.jpg"},
        }

        attrs = AppleMusicAlbumAttributes.model_validate(raw)

        assert attrs.release_date == date(2026, 1, 1)

    @staticmethod
    def test_track_attributes_normalizes_year_only_release_date() -> None:
        raw = {
            "name": "Track Name",
            "artistName": "Artist",
            "albumName": "Album",
            "trackNumber": 1,
            "releaseDate": "2026",
            "artwork": {"url": "http://example.com/art.jpg"},
            "playParams": {"id": "123"},
        }

        attrs = AppleMusicTrackAttributes.model_validate(raw)

        assert attrs.release_date == date(2026, 1, 1)


class TestPlaybackSchemas:
    @staticmethod
    def test_playback_response_camel_case_aliases() -> None:
        raw = {
            "customerMessage": "Error occurred",
            "songList": [{"assets": [{"flavor": "2b:ctrp256", "URL": "https://example.com/stream.m3u8"}]}],
        }
        resp = AppleMusicPlaybackResponse.model_validate(raw)
        assert resp.customer_message == "Error occurred"
        assert resp.song_list is not None
        assert len(resp.song_list) == 1
        assert str(resp.song_list[0].assets[0].url) == "https://example.com/stream.m3u8"


class TestLicenseSchemas:
    @staticmethod
    def test_license_response_validation() -> None:
        raw = {"status": 0, "license": "base64encodedlicense"}
        resp = AppleMusicLicenseResponse.model_validate(raw)
        assert resp.status == 0
        assert resp.license == "base64encodedlicense"

    @staticmethod
    def test_license_response_missing_keys_raises() -> None:
        with pytest.raises(ValidationError):
            _ = AppleMusicLicenseResponse.model_validate({"status": 0})
