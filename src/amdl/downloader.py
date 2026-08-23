import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from amdl.apple_music.client import AppleMusicClient
from amdl.apple_music.urls import AppleMusicType
from amdl.media.downloader import MediaDownloader
from amdl.media.drm import WidevineDRM
from amdl.media.metadata import embed_track_metadata, save_artwork
from amdl.media.paths import (
    album_artwork_path,
    album_track_path,
    playlist_artwork_path,
    playlist_track_path,
    track_path,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from pathlib import Path
    from types import TracebackType

    from amdl.apple_music.auth import AppleMusicAuthenticator
    from amdl.domain import Album, Track

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TrackContext:
    track: Track
    output_path: Path
    url: str
    artwork: bytes | None = None


class Downloader:
    def __init__(self, auth: AppleMusicAuthenticator, *, max_workers: int = 8) -> None:
        self.client: AppleMusicClient = AppleMusicClient(auth)
        self.media_downloader: MediaDownloader = MediaDownloader(self.client)
        self.drm: WidevineDRM = WidevineDRM(self.client)
        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=max_workers)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, et: type[BaseException] | None, val: BaseException | None, tb: TracebackType | None) -> None:
        self.executor.shutdown(wait=True)

    def _map_downloader(self, am_type: AppleMusicType) -> Callable[..., Iterable[TrackContext]]:
        return {
            AppleMusicType.ALBUM: self.album,
            AppleMusicType.SONG: self.track,
            AppleMusicType.ARTIST: self.artist,
            AppleMusicType.PLAYLIST: self.playlist,
        }[am_type]

    def download(self, am_type: AppleMusicType, resource_id: str, output_dir: Path, input_url: str) -> None:
        logger.info("Initiating download for %s %s", am_type.name, resource_id)
        track_contexts = self._map_downloader(am_type)(resource_id, output_dir, input_url)
        futures = [self.executor.submit(self._download_context, context) for context in track_contexts]
        for future in as_completed(futures):
            future.result()

    def _download_context(self, context: TrackContext) -> None:
        if context.output_path.exists():
            logger.info("Skipping track %s: %s already exists", context.track.id, context.output_path)
            return
        try:
            self._download_track_audio(context.track, context.output_path)
            embed_track_metadata(context.track, context.output_path, context.url, self._get_context_art(context))
        except ValueError as e:
            logger.info("Skipping track %s: %s", context.track.id, e)

    def _download_track_audio(self, track: Track, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        playback = self.client.get_playback(track.id)
        key = self.drm.get_content_key(playback.kid, track.id) if playback.kid else None
        self.media_downloader.download(playback.url, output_path, playback.kid, key)
        logger.info("Downloaded track %s to %s", track.id, output_path)

    def track(self, track_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        track = self.client.get_track(track_id)
        url = str(track.url or input_url)
        output_path = track_path(output_dir, track)
        return (TrackContext(track, output_path, url),)

    def album(self, album_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        album = self.client.get_album(album_id)
        return self._prepare_album_contexts(album, output_dir, input_url)

    def artist(self, artist_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        artist = self.client.get_artist(artist_id)
        futures = [self.executor.submit(self._prepare_album_contexts, a, output_dir, input_url) for a in artist.albums]
        contexts: list[TrackContext] = []
        for future in as_completed(futures):
            contexts.extend(future.result())
        return contexts

    def playlist(self, playlist_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        playlist = self.client.get_playlist(playlist_id)

        if not playlist.tracks:
            raise ValueError("Playlist has no tracks.")

        if playlist.artwork_url:
            artwork = self.client.fetch_content(playlist.artwork_url)
            save_artwork(artwork, playlist_artwork_path(output_dir, playlist))

        return (
            TrackContext(track, playlist_track_path(output_dir, playlist, track, num), str(track.url or input_url))
            for num, track in enumerate(playlist.tracks, 1)
        )

    def _prepare_album_contexts(self, album: Album, output_dir: Path, input_url: str) -> list[TrackContext]:
        url = str(album.url or next((t.url for t in album.tracks if t.url is not None), None) or input_url)

        if artwork_url := self._get_album_artwork_url(album):
            artwork = self.client.fetch_content(artwork_url)
            save_artwork(artwork, album_artwork_path(output_dir, album))
        else:
            artwork = None
            logger.debug("Album %s has no artwork.", album.id)

        return [TrackContext(track, album_track_path(output_dir, album, track), url, artwork) for track in album.tracks]

    @staticmethod
    def _get_album_artwork_url(album: Album) -> str | None:
        artwork_url = album.artwork_url
        if artwork_url is None:
            artwork_url = next((t.artwork_url for t in album.tracks if t.artwork_url is not None), None)
            if artwork_url is not None:
                logger.warning("Album %s has no artwork. Using track artwork instead.", album.id)
        return artwork_url

    def _get_context_art(self, context: TrackContext) -> bytes | None:
        if context.artwork is not None:
            return context.artwork
        if context.track.artwork_url is not None:
            return self.client.fetch_content(context.track.artwork_url)
        return None
