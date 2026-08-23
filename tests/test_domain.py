from datetime import date

import pytest
from pydantic import HttpUrl, ValidationError

from amdl.domain import Album, DomainModel, Track


class TestDomainModel:
    @staticmethod
    def test_id_property_prefers_catalog_id() -> None:
        model = DomainModel(catalog_id="cat123", library_id="lib456")
        assert model.id == "cat123"

    @staticmethod
    def test_id_property_falls_back_to_library_id() -> None:
        model = DomainModel(catalog_id=None, library_id="lib456")
        assert model.id == "lib456"

    @staticmethod
    def test_missing_both_ids_raises_validation_error() -> None:
        with pytest.raises(ValidationError, match="A library or catalog ID is required"):
            _ = DomainModel()

    def test_id_property_raises_if_invariant_is_bypassed(self) -> None:
        model = DomainModel.model_construct(library_id=None, catalog_id=None)

        with pytest.raises(AssertionError, match="A library or catalog ID is required"):
            _ = model.id


class TestTrack:
    @staticmethod
    def test_valid_track_instantiation() -> None:
        track = Track(
            catalog_id="12345",
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
            library_id="i.12345",
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

    @staticmethod
    def test_track_requires_id() -> None:
        with pytest.raises(ValidationError, match="A library or catalog ID is required"):
            _ = Track(
                name="Test Track",
                artist_name="Test Artist",
                album_name="Test Album",
                track_number=1,
                release_date=date(2026, 1, 1),
                artwork_url="https://example.com/art.jpg",
                url=None,
            )


class TestAlbum:
    @staticmethod
    def test_valid_album_with_tracks() -> None:
        track = Track(
            catalog_id="t1",
            name="Track 1",
            artist_name="Artist",
            album_name="Album Name",
            track_number=1,
            release_date=date(2026, 1, 1),
            artwork_url="https://example.com/art.jpg",
            url=None,
        )
        album = Album(
            catalog_id="a1",
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
            library_id="l.123",
            name="Album Name",
            artist_name="Artist",
            release_date=date(2026, 1, 1),
            artwork_url="https://example.com/art.jpg",
        )
        assert album.tracks == []
