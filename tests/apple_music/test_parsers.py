from datetime import date

import pytest

from amdl.apple_music.parsers import (
    AppleMusicAlbumParser,
    AppleMusicLicenseParser,
    AppleMusicPlaybackParser,
    AppleMusicTrackParser,
)
from amdl.domain import Album, Playback, Track
from amdl.json_type import JSON


@pytest.fixture
def raw_catalog_track_data() -> JSON:
    return {
        "data": [
            {
                "id": "10001",
                "attributes": {
                    "name": "Track One",
                    "artistName": "Test Artist",
                    "albumName": "Test Album",
                    "trackNumber": 1,
                    "releaseDate": "2026-01-15",
                    "artwork": {"url": "https://example.com/{w}x{h}bb.jpg"},
                    "playParams": {"id": "10001"},
                    "url": "https://music.apple.com/us/song/track-one/10001",
                },
            }
        ]
    }


@pytest.fixture
def raw_library_track_data() -> JSON:
    return {
        "data": [
            {
                "id": "i.libtrack1",
                "attributes": {
                    "name": "Library Track Name",
                    "artistName": "Library Artist",
                    "albumName": "Library Album",
                    "trackNumber": 2,
                    "releaseDate": "2026-02-01",
                    "artwork": {"url": "https://example.com/lib/{w}x{h}.jpg"},
                    "playParams": {"id": "i.libtrack1", "catalogId": "20002"},
                },
                "relationships": {
                    "catalog": {
                        "data": [
                            {
                                "id": "20002",
                                "attributes": {
                                    "name": "Catalog Track Name",
                                    "artistName": "Catalog Artist",
                                    "albumName": "Catalog Album",
                                    "trackNumber": 2,
                                    "releaseDate": "2026-02-01",
                                    "artwork": {"url": "https://example.com/cat/{w}x{h}.jpg"},
                                    "playParams": {"id": "20002"},
                                },
                            }
                        ]
                    }
                },
            }
        ]
    }


class TestAppleMusicTrackParser:
    def test_parse_catalog_track(self, raw_catalog_track_data: JSON) -> None:
        track = AppleMusicTrackParser.parse(raw_catalog_track_data)
        assert isinstance(track, Track)
        assert track.library_id == "10001"
        assert track.catalog_id == "10001"
        assert track.name == "Track One"
        assert track.release_date == date(2026, 1, 15)
        assert track.artwork_url == "https://example.com/9999x9999bb.jpg"

    def test_parse_library_track_with_catalog_relationship(self, raw_library_track_data: JSON) -> None:
        track = AppleMusicTrackParser.parse(raw_library_track_data)
        assert track.library_id == "i.libtrack1"
        assert track.catalog_id == "20002"
        assert track.name == "Catalog Track Name"
        assert track.artist_name == "Catalog Artist"


class TestAppleMusicPlaybackParser:
    def test_parse_successful_playback(self) -> None:
        data: JSON = {"songList": [{"assets": [{"flavor": "2b:ctrp256", "URL": "https://example.com/manifest.m3u8"}]}]}
        playback = AppleMusicPlaybackParser.parse(data)
        assert isinstance(playback, Playback)
        assert len(playback.songs) == 1

    def test_parse_playback_failure_dialog_raises(self) -> None:
        data: JSON = {"dialog": {"message": "Geoblocked track"}}
        with pytest.raises(ValueError, match="Geoblocked track"):
            _ = AppleMusicPlaybackParser.parse(data)

    def test_parse_playback_missing_songs_raises(self) -> None:
        data: JSON = {"customerMessage": None}
        with pytest.raises(ValueError, match="Playback response missing songs list"):
            _ = AppleMusicPlaybackParser.parse(data)


class TestAppleMusicAlbumParser:
    def test_parse_catalog_album(self, raw_catalog_track_data: JSON) -> None:
        raw_album: JSON = {
            "data": [
                {
                    "id": "album123",
                    "attributes": {
                        "name": "Full Album - EP",
                        "artistName": "Album Artist",
                        "releaseDate": "2026-03-01",
                        "artwork": {"url": "https://example.com/album/{w}x{h}.jpg"},
                    },
                    "relationships": {"tracks": raw_catalog_track_data},
                }
            ]
        }
        album = AppleMusicAlbumParser.parse(raw_album)
        assert isinstance(album, Album)
        assert album.catalog_id == "album123"
        assert album.library_id is None
        assert album.name == "Full Album"
        assert len(album.tracks) == 1
        assert album.tracks[0].name == "Track One"

    def test_parse_album_without_tracks_raises(self) -> None:
        raw_album: JSON = {
            "data": [
                {
                    "id": "album123",
                    "attributes": {
                        "name": "Empty Album",
                        "artistName": "Artist",
                        "releaseDate": "2026-03-01",
                        "artwork": {"url": "https://example.com/album.jpg"},
                    },
                }
            ]
        }
        with pytest.raises(ValueError, match="Album has no tracks"):
            _ = AppleMusicAlbumParser.parse(raw_album)


class TestAppleMusicLicenseParser:
    def test_parse_valid_license(self) -> None:
        data: JSON = {"status": 0, "license": "valid_license_string"}
        license_str = AppleMusicLicenseParser.parse(data)
        assert license_str == "valid_license_string"

    @pytest.mark.parametrize(
        "status,expected_error",
        [
            (-1001, "Invalid PSSH."),
            (-1002, "You do not own this title."),
            (-9999, "-9999"),
        ],
    )
    def test_check_status_errors(self, status: int, expected_error: str) -> None:
        with pytest.raises(ValueError, match=f"License error: {expected_error}"):
            AppleMusicLicenseParser.check_status(status)

    def test_empty_license_raises(self) -> None:
        with pytest.raises(ValueError, match="No license data received from Apple"):
            AppleMusicLicenseParser.check_license("")
