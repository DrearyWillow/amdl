from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import HttpUrl

from amdl.apple_music.urls import AppleMusicType
from amdl.domain import Album, Artist, Playlist, Track
from amdl.downloader import Downloader, TrackContext


class TestDownloader:
    @staticmethod
    def make_downloader() -> tuple[Downloader, MagicMock, MagicMock, MagicMock]:
        auth = MagicMock()
        client = MagicMock()
        media_downloader = MagicMock()
        drm = MagicMock()

        with (
            patch("amdl.downloader.AppleMusicClient", return_value=client),
            patch("amdl.downloader.MediaDownloader", return_value=media_downloader),
            patch("amdl.downloader.WidevineDRM", return_value=drm),
        ):
            downloader = Downloader(auth)

        return downloader, client, media_downloader, drm

    @staticmethod
    def make_track(
        track_id: str = "track-1",
        *,
        name: str = "Song",
        track_number: int = 1,
        url: str | None = None,
        artwork_url: str | None = None,
    ) -> Track:
        return Track(
            id=track_id,
            name=name,
            artist_name="Artist",
            album_name="Album",
            track_number=track_number,
            url=HttpUrl(url) if url is not None else None,
            artwork_url=artwork_url,
        )

    @staticmethod
    def make_album(tracks: list[Track] | None = None, artwork_url: str | None = None, url: str | None = None) -> Album:
        return Album(
            id="album-1",
            name="Album",
            artist_name="Artist",
            artwork_url=artwork_url,
            url=HttpUrl(url) if url is not None else None,
            tracks=tracks or [],
        )

    @staticmethod
    def test_init() -> None:
        auth = MagicMock()
        client = MagicMock()
        media_downloader = MagicMock()
        drm = MagicMock()

        with (
            patch("amdl.downloader.AppleMusicClient", return_value=client) as client_class,
            patch("amdl.downloader.MediaDownloader", return_value=media_downloader) as media_class,
            patch("amdl.downloader.WidevineDRM", return_value=drm) as drm_class,
        ):
            downloader = Downloader(auth, max_workers=2)

        client_class.assert_called_once_with(auth)
        media_class.assert_called_once_with(client)
        drm_class.assert_called_once_with(client)

        assert downloader.client is client
        assert downloader.media_downloader is media_downloader
        assert downloader.drm is drm

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_context_manager() -> None:
        downloader, _, _, _ = TestDownloader.make_downloader()

        with patch.object(downloader.executor, "shutdown") as shutdown, downloader:
            pass

        shutdown.assert_called_once_with(wait=True)

    @staticmethod
    @pytest.mark.parametrize(
        ("am_type", "method_name"),
        [
            (AppleMusicType.ALBUM, "album"),
            (AppleMusicType.SONG, "track"),
            (AppleMusicType.ARTIST, "artist"),
            (AppleMusicType.PLAYLIST, "playlist"),
        ],
    )
    def test_map_downloader(am_type: AppleMusicType, method_name: str) -> None:
        downloader, _, _, _ = TestDownloader.make_downloader()

        method = downloader._map_downloader(am_type)  # pyright: ignore[reportPrivateUsage]

        assert method == getattr(downloader, method_name)

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_download() -> None:
        downloader, _, _, _ = TestDownloader.make_downloader()

        output_dir = Path("downloads")
        context = TrackContext(TestDownloader.make_track(), output_dir / "song.m4a", "https://music.apple.com/song")

        with (
            patch.object(
                downloader, "_map_downloader", return_value=MagicMock(return_value=[context])
            ) as map_downloader,
            patch.object(downloader, "_download_context") as download_context,
        ):
            downloader.download(AppleMusicType.SONG, "track-1", output_dir, "https://music.apple.com/song")

        map_downloader.assert_called_once_with(AppleMusicType.SONG)
        download_context.assert_called_once_with(context)

    @staticmethod
    def test_download_propagates_worker_error() -> None:
        downloader, _, _, _ = TestDownloader.make_downloader()

        context = TrackContext(TestDownloader.make_track(), Path("song.m4a"), "https://music.apple.com/song")

        error = RuntimeError("download failed")

        with (
            patch.object(downloader, "_map_downloader", return_value=MagicMock(return_value=[context])),
            patch.object(downloader, "_download_context", side_effect=error),
            pytest.raises(RuntimeError, match="download failed"),
        ):
            downloader.download(AppleMusicType.SONG, "track-1", Path("downloads"), "https://music.apple.com/song")

    @staticmethod
    def test_download_context_skips_existing_file() -> None:
        downloader, _, _, _ = TestDownloader.make_downloader()

        context = TrackContext(
            TestDownloader.make_track(),
            Path("song.m4a"),
            "https://music.apple.com/song",
        )

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch.object(downloader, "_download_track_audio") as download_audio,
            patch("amdl.downloader.embed_track_metadata") as embed_metadata,
        ):
            downloader._download_context(context)  # pyright: ignore[reportPrivateUsage]

        download_audio.assert_not_called()
        embed_metadata.assert_not_called()

    @staticmethod
    def test_download_context() -> None:
        downloader, _, _, _ = TestDownloader.make_downloader()

        context = TrackContext(
            TestDownloader.make_track(), Path("song.m4a"), "https://music.apple.com/song", b"artwork"
        )

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch.object(downloader, "_download_track_audio") as download_audio,
            patch.object(downloader, "_get_context_art", return_value=b"artwork") as get_art,
            patch("amdl.downloader.embed_track_metadata") as embed_metadata,
        ):
            downloader._download_context(context)  # pyright: ignore[reportPrivateUsage]

        download_audio.assert_called_once_with(
            context.track,
            context.output_path,
        )
        get_art.assert_called_once_with(context)
        embed_metadata.assert_called_once_with(
            context.track,
            context.output_path,
            context.url,
            b"artwork",
        )

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_download_context_skips_value_error() -> None:
        downloader, _, _, _ = TestDownloader.make_downloader()

        context = TrackContext(TestDownloader.make_track(), Path("song.m4a"), "https://music.apple.com/song")

        with (
            patch("pathlib.Path.exists", return_value=False),
            patch.object(downloader, "_download_track_audio", side_effect=ValueError("unavailable")),
            patch("amdl.downloader.embed_track_metadata") as embed_metadata,
        ):
            downloader._download_context(context)  # pyright: ignore[reportPrivateUsage]

        embed_metadata.assert_not_called()

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_download_track_audio_without_drm() -> None:
        downloader, client, media_downloader, drm = TestDownloader.make_downloader()

        track = TestDownloader.make_track()
        output_path = Path("Artist/Song.m4a")

        playback = MagicMock()
        playback.url = "https://example.com/song.m4a"
        playback.kid = None
        client.get_playback.return_value = playback

        downloader._download_track_audio(track, output_path)  # pyright: ignore[reportPrivateUsage]

        client.get_playback.assert_called_once_with(track.id)
        drm.get_content_key.assert_not_called()
        media_downloader.download.assert_called_once_with(playback.url, output_path, None, None)

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_download_track_audio_with_drm() -> None:
        downloader, client, media_downloader, drm = TestDownloader.make_downloader()

        track = TestDownloader.make_track()
        output_path = Path("Artist/Song.m4a")

        playback = MagicMock()
        playback.url = "https://example.com/song.m4a"
        playback.kid = "kid"
        client.get_playback.return_value = playback
        drm.get_content_key.return_value = "key"

        downloader._download_track_audio(track, output_path)  # pyright: ignore[reportPrivateUsage]

        client.get_playback.assert_called_once_with(track.id)
        drm.get_content_key.assert_called_once_with(playback.kid, track.id)
        media_downloader.download.assert_called_once_with(playback.url, output_path, playback.kid, "key")

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_track_uses_track_url() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        track = TestDownloader.make_track(
            url="https://music.apple.com/track/1",
        )
        client.get_track.return_value = track

        output_dir = Path("downloads")

        with patch(
            "amdl.downloader.track_path",
            return_value=output_dir / "Artist/Song.m4a",
        ) as path:
            contexts = list(
                downloader.track("track-1", output_dir, "https://input.example"),
            )

        client.get_track.assert_called_once_with("track-1")
        path.assert_called_once_with(output_dir, track)

        assert contexts == [
            TrackContext(
                track,
                output_dir / "Artist/Song.m4a",
                "https://music.apple.com/track/1",
            ),
        ]

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_track_falls_back_to_input_url() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        track = TestDownloader.make_track()
        client.get_track.return_value = track
        output_dir = Path("downloads")

        with patch("amdl.downloader.track_path", return_value=output_dir / "Artist/Song.m4a"):
            contexts = list(
                downloader.track("track-1", output_dir, "https://input.example"),
            )

        assert contexts[0].url == "https://input.example"

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_album() -> None:
        downloader, _, _, _ = TestDownloader.make_downloader()

        album = TestDownloader.make_album(
            tracks=[
                TestDownloader.make_track(track_number=1),
                TestDownloader.make_track(
                    track_id="track-2",
                    name="Second",
                    track_number=2,
                ),
            ],
        )
        output_dir = Path("downloads")

        with (
            patch.object(downloader.client, "get_album", return_value=album),
            patch.object(downloader, "_prepare_album_contexts", return_value=[]) as prepare,
        ):
            result = downloader.album("album-1", output_dir, "https://input.example")

        prepare.assert_called_once_with(album, output_dir, "https://input.example")
        assert result == []

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_artist() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        album_one = TestDownloader.make_album()
        album_two = Album(
            id="album-2",
            name="Second Album",
            artist_name="Artist",
        )
        artist = Artist(
            id="artist-1",
            name="Artist",
            albums=[album_one, album_two],
        )
        client.get_artist.return_value = artist

        first_context = TrackContext(
            TestDownloader.make_track(),
            Path("one.m4a"),
            "https://input.example",
        )
        second_context = TrackContext(
            TestDownloader.make_track(track_id="track-2"),
            Path("two.m4a"),
            "https://input.example",
        )

        def prepare(album: Album, output_dir: Path, input_url: str) -> list[TrackContext]:
            del output_dir, input_url
            return [first_context] if album.id == album_one.id else [second_context]

        with patch.object(downloader, "_prepare_album_contexts", side_effect=prepare) as prepare_mock:
            result = downloader.artist("artist-1", Path("downloads"), "https://input.example")

        client.get_artist.assert_called_once_with("artist-1")
        expected_album_count = 2
        assert prepare_mock.call_count == expected_album_count
        assert sorted(context.track.id for context in result) == ["track-1", "track-2"]

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_playlist() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        track = TestDownloader.make_track(
            url="https://music.apple.com/track/1",
        )
        playlist = Playlist(
            id="playlist-1",
            name="Playlist",
            tracks=[track],
            artwork_url="https://example.com/artwork.jpg",
        )
        client.get_playlist.return_value = playlist
        client.fetch_content.return_value = b"artwork"

        output_dir = Path("downloads")

        with (
            patch(
                "amdl.downloader.playlist_artwork_path",
                return_value=output_dir / "Playlist/cover.jpg",
            ) as artwork_path,
            patch("amdl.downloader.save_artwork") as save,
            patch(
                "amdl.downloader.playlist_track_path",
                return_value=output_dir / "Playlist/01 - Artist - Song.m4a",
            ) as track_path,
        ):
            contexts = list(
                downloader.playlist("playlist-1", output_dir, "https://input.example"),
            )

        client.get_playlist.assert_called_once_with("playlist-1")
        client.fetch_content.assert_called_once_with(playlist.artwork_url)
        artwork_path.assert_called_once_with(output_dir, playlist)
        save.assert_called_once_with(b"artwork", output_dir / "Playlist/cover.jpg")
        track_path.assert_called_once_with(output_dir, playlist, track, 1)

        assert contexts[0].track == track
        assert contexts[0].url == "https://music.apple.com/track/1"

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_playlist_without_artwork() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        playlist = Playlist(id="playlist-1", name="Playlist", tracks=[TestDownloader.make_track()])
        client.get_playlist.return_value = playlist

        with patch("amdl.downloader.save_artwork") as save, patch("amdl.downloader.playlist_track_path"):
            contexts = list(downloader.playlist("playlist-1", Path("downloads"), "https://input.example"))

        client.fetch_content.assert_not_called()
        save.assert_not_called()
        assert len(contexts) == 1

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_playlist_empty() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        client.get_playlist.return_value = Playlist(id="playlist-1", name="Empty")

        with pytest.raises(ValueError, match=r"Playlist has no tracks\."):
            downloader.playlist("playlist-1", Path("downloads"), "https://input.example")

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_prepare_album_contexts() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        track = TestDownloader.make_track(url="https://music.apple.com/track/1")
        album = TestDownloader.make_album(
            tracks=[track], url="https://music.apple.com/album/1", artwork_url="https://example.com/cover.jpg"
        )
        client.fetch_content.return_value = b"artwork"

        output_dir = Path("downloads")

        with (
            patch(
                "amdl.downloader.album_artwork_path", return_value=output_dir / "Artist/Album/cover.jpg"
            ) as artwork_path,
            patch("amdl.downloader.save_artwork") as save,
            patch(
                "amdl.downloader.album_track_path", return_value=output_dir / "Artist/Album/01 - Song.m4a"
            ) as track_path,
        ):
            contexts = downloader._prepare_album_contexts(  # pyright: ignore[reportPrivateUsage]
                album, output_dir, "https://input.example"
            )

        client.fetch_content.assert_called_once_with(album.artwork_url)
        artwork_path.assert_called_once_with(output_dir, album)
        save.assert_called_once_with(
            b"artwork",
            output_dir / "Artist/Album/cover.jpg",
        )
        track_path.assert_called_once_with(
            output_dir,
            album,
            track,
        )

        assert contexts == [
            TrackContext(
                track, output_dir / "Artist/Album/01 - Song.m4a", "https://music.apple.com/album/1", b"artwork"
            ),
        ]

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_prepare_album_contexts_falls_back_to_track_url() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        track = TestDownloader.make_track(url="https://music.apple.com/track/1")
        album = TestDownloader.make_album(tracks=[track])

        with patch("amdl.downloader.album_track_path", return_value=Path("Album/01 - Song.m4a")):
            contexts = downloader._prepare_album_contexts(  # pyright: ignore[reportPrivateUsage]
                album, Path("downloads"), "https://input.example"
            )

        assert contexts[0].url == "https://music.apple.com/track/1"
        client.fetch_content.assert_not_called()

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_prepare_album_contexts_without_artwork() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        album = TestDownloader.make_album(
            tracks=[TestDownloader.make_track()],
        )

        with patch(
            "amdl.downloader.album_track_path",
            return_value=Path("Album/01 - Song.m4a"),
        ):
            contexts = downloader._prepare_album_contexts(  # pyright: ignore[reportPrivateUsage]
                album, Path("downloads"), "https://input.example"
            )

        assert contexts[0].artwork is None
        client.fetch_content.assert_not_called()

        downloader.executor.shutdown(wait=True)

    @staticmethod
    @pytest.mark.parametrize(
        ("album_artwork", "track_artwork", "expected"),
        [
            ("https://album.example/cover.jpg", "https://track.example/cover.jpg", "https://album.example/cover.jpg"),
            (None, "https://track.example/cover.jpg", "https://track.example/cover.jpg"),
            (None, None, None),
        ],
    )
    def test_get_album_artwork_url(
        album_artwork: str | None,
        track_artwork: str | None,
        expected: str | None,
    ) -> None:
        track = TestDownloader.make_track(artwork_url=track_artwork)
        album = TestDownloader.make_album(
            tracks=[track],
            artwork_url=album_artwork,
        )

        assert Downloader._get_album_artwork_url(album) == expected  # pyright: ignore[reportPrivateUsage]

    @staticmethod
    def test_get_context_art_from_album_artwork() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        context = TrackContext(
            TestDownloader.make_track(artwork_url="https://track.example/cover.jpg"),
            Path("song.m4a"),
            "https://input.example",
            b"album-artwork",
        )

        assert downloader._get_context_art(context) == b"album-artwork"  # pyright: ignore[reportPrivateUsage]
        client.fetch_content.assert_not_called()

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_get_context_art_from_track() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        context = TrackContext(
            TestDownloader.make_track(
                artwork_url="https://track.example/cover.jpg",
            ),
            Path("song.m4a"),
            "https://input.example",
        )
        client.fetch_content.return_value = b"track-artwork"

        result = downloader._get_context_art(context)  # pyright: ignore[reportPrivateUsage]

        assert result == b"track-artwork"
        client.fetch_content.assert_called_once_with(
            "https://track.example/cover.jpg",
        )

        downloader.executor.shutdown(wait=True)

    @staticmethod
    def test_get_context_art_without_artwork() -> None:
        downloader, client, _, _ = TestDownloader.make_downloader()

        context = TrackContext(
            TestDownloader.make_track(),
            Path("song.m4a"),
            "https://input.example",
        )

        assert downloader._get_context_art(context) is None  # pyright: ignore[reportPrivateUsage]
        client.fetch_content.assert_not_called()

        downloader.executor.shutdown(wait=True)
