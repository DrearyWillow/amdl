from datetime import date
from typing import TYPE_CHECKING

import pytest

from amdl.apple_music.parsers import (
    AppleMusicAlbumParser,
    AppleMusicArtistParser,
    AppleMusicLicenseParser,
    AppleMusicPlaybackParser,
    AppleMusicPlaylistParser,
    AppleMusicTrackParser,
)
from amdl.domain import Album, Artist, PlaybackSong, Playlist, Track

if TYPE_CHECKING:
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
            },
        ],
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
                            },
                        ],
                    },
                },
            },
        ],
    }


class TestAppleMusicTrackParser:
    @staticmethod
    def test_parse_catalog_track(raw_catalog_track_data: JSON) -> None:
        track = AppleMusicTrackParser.parse(raw_catalog_track_data)
        assert isinstance(track, Track)
        assert track.id == "10001"
        assert track.name == "Track One"
        assert track.release_date == date(2026, 1, 15)
        assert track.artwork_url == "https://example.com/9999x9999bb.jpg"

    @staticmethod
    def test_parse_library_track_with_catalog_relationship(raw_library_track_data: JSON) -> None:
        track = AppleMusicTrackParser.parse(raw_library_track_data)
        assert track.id == "20002"
        assert track.name == "Catalog Track Name"
        assert track.artist_name == "Catalog Artist"

    @staticmethod
    def test_parse_library_track_without_catalog_uses_play_params_catalog_id() -> None:
        data: JSON = {
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
                        "playParams": {
                            "id": "i.libtrack1",
                            "catalogId": "20002",
                        },
                    },
                    "relationships": None,
                },
            ],
        }

        track = AppleMusicTrackParser.parse(data)

        assert track.id == "20002"
        assert track.name == "Library Track Name"

    @staticmethod
    def test_parse_library_track_without_catalog_or_play_params() -> None:
        data: JSON = {
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
                        "playParams": None,
                    },
                    "relationships": None,
                },
            ],
        }

        track = AppleMusicTrackParser.parse(data)

        assert track.id == "i.libtrack1"
        assert track.name == "Library Track Name"
        assert track.artist_name == "Library Artist"

    @staticmethod
    def test_parse_library_track_with_empty_catalog_relationship() -> None:
        data: JSON = {
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
                        "playParams": {
                            "id": "i.libtrack1",
                            "catalogId": "20002",
                        },
                    },
                    "relationships": {
                        "catalog": {
                            "data": [],
                        },
                    },
                },
            ],
        }

        track = AppleMusicTrackParser.parse(data)

        assert track.id == "20002"
        assert track.name == "Library Track Name"


class TestAppleMusicPlaybackParser:
    @staticmethod
    def test_parse_hls_playback(monkeypatch: pytest.MonkeyPatch) -> None:
        expected = PlaybackSong(url="https://example.com/audio.m4a", kid="test-kid")

        def mock_parse_hls_playlist(url: str) -> PlaybackSong:
            assert url == "https://example.com/manifest.m3u8"
            return expected

        monkeypatch.setattr("amdl.apple_music.parsers.parse_hls_playlist", mock_parse_hls_playlist)
        data: JSON = {"songList": [{"assets": [{"flavor": "28:ctrp256", "URL": "https://example.com/manifest.m3u8"}]}]}
        assert AppleMusicPlaybackParser.parse(data) == expected

    @staticmethod
    def test_parse_direct_playback() -> None:
        data: JSON = {"songList": [{"assets": [{"URL": "https://example.com/audio.m4a"}]}]}
        assert AppleMusicPlaybackParser.parse(data) == PlaybackSong(url="https://example.com/audio.m4a")

    @staticmethod
    def test_parse_playback_no_suitable_asset_raises() -> None:
        data: JSON = {
            "songList": [{"assets": [{"flavor": "something-else", "URL": "https://example.com/manifest.m3u8"}]}],
        }
        with pytest.raises(ValueError, match="No suitable playback URL found"):
            _ = AppleMusicPlaybackParser.parse(data)

    @staticmethod
    def test_parse_playback_failure_dialog_raises() -> None:
        data: JSON = {"dialog": {"message": "Geoblocked track"}}
        with pytest.raises(ValueError, match="Geoblocked track"):
            _ = AppleMusicPlaybackParser.parse(data)

    @staticmethod
    def test_parse_playback_missing_songs_raises() -> None:
        data: JSON = {"customerMessage": None}
        with pytest.raises(ValueError, match="Playback response missing songs list"):
            _ = AppleMusicPlaybackParser.parse(data)

    @staticmethod
    def test_parse_playback_failure_customer_message_raises() -> None:
        data: JSON = {
            "customerMessage": "Playback unavailable",
        }

        with pytest.raises(ValueError, match="Playback unavailable"):
            _ = AppleMusicPlaybackParser.parse(data)

    @staticmethod
    def test_parse_playback_failure_type_raises() -> None:
        data: JSON = {
            "failureType": "NO_PLAYBACK",
        }

        with pytest.raises(ValueError, match="NO_PLAYBACK"):
            _ = AppleMusicPlaybackParser.parse(data)


class TestAppleMusicAlbumParser:
    @staticmethod
    def test_parse_catalog_album(raw_catalog_track_data: JSON) -> None:
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
                },
            ],
        }
        album = AppleMusicAlbumParser.parse(raw_album)
        assert isinstance(album, Album)
        assert album.id == "album123"
        assert album.name == "Full Album"
        assert len(album.tracks) == 1
        assert album.tracks[0].name == "Track One"

    @staticmethod
    def test_parse_album_without_tracks_raises() -> None:
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
                },
            ],
        }
        with pytest.raises(ValueError, match="Album has no tracks"):
            _ = AppleMusicAlbumParser.parse(raw_album)

    @staticmethod
    def test_parse_library_album_with_catalog(raw_catalog_track_data: JSON) -> None:
        data: JSON = {
            "data": [
                {
                    "id": "l.libalbum1",
                    "attributes": {
                        "name": "Library Album",
                        "artistName": "Library Artist",
                        "releaseDate": "2026-03-01",
                        "artwork": {"url": "https://example.com/library/{w}x{h}.jpg"},
                        "url": "https://example.com/library-album",
                    },
                    "relationships": {
                        "catalog": {
                            "data": [
                                {
                                    "id": "catalogalbum1",
                                    "attributes": {
                                        "name": "Catalog Album",
                                        "artistName": "Catalog Artist",
                                        "releaseDate": "2026-03-01",
                                        "artwork": {"url": "https://example.com/catalog/{w}x{h}.jpg"},
                                        "url": "https://example.com/catalog-album",
                                    },
                                },
                            ],
                        },
                        "tracks": raw_catalog_track_data,
                    },
                },
            ],
        }

        album = AppleMusicAlbumParser.parse(data)

        assert album.id == "catalogalbum1"
        assert album.name == "Catalog Album"
        assert album.artist_name == "Catalog Artist"
        assert len(album.tracks) == 1

    @staticmethod
    def test_parse_library_album_without_catalog(raw_catalog_track_data: JSON) -> None:
        data: JSON = {
            "data": [
                {
                    "id": "l.libalbum1",
                    "attributes": {
                        "name": "Library Album",
                        "artistName": "Library Artist",
                        "releaseDate": "2026-03-01",
                        "artwork": {"url": "https://example.com/library/{w}x{h}.jpg"},
                        "url": "https://example.com/library-album",
                    },
                    "relationships": {
                        "tracks": raw_catalog_track_data,
                    },
                },
            ],
        }

        album = AppleMusicAlbumParser.parse(data)

        assert album.id == "l.libalbum1"
        assert album.name == "Library Album"
        assert album.artist_name == "Library Artist"

    @staticmethod
    def test_parse_album_with_empty_tracks_raises() -> None:
        data: JSON = {
            "data": [
                {
                    "id": "album123",
                    "attributes": {
                        "name": "Empty Album",
                        "artistName": "Artist",
                        "releaseDate": "2026-03-01",
                        "artwork": {"url": "https://example.com/album.jpg"},
                    },
                    "relationships": {
                        "tracks": {
                            "data": [],
                        },
                    },
                },
            ],
        }

        with pytest.raises(ValueError, match="Album has no tracks"):
            _ = AppleMusicAlbumParser.parse(data)

    @staticmethod
    def test_parse_album_with_null_tracks_relationship_raises() -> None:
        data: JSON = {
            "data": [
                {
                    "id": "album123",
                    "attributes": {
                        "name": "Empty Album",
                        "artistName": "Artist",
                        "releaseDate": "2026-03-01",
                        "artwork": {"url": "https://example.com/album.jpg"},
                    },
                    "relationships": {
                        "tracks": None,
                    },
                },
            ],
        }

        with pytest.raises(ValueError, match="Album has no tracks"):
            _ = AppleMusicAlbumParser.parse(data)

    @staticmethod
    def test_parse_library_album_without_relationships_raises() -> None:
        data: JSON = {
            "data": [
                {
                    "id": "l.libalbum1",
                    "attributes": {
                        "name": "Library Album",
                        "artistName": "Library Artist",
                        "releaseDate": "2026-03-01",
                        "artwork": {"url": "https://example.com/library/{w}x{h}.jpg"},
                        "url": "https://example.com/library-album",
                    },
                    "relationships": None,
                },
            ],
        }

        with pytest.raises(ValueError, match="Album has no tracks"):
            _ = AppleMusicAlbumParser.parse(data)


class TestAppleMusicLicenseParser:
    @staticmethod
    def test_parse_valid_license() -> None:
        data: JSON = {"status": 0, "license": "valid_license_string"}
        license_str = AppleMusicLicenseParser.parse(data)
        assert license_str == "valid_license_string"

    class TestAppleMusicLicenseParser:
        @staticmethod
        @pytest.mark.parametrize(
            ("status", "expected_error"),
            [
                (-1001, "Invalid PSSH."),
                (-1002, "You do not own this title."),
                (-1004, "Maximum number of simultaneous streams exceeded."),
                (-1017, "This content is geo-restricted."),
                (-1021, "Device has insufficient security level."),
                (-9999, "-9999"),
            ],
        )
        def test_check_status_errors(status: int, expected_error: str) -> None:
            with pytest.raises(ValueError, match=f"License error: {expected_error}"):
                AppleMusicLicenseParser.check_status(status)

        @staticmethod
        def test_parse_empty_license_raises() -> None:
            data: JSON = {"status": 0, "license": ""}

            with pytest.raises(ValueError, match="No license data received from Apple"):
                _ = AppleMusicLicenseParser.parse(data)


class TestAppleMusicArtistParser:
    @staticmethod
    def _album_resource(album_id: str, name: str) -> JSON:
        return {
            "id": album_id,
            "attributes": {
                "name": name,
                "artistName": "Test Artist",
                "releaseDate": "2026-01-01",
                "artwork": {"url": "https://example.com/{w}x{h}.jpg"},
                "url": f"https://music.apple.com/us/album/{album_id}",
            },
            "relationships": {
                "tracks": {
                    "data": [
                        {
                            "id": "track1",
                            "attributes": {
                                "name": "Track",
                                "artistName": "Test Artist",
                                "albumName": name,
                                "trackNumber": 1,
                                "releaseDate": "2026-01-01",
                                "artwork": {"url": "https://example.com/{w}x{h}.jpg"},
                                "playParams": {"id": "track1"},
                                "url": "https://example.com/track",
                            },
                        },
                    ],
                },
            },
        }

    def test_parse_artist_using_resource_albums(self) -> None:
        data: JSON = {
            "data": [
                {
                    "id": "artist1",
                    "attributes": {
                        "name": "Test Artist",
                        "artwork": {"url": "https://example.com/{w}x{h}.jpg"},
                    },
                    "relationships": {
                        "albums": {
                            "data": [
                                self._album_resource("album1", "Album One"),
                            ],
                        },
                    },
                },
            ],
        }

        artist = AppleMusicArtistParser.parse(data)

        assert isinstance(artist, Artist)
        assert artist.id == "artist1"
        assert artist.name == "Test Artist"
        assert len(artist.albums) == 1
        assert artist.albums[0].name == "Album One"

    def test_parse_artist_using_catalog_albums(self) -> None:
        data: JSON = {
            "data": [
                {
                    "id": "i.artist1",
                    "attributes": {
                        "name": "Library Artist",
                        "artwork": None,
                    },
                    "relationships": {
                        "catalog": {
                            "data": [
                                {
                                    "id": "artist1",
                                    "attributes": {
                                        "name": "Catalog Artist",
                                        "artwork": {"url": "https://example.com/{w}x{h}.jpg"},
                                    },
                                    "relationships": {
                                        "albums": {"data": [self._album_resource("album1", "Catalog Album")]},
                                    },
                                },
                            ],
                        },
                        "albums": {
                            "data": [],
                        },
                    },
                },
            ],
        }

        artist = AppleMusicArtistParser.parse(data)

        assert artist.id == "artist1"
        assert artist.name == "Catalog Artist"
        assert len(artist.albums) == 1
        assert artist.albums[0].name == "Catalog Album"

    @staticmethod
    def test_parse_artist_without_albums_raises() -> None:
        data: JSON = {
            "data": [
                {
                    "id": "artist1",
                    "attributes": {
                        "name": "Artist Without Albums",
                        "artwork": None,
                    },
                    "relationships": {},
                },
            ],
        }

        with pytest.raises(ValueError, match=r"Artist has no albums\."):
            _ = AppleMusicArtistParser.parse(data)

    def test_parse_artist_without_catalog_uses_resource_attributes(self) -> None:
        data: JSON = {
            "data": [
                {
                    "id": "artist1",
                    "attributes": {
                        "name": "Test Artist",
                        "artwork": None,
                    },
                    "relationships": {
                        "albums": {
                            "data": [
                                self._album_resource("album1", "Album One"),
                            ],
                        },
                    },
                },
            ],
        }

        artist = AppleMusicArtistParser.parse(data)

        assert artist.id == "artist1"
        assert artist.name == "Test Artist"
        assert artist.artwork_url is None

    @staticmethod
    def test_parse_artist_without_relationships_raises() -> None:
        data: JSON = {
            "data": [
                {
                    "id": "r.artist1",
                    "attributes": {
                        "name": "Test Artist",
                        "artwork": None,
                    },
                    "relationships": None,
                },
            ],
        }

        with pytest.raises(ValueError, match=r"Artist has no albums\."):
            _ = AppleMusicArtistParser.parse(data)


class TestAppleMusicPlaylistParser:
    @staticmethod
    def test_parse_playlist() -> None:
        data: JSON = {
            "data": [
                {
                    "id": "playlist1",
                    "attributes": {
                        "name": "Test Playlist",
                        "artwork": {"url": "https://example.com/{w}x{h}.jpg"},
                    },
                },
            ],
        }

        playlist = AppleMusicPlaylistParser.parse(data)

        assert isinstance(playlist, Playlist)
        assert playlist.id == "playlist1"
        assert playlist.name == "Test Playlist"
        assert playlist.artwork_url == "https://example.com/9999x9999.jpg"
