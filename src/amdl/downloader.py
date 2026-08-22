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
    pin_artwork_path,
    playlist_artwork_path,
    playlist_track_path,
    profile_artwork_path,
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
            AppleMusicType.PROFILE: ProfileDownloader,
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
        return self.prepare_albums((album,), output_dir, input_url)

    def prepare_albums(self, albums: Iterable[Album], output_dir: Path, input_url: str) -> list[TrackContext]:
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(self._prepare_album, album, output_dir, input_url) for album in albums]
            contexts: list[TrackContext] = []
            for future in as_completed(futures):
                contexts.extend(future.result())
        return contexts

    def _prepare_album(self, album: Album, output_dir: Path, input_url: str) -> list[TrackContext]:
        url = str(album.url or next((track.url for track in album.tracks if track.url is not None), None) or input_url)
        artwork = self.parent.client.fetch_content(album.artwork_url)
        return [TrackContext(track, album_track_path(output_dir, album, track), url, artwork) for track in album.tracks]

    def art(self, album_id: str, output_dir: Path) -> None:
        album = self.parent.client.get_album(album_id)
        artwork = self.parent.client.fetch_content(album.artwork_url)
        save_artwork(artwork, album_artwork_path(output_dir, album))


class ArtistDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, artist_id: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        artist = self.parent.client.get_artist(artist_id)
        return AlbumDownloader(self.parent).prepare_albums(artist.albums, output_dir, input_url)

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
            TrackContext(t, playlist_track_path(output_dir, playlist, t, track_num), str(t.url or input_url))
            for track_num, t in enumerate(playlist.tracks, 1)
        )

    def art(self, playlist_id: str, output_dir: Path) -> None:
        playlist = self.parent.client.get_playlist(playlist_id)
        artwork = self.parent.client.fetch_content(playlist.artwork_url)
        save_artwork(artwork, playlist_artwork_path(output_dir, playlist))


class ProfileDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, handle: str, output_dir: Path, input_url: str, /) -> Iterable[TrackContext]:
        # TODO: download all public playlists?
        _ = input_url
        self.art(handle, output_dir)
        return ()

    def art(self, handle: str, output_dir: Path) -> None:
        profile = self.parent.client.get_profile(handle)
        artwork = self.parent.client.fetch_content(profile.artwork_url)
        save_artwork(artwork, profile_artwork_path(output_dir, profile))


class PinsDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def download(self, download_type: DownloadType, output_dir: Path) -> None:
        if download_type == DownloadType.MEDIA:
            self.parent.execute_media(self.media(output_dir))
        elif download_type == DownloadType.ART:
            self.art(output_dir)

    def media(self, output_dir: Path, /) -> Iterable[TrackContext]:
        fallback_url = ""  # TODO: feels bad?

        album_downloader = AlbumDownloader(self.parent)
        track_downloader = TrackDownloader(self.parent)
        playlist_downloader = PlaylistDownloader(self.parent)

        for pin in self.parent.client.get_pins():
            if pin.track:
                yield from track_downloader.media(pin.track.id, output_dir, fallback_url)
            elif pin.album:
                yield from album_downloader.prepare_albums((pin.album,), output_dir, fallback_url)
            elif pin.artist:
                yield from album_downloader.prepare_albums(pin.artist.albums, output_dir, fallback_url)
            elif pin.playlist:
                yield from playlist_downloader.media(pin.playlist.id, output_dir, fallback_url)

    def art(self, output_dir: Path, /) -> None:
        for pin in self.parent.client.get_pins():  # TODO: this could be significantly cheaper
            if not pin.artwork_url:
                continue
            artwork = self.parent.client.fetch_content(pin.artwork_url)
            save_artwork(artwork, pin_artwork_path(output_dir, pin))
