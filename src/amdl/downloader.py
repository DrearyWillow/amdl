import logging
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from types import TracebackType
from typing import Protocol, Self

from amdl.apple_music import AppleMusicAuthenticator, AppleMusicClient, AppleMusicType
from amdl.domain import Album, Track
from amdl.media import (
    HLSManifest,
    MediaDownloader,
    WidevineDRM,
    album_artwork_path,
    album_track_path,
    embed_track_metadata,
    save_artwork,
    track_artwork_path,
    track_path,
)
from amdl.media.paths import (
    artist_artwork_path,
    playlist_artwork_path,
    playlist_track_path,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrackContext:
    track: Track
    output_path: Path
    url: str
    artwork: bytes | None = None


class DownloadType(Enum):
    MEDIA = auto()
    ART = auto()


class ResourceDownloader(Protocol):
    def __init__(self, parent: Downloader) -> None: ...
    def media(self, resource_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]: ...
    def art(self, resource_id: str, output_dir: Path, /) -> None: ...


class Downloader:
    def __init__(self, auth: AppleMusicAuthenticator, *, max_workers: int = 8) -> None:
        self.client: AppleMusicClient = AppleMusicClient(auth)
        self.media_downloader: MediaDownloader = MediaDownloader(self.client)
        self.drm: WidevineDRM = WidevineDRM(self.client)

        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max_workers)

        self._downloaders: dict[AppleMusicType, type[ResourceDownloader]] = {
            AppleMusicType.ALBUM: AlbumDownloader,
            AppleMusicType.LIBRARY_ALBUM: AlbumDownloader,
            AppleMusicType.SONG: TrackDownloader,
            AppleMusicType.LIBRARY_SONG: TrackDownloader,
            AppleMusicType.ARTIST: ArtistDownloader,
            AppleMusicType.LIBRARY_ARTIST: ArtistDownloader,
            AppleMusicType.PLAYLIST: PlaylistDownloader,
            AppleMusicType.LIBRARY_PLAYLIST: PlaylistDownloader,
        }

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None
    ) -> None:
        self.executor.shutdown(wait=True)

    def download(
        self,
        download_type: DownloadType,
        am_type: AppleMusicType,
        resource_id: str,
        output_dir: Path,
        input_url: str | None = None,
    ) -> None:
        downloader_type = self._downloaders.get(am_type)

        if downloader_type is None:
            raise NotImplementedError(f"URL `{am_type.name}` not supported")

        downloader = downloader_type(self)

        match download_type:
            case DownloadType.MEDIA:
                if input_url is None:
                    raise ValueError("input_url is required for media downloads")

                self.execute_media(downloader.media(resource_id, output_dir, input_url))

            case DownloadType.ART:
                downloader.art(resource_id, output_dir)

    def execute_media(self, contexts: Iterable[TrackContext]) -> None:
        futures = [self.executor.submit(self._download_context, context) for context in contexts]
        for future in as_completed(futures):
            future.result()

    def _download_context(self, context: TrackContext) -> None:
        if context.output_path.exists():
            logger.info(f"Skipping track {context.track.id}: {context.output_path} already exists")
            return

        try:
            artwork = context.artwork
            if artwork is None:
                artwork = self.client.fetch_content(context.track.artwork_url)

            self._download_track_audio(context.track, context.output_path)
            embed_track_metadata(context.track, context.output_path, context.url, artwork)

        except ValueError as exc:
            logger.info(f"Skipping track {context.track.id}: {exc}")

    def _download_track_audio(self, track: Track, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        playback = self.client.get_playback(track.id)

        playlist_url = HLSManifest.extract_playlist_url(playback)
        media_url = HLSManifest.extract_media_url(playlist_url)
        kid = HLSManifest.extract_kid(playlist_url)

        key = self.drm.get_content_key(kid, track.id)
        self.media_downloader.download_and_decrypt(media_url, output_path, kid, key)
        logger.info(f"Downloaded track {track.id} to {output_path}")

    def prepare_album_contexts(self, album: Album, output_dir: Path, input_url: str) -> list[TrackContext]:
        url = str(album.url or next((t.url for t in album.tracks if t.url is not None), None) or input_url)
        artwork = self.client.fetch_content(album.artwork_url)
        return [TrackContext(track, album_track_path(output_dir, album, track), url, artwork) for track in album.tracks]


class TrackDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, track_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        track = self.parent.client.get_track(track_id)
        url = str(track.url or input_url)
        output_path = track_path(output_dir, track)
        return (TrackContext(track, output_path, url),)

    def art(self, track_id: str, output_dir: Path) -> None:
        track = self.parent.client.get_track(track_id)
        artwork = self.parent.client.fetch_content(track.artwork_url)
        save_artwork(artwork, track_artwork_path(output_dir, track))


class AlbumDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, album_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        album = self.parent.client.get_album(album_id)
        return self.parent.prepare_album_contexts(album, output_dir, input_url)

    def art(self, album_id: str, output_dir: Path) -> None:
        album = self.parent.client.get_album(album_id)
        artwork = self.parent.client.fetch_content(album.artwork_url)
        save_artwork(artwork, album_artwork_path(output_dir, album))


class ArtistDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, artist_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        artist = self.parent.client.get_artist(artist_id)
        futures = [
            self.parent.executor.submit(self.parent.prepare_album_contexts, album, output_dir, input_url)
            for album in artist.albums
        ]
        contexts: list[TrackContext] = []
        for future in as_completed(futures):
            contexts.extend(future.result())
        return contexts

    def art(self, artist_id: str, output_dir: Path) -> None:
        artist = self.parent.client.get_artist(artist_id)  # TODO: this could be significantly cheaper

        if not artist.artwork_url:
            # TODO: see if there are better `include`s to prevent this
            # TODO: alternatively, download all album artwork
            raise ValueError("Artist does not have artwork")

        artwork = self.parent.client.fetch_content(artist.artwork_url)
        save_artwork(artwork, artist_artwork_path(output_dir, artist))


class PlaylistDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, playlist_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        playlist = self.parent.client.get_playlist(playlist_id)

        return (
            TrackContext(track, playlist_track_path(output_dir, playlist, track, num), str(track.url or input_url))
            for num, track in enumerate(playlist.tracks, 1)
        )

    def art(self, playlist_id: str, output_dir: Path) -> None:
        playlist = self.parent.client.get_playlist(playlist_id)
        artwork = self.parent.client.fetch_content(playlist.artwork_url)
        save_artwork(artwork, playlist_artwork_path(output_dir, playlist))
