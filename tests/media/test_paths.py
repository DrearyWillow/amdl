from pathlib import Path

import pytest

from amdl.domain import Album, Playlist, Track
from amdl.media.paths import (
    album_artwork_path,
    album_track_path,
    playlist_artwork_path,
    playlist_track_path,
    sanitize_filename_component,
    track_path,
)


class TestSanitizeFilenameComponent:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("Song", "Song"),
            ("  Song  ", "Song"),
            ("Song/Name", "Song_Name"),
            ('Song: "Name"', "Song_ _Name_"),
            ("Song|Name", "Song_Name"),
            ("Song?Name", "Song_Name"),
            ("Song*Name", "Song_Name"),
            ("Song<Name>", "Song_Name_"),
            ("Song\\Name", "Song_Name"),
            ("Song\nName", "Song_Name"),
            ("Song\tName", "Song_Name"),
            ("Song.", "Song"),
            ("Song... ", "Song"),
            ("   ", "Unknown"),
            ("...", "Unknown"),
            (". ", "Unknown"),
            ("\x00\x1f", "_"),
        ],
    )
    @staticmethod
    def test_sanitize(value: str, expected: str) -> None:
        assert sanitize_filename_component(value) == expected


class TestTrackPath:
    @staticmethod
    def test_track_path() -> None:
        track = Track(
            id="123",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
        )

        result = track_path(Path("/music"), track)

        assert result == Path("/music/Artist/Song.m4a")

    @staticmethod
    def test_sanitizes_components() -> None:
        track = Track(
            id="123",
            name="Song/Name",
            artist_name="Artist/Name",
            album_name="Album",
            track_number=1,
        )

        result = track_path(Path("/music"), track)

        assert result == Path("/music/Artist_Name/Song_Name.m4a")


class TestAlbumTrackPath:
    @staticmethod
    def test_album_track_path() -> None:
        album = Album(
            id="123",
            name="Album",
            artist_name="Artist",
        )
        track = Track(
            id="456",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=3,
        )

        result = album_track_path(Path("/music"), album, track)

        assert result == Path("/music/Artist/Album/03 - Song.m4a")

    @staticmethod
    def test_track_number_is_zero_padded() -> None:
        album = Album(
            id="123",
            name="Album",
            artist_name="Artist",
        )
        track = Track(
            id="456",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=12,
        )

        result = album_track_path(Path("/music"), album, track)

        assert result.name == "12 - Song.m4a"

    @staticmethod
    def test_sanitizes_components() -> None:
        album = Album(
            id="123",
            name="Album/Name",
            artist_name="Artist/Name",
        )
        track = Track(
            id="456",
            name="Song/Name",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
        )

        result = album_track_path(Path("/music"), album, track)

        assert result == Path("/music/Artist_Name/Album_Name/01 - Song_Name.m4a")


class TestAlbumArtworkPath:
    @staticmethod
    def test_album_artwork_path() -> None:
        album = Album(
            id="123",
            name="Album",
            artist_name="Artist",
        )

        result = album_artwork_path(Path("/music"), album)

        assert result == Path("/music/Artist/Album/cover.jpg")

    @staticmethod
    def test_sanitizes_components() -> None:
        album = Album(
            id="123",
            name="Album/Name",
            artist_name="Artist/Name",
        )

        result = album_artwork_path(Path("/music"), album)

        assert result == Path("/music/Artist_Name/Album_Name/cover.jpg")


class TestPlaylistTrackPath:
    @staticmethod
    def test_playlist_track_path() -> None:
        track = Track(
            id="1",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
        )
        playlist = Playlist(
            id="123",
            name="Playlist",
            tracks=[track],
        )

        result = playlist_track_path(Path("/music"), playlist, track, 1)

        assert result == Path("/music/Playlist/01 - Artist - Song.m4a")

    @staticmethod
    def test_playlist_track_number_width_matches_playlist_length() -> None:
        tracks = [
            Track(
                id=str(i),
                name=f"Song {i}",
                artist_name="Artist",
                album_name="Album",
                track_number=i,
            )
            for i in range(100)
        ]
        playlist = Playlist(
            id="123",
            name="Playlist",
            tracks=tracks,
        )

        result = playlist_track_path(Path("/music"), playlist, tracks[0], 1)

        assert result.name == "001 - Artist - Song 0.m4a"

    @staticmethod
    def test_playlist_track_number_width_is_at_least_two_digits() -> None:
        track = Track(
            id="1",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
        )
        playlist = Playlist(
            id="123",
            name="Playlist",
            tracks=[track],
        )

        result = playlist_track_path(Path("/music"), playlist, track, 1)

        assert result.name == "01 - Artist - Song.m4a"

    @staticmethod
    def test_sanitizes_components() -> None:
        track = Track(
            id="1",
            name="Song/Name",
            artist_name="Artist/Name",
            album_name="Album",
            track_number=1,
        )
        playlist = Playlist(
            id="123",
            name="Playlist/Name",
            tracks=[track],
        )

        result = playlist_track_path(Path("/music"), playlist, track, 1)

        assert result == Path("/music/Playlist_Name/01 - Artist_Name - Song_Name.m4a")


class TestPlaylistArtworkPath:
    @staticmethod
    def test_playlist_artwork_path() -> None:
        playlist = Playlist(
            id="123",
            name="Playlist",
        )

        result = playlist_artwork_path(Path("/music"), playlist)

        assert result == Path("/music/Playlist/cover.jpg")

    @staticmethod
    def test_sanitizes_playlist_name() -> None:
        playlist = Playlist(
            id="123",
            name="Playlist/Name",
        )

        result = playlist_artwork_path(Path("/music"), playlist)

        assert result == Path("/music/Playlist_Name/cover.jpg")
