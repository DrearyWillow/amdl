from datetime import date

from pydantic import HttpUrl

from amdl.domain import Album, Track


class TestTrack:
    @staticmethod
    def test_valid_track_instantiation() -> None:
        track = Track(
            id="12345",
            name="Test Track",
            artist_name="Test Artist",
            album_name="Test Album",
            track_number=1,
            release_date=date(2026, 1, 1),
            artwork_url="https://example.com/art.jpg",
            url=HttpUrl("https://music.apple.com/us/song/test-track/12345"),
        )
        assert track.id == "12345"
        assert track.name == "Test Track"
        assert track.track_number == 1
        assert track.release_date == date(2026, 1, 1)

    @staticmethod
    def test_track_optional_url() -> None:
        track = Track(
            id="i.12345",
            name="Test Track",
            artist_name="Test Artist",
            album_name="Test Album",
            track_number=1,
            release_date=date(2026, 1, 1),
            artwork_url="https://example.com/art.jpg",
            url=None,
        )
        assert track.id == "i.12345"
        assert track.url is None


class TestAlbum:
    @staticmethod
    def test_valid_album_with_tracks() -> None:
        track = Track(
            id="t1",
            name="Track 1",
            artist_name="Artist",
            album_name="Album Name",
            track_number=1,
            release_date=date(2026, 1, 1),
            artwork_url="https://example.com/art.jpg",
            url=None,
        )
        album = Album(
            id="a1",
            name="Album Name",
            artist_name="Artist",
            release_date=date(2026, 1, 1),
            artwork_url="https://example.com/art.jpg",
            tracks=[track],
        )
        assert album.id == "a1"
        assert len(album.tracks) == 1
        assert album.tracks[0].name == "Track 1"

    @staticmethod
    def test_album_default_tracks_empty_list() -> None:
        album = Album(
            id="l.123",
            name="Album Name",
            artist_name="Artist",
            release_date=date(2026, 1, 1),
            artwork_url="https://example.com/art.jpg",
        )
        assert album.tracks == []
