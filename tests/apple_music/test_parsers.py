from datetime import date

import pytest

from amdl.apple_music.parsers import (
    AppleMusicAlbumParser,
    AppleMusicArtistParser,
    AppleMusicLicenseParser,
    AppleMusicPlaybackParser,
    AppleMusicPlaylistParser,
    AppleMusicTrackParser,
)
from amdl.domain import Album, Artist, Playback, Playlist, Track
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

    def test_parse_library_track_without_catalog_uses_play_params_catalog_id(self) -> None:
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
                }
            ]
        }

        track = AppleMusicTrackParser.parse(data)

        assert track.library_id == "i.libtrack1"
        assert track.catalog_id == "20002"
        assert track.name == "Library Track Name"

    def test_parse_library_track_without_catalog_or_play_params(self) -> None:
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
                }
            ]
        }

        track = AppleMusicTrackParser.parse(data)

        assert track.library_id == "i.libtrack1"
        assert track.catalog_id is None
        assert track.name == "Library Track Name"
        assert track.artist_name == "Library Artist"

    def test_parse_library_track_with_empty_catalog_relationship(self) -> None:
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
                        }
                    },
                }
            ]
        }

        track = AppleMusicTrackParser.parse(data)

        assert track.library_id == "i.libtrack1"
        assert track.catalog_id == "20002"
        assert track.name == "Library Track Name"


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

    def test_parse_playback_failure_customer_message_raises(self) -> None:
        data: JSON = {
            "customerMessage": "Playback unavailable",
        }

        with pytest.raises(ValueError, match="Playback unavailable"):
            _ = AppleMusicPlaybackParser.parse(data)

    def test_parse_playback_failure_type_raises(self) -> None:
        data: JSON = {
            "failureType": "NO_PLAYBACK",
        }

        with pytest.raises(ValueError, match="NO_PLAYBACK"):
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

    def test_parse_library_album_with_catalog(self, raw_catalog_track_data: JSON) -> None:
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
                                }
                            ]
                        },
                        "tracks": raw_catalog_track_data,
                    },
                }
            ]
        }

        album = AppleMusicAlbumParser.parse(data)

        assert album.library_id == "l.libalbum1"
        assert album.catalog_id == "catalogalbum1"
        assert album.name == "Catalog Album"
        assert album.artist_name == "Catalog Artist"
        assert len(album.tracks) == 1

    def test_parse_library_album_without_catalog(self, raw_catalog_track_data: JSON) -> None:
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
                }
            ]
        }

        album = AppleMusicAlbumParser.parse(data)

        assert album.library_id == "l.libalbum1"
        assert album.catalog_id is None
        assert album.name == "Library Album"
        assert album.artist_name == "Library Artist"

    def test_parse_album_with_empty_tracks_raises(self) -> None:
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
                        }
                    },
                }
            ]
        }

        with pytest.raises(ValueError, match="Album has no tracks"):
            _ = AppleMusicAlbumParser.parse(data)

    def test_parse_album_with_null_tracks_relationship_raises(self) -> None:
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
                }
            ]
        }

        with pytest.raises(ValueError, match="Album has no tracks"):
            _ = AppleMusicAlbumParser.parse(data)

    def test_parse_library_album_without_relationships_raises(self) -> None:
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
                }
            ]
        }

        with pytest.raises(ValueError, match="Album has no tracks"):
            _ = AppleMusicAlbumParser.parse(data)


class TestAppleMusicLicenseParser:
    def test_parse_valid_license(self) -> None:
        data: JSON = {"status": 0, "license": "valid_license_string"}
        license_str = AppleMusicLicenseParser.parse(data)
        assert license_str == "valid_license_string"

    class TestAppleMusicLicenseParser:
        @pytest.mark.parametrize(
            "status,expected_error",
            [
                (-1001, "Invalid PSSH."),
                (-1002, "You do not own this title."),
                (-1004, "Maximum number of simultaneous streams exceeded."),
                (-1017, "This content is geo-restricted."),
                (-1021, "Device has insufficient security level."),
                (-9999, "-9999"),
            ],
        )
        def test_check_status_errors(self, status: int, expected_error: str) -> None:
            with pytest.raises(ValueError, match=f"License error: {expected_error}"):
                AppleMusicLicenseParser.check_status(status)

        def test_parse_empty_license_raises(self) -> None:
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
                        }
                    ]
                }
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
                            ]
                        }
                    },
                }
            ]
        }

        artist = AppleMusicArtistParser.parse(data)

        assert isinstance(artist, Artist)
        assert artist.artist_id == "artist1"
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
                                        "albums": {"data": [self._album_resource("album1", "Catalog Album")]}
                                    },
                                }
                            ]
                        },
                        "albums": {
                            "data": [],
                        },
                    },
                }
            ]
        }

        artist = AppleMusicArtistParser.parse(data)

        assert artist.artist_id == "artist1"
        assert artist.name == "Catalog Artist"
        assert len(artist.albums) == 1
        assert artist.albums[0].name == "Catalog Album"

    def test_parse_artist_without_albums_raises(self) -> None:
        data: JSON = {
            "data": [
                {
                    "id": "artist1",
                    "attributes": {
                        "name": "Artist Without Albums",
                        "artwork": None,
                    },
                    "relationships": {},
                }
            ]
        }

        with pytest.raises(ValueError, match="Artist response included no albums"):
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
                            ]
                        }
                    },
                }
            ]
        }

        artist = AppleMusicArtistParser.parse(data)

        assert artist.artist_id == "artist1"
        assert artist.name == "Test Artist"
        assert artist.artwork_url is None

    def test_parse_artist_without_relationships_raises(self) -> None:
        data: JSON = {
            "data": [
                {
                    "id": "r.artist1",
                    "attributes": {
                        "name": "Test Artist",
                        "artwork": None,
                    },
                    "relationships": None,
                }
            ]
        }

        with pytest.raises(ValueError, match="Artist response included no albums"):
            _ = AppleMusicArtistParser.parse(data)


class TestAppleMusicPlaylistParser:
    def test_parse_playlist(self) -> None:
        data: JSON = {
            "data": [
                {
                    "id": "playlist1",
                    "attributes": {
                        "name": "Test Playlist",
                        "artwork": {"url": "https://example.com/{w}x{h}.jpg"},
                    },
                }
            ]
        }

        playlist = AppleMusicPlaylistParser.parse(data)

        assert isinstance(playlist, Playlist)
        assert playlist.id == "playlist1"
        assert playlist.name == "Test Playlist"
        assert playlist.artwork_url == "https://example.com/9999x9999.jpg"
