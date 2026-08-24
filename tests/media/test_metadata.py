from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from amdl.domain import Track
from amdl.media.metadata import embed_track_metadata, save_artwork


class TestEmbedTrackMetadata:
    @staticmethod
    def test_embeds_metadata() -> None:
        track = Track(
            id="123",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=3,
            release_date=date(2024, 5, 17),
        )
        mp4 = MagicMock()
        mp4.tags = {}

        with patch("amdl.media.metadata.MP4", return_value=mp4) as mp4_class:
            embed_track_metadata(track, Path("/music/song.m4a"))

        mp4_class.assert_called_once_with(Path("/music/song.m4a"))
        assert mp4.tags == {
            "\xa9nam": "Song",
            "\xa9ART": "Artist",
            "\xa9alb": "Album",
            "\xa9day": "2024-05-17",
            "trkn": [(3, 0)],
        }
        mp4.save.assert_called_once()

    @staticmethod
    def test_adds_tags_when_mp4_has_no_tags() -> None:
        track = Track(
            id="123",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
            release_date=date(2024, 5, 17),
        )
        mp4 = MagicMock()
        mp4.tags = None

        def add_tags() -> None:
            mp4.tags = {}

        mp4.add_tags.side_effect = add_tags

        with patch("amdl.media.metadata.MP4", return_value=mp4):
            embed_track_metadata(track, Path("/music/song.m4a"))

        mp4.add_tags.assert_called_once()
        assert mp4.tags["\xa9nam"] == "Song"
        mp4.save.assert_called_once()

    @staticmethod
    def test_returns_when_tags_cannot_be_created() -> None:
        track = Track(
            id="123",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
            release_date=date(2024, 5, 17),
        )
        mp4 = MagicMock()
        mp4.tags = None
        mp4.add_tags.return_value = None

        with patch("amdl.media.metadata.MP4", return_value=mp4):
            embed_track_metadata(track, Path("/music/song.m4a"))

        mp4.add_tags.assert_called_once()
        mp4.save.assert_not_called()

    @staticmethod
    def test_embeds_url() -> None:
        track = Track(
            id="123",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
            release_date=date(2024, 5, 17),
        )
        mp4 = MagicMock()
        mp4.tags = {}

        with patch("amdl.media.metadata.MP4", return_value=mp4):
            embed_track_metadata(
                track,
                Path("/music/song.m4a"),
                url="https://music.apple.com/song/123",
            )

        assert mp4.tags["\xa9url"] == "https://music.apple.com/song/123"
        assert mp4.tags["purl"] == ["https://music.apple.com/song/123"]

    @staticmethod
    def test_does_not_embed_url_when_not_provided() -> None:
        track = Track(
            id="123",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
            release_date=date(2024, 5, 17),
        )
        mp4 = MagicMock()
        mp4.tags = {}

        with patch("amdl.media.metadata.MP4", return_value=mp4):
            embed_track_metadata(track, Path("/music/song.m4a"))

        assert "\xa9url" not in mp4.tags
        assert "purl" not in mp4.tags

    @staticmethod
    def test_embeds_artwork() -> None:
        track = Track(
            id="123",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
            release_date=date(2024, 5, 17),
        )
        mp4 = MagicMock()
        mp4.tags = {}
        artwork = b"jpeg data"

        with (
            patch("amdl.media.metadata.MP4", return_value=mp4),
            patch("amdl.media.metadata.MP4Cover") as mp4_cover,
        ):
            embed_track_metadata(
                track,
                Path("/music/song.m4a"),
                artwork=artwork,
            )

        mp4_cover.assert_called_once_with(artwork)
        assert mp4.tags["covr"] == [mp4_cover.return_value]

    @staticmethod
    def test_does_not_embed_artwork_when_not_provided() -> None:
        track = Track(
            id="123",
            name="Song",
            artist_name="Artist",
            album_name="Album",
            track_number=1,
            release_date=date(2024, 5, 17),
        )
        mp4 = MagicMock()
        mp4.tags = {}

        with patch("amdl.media.metadata.MP4", return_value=mp4):
            embed_track_metadata(
                track,
                Path("/music/song.m4a"),
                artwork=None,
            )

        assert "covr" not in mp4.tags


class TestSaveArtwork:
    @staticmethod
    def test_saves_artwork(tmp_path: Path) -> None:
        output_path = tmp_path / "artist" / "album" / "cover.jpg"
        image_bytes = b"jpeg data"

        save_artwork(image_bytes, output_path)

        assert output_path.read_bytes() == image_bytes

    @staticmethod
    def test_creates_parent_directories(tmp_path: Path) -> None:
        output_path = tmp_path / "artist" / "album" / "cover.jpg"

        save_artwork(b"jpeg data", output_path)

        assert output_path.parent.is_dir()
        assert output_path.read_bytes() == b"jpeg data"

    @staticmethod
    def test_skips_existing_artwork(tmp_path: Path) -> None:
        output_path = tmp_path / "cover.jpg"
        output_path.write_bytes(b"existing data")

        save_artwork(b"new data", output_path)

        assert output_path.read_bytes() == b"existing data"
