from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from enum import Enum, auto
from pathlib import Path
from typing import Protocol

from amdl.apple_music import AppleMusicAuthenticator, AppleMusicClient, AppleMusicType
from amdl.domain import Album, Playlist, Track
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


class DownloadType(Enum):
    MEDIA = auto()
    ART = auto()


class DownloaderProtocol(Protocol):
    def __init__(self, parent: Downloader) -> None: ...
    def media(self, am_id: str, output_dir: Path, input_url: str, /) -> None: ...
    def art(self, am_id: str, output_dir: Path, /) -> None: ...


class Downloader:
    def __init__(self, auth: AppleMusicAuthenticator) -> None:
        self.client: AppleMusicClient = AppleMusicClient(auth)
        self.media_downloader: MediaDownloader = MediaDownloader(self.client)
        self.drm: WidevineDRM = WidevineDRM(self.client)
        self._downloaders: dict[AppleMusicType, type[DownloaderProtocol]] = {
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
                downloader.media(resource_id, output_dir, input_url)
            case DownloadType.ART:
                downloader.art(resource_id, output_dir)

    def download_track_audio(self, track: Track, output_path: Path) -> None:
        # TODO: check if output file exists first? skip if true?
        output_path.parent.mkdir(parents=True, exist_ok=True)

        playback = self.client.get_playback(track.id)

        playlist_url = HLSManifest.extract_playlist_url(playback)
        media_url = HLSManifest.extract_media_url(playlist_url)
        kid = HLSManifest.extract_kid(playlist_url)

        key = self.drm.get_content_key(kid, track.id)
        self.media_downloader.download_and_decrypt(media_url, output_path, kid, key)

        print(f"Downloaded track {track.id} to {output_path}")


class TrackDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, track_id: str, output_dir: Path, input_url: str, /) -> None:
        track = self.parent.client.get_track(track_id)
        self.download_track(track, output_dir, input_url)

    def download_track(self, track: Track, output_dir: Path, input_url: str) -> None:
        output_path = track_path(output_dir, track)
        url = str(track.url or input_url)
        artwork = self.parent.client.fetch_content(track.artwork_url)
        try:
            self.parent.download_track_audio(track, output_path)
            embed_track_metadata(track, output_path, url, artwork)
        except ValueError as e:
            print(f"Skipping track {track.id}: {e}")

    def art(self, track_id: str, output_dir: Path, /) -> None:
        track = self.parent.client.get_track(track_id)
        artwork = self.parent.client.fetch_content(track.artwork_url)
        output_path = track_artwork_path(output_dir, track)
        save_artwork(artwork, output_path)


class AlbumDownloader:
    type TrackContext = tuple[Album, Track, str, bytes]

    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, album_id: str, output_dir: Path, input_url: str, /) -> None:
        album = self.parent.client.get_album(album_id)
        return self.download_tracks([album], output_dir, input_url)

    def download_tracks(self, albums: list[Album], output_dir: Path, input_url: str) -> None:
        work_items = self._build_contexts(albums, input_url)

        def process_track(context: AlbumDownloader.TrackContext) -> None:
            album, track, url, artwork = context
            output_path = album_track_path(output_dir, album, track)
            try:
                self.parent.download_track_audio(track, output_path)
                embed_track_metadata(track, output_path, url, artwork)
            except ValueError as e:
                print(f"Skipping track {track.id}: {e}")

        with ThreadPoolExecutor(max_workers=8) as executor:
            _ = list(executor.map(process_track, work_items))

    def _build_contexts(self, albums: list[Album], input_url: str) -> Generator[TrackContext]:
        def build(album: Album) -> tuple[Album, str, bytes]:
            url = str(album.url or next((t.url for t in album.tracks if t.url is not None), None) or input_url)
            artwork = self.parent.client.fetch_content(album.artwork_url)
            return album, url, artwork

        with ThreadPoolExecutor(max_workers=8) as executor:
            album_contexts = list(executor.map(build, albums))

        return ((album, track, url, artwork) for album, url, artwork in album_contexts for track in album.tracks)

    def art(self, album_id: str, output_dir: Path, /) -> None:
        album = self.parent.client.get_album(album_id)
        artwork = self.parent.client.fetch_content(album.artwork_url)
        output_path = album_artwork_path(output_dir, album)
        save_artwork(artwork, output_path)


class ArtistDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, artist_id: str, output_dir: Path, input_url: str, /) -> None:
        artist = self.parent.client.get_artist(artist_id)
        AlbumDownloader(self.parent).download_tracks(artist.albums, output_dir, input_url)

    def art(self, artist_id: str, output_dir: Path, /) -> None:
        artist = self.parent.client.get_artist(artist_id)  # TODO: this could be significantly cheaper
        if not artist.artwork_url:
            raise ValueError("Artist does not have artwork")  # TODO: see if there are better `include`s to prevent this
            # TODO: alternatively, download all album artwork
        artwork = self.parent.client.fetch_content(artist.artwork_url)
        output_path = artist_artwork_path(output_dir, artist)
        save_artwork(artwork, output_path)


class PlaylistDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, playlist_id: str, output_dir: Path, input_url: str, /) -> None:
        playlist = self.parent.client.get_playlist(playlist_id)
        self.download_tracks(playlist, output_dir, input_url)

    def download_tracks(self, playlist: Playlist, output_dir: Path, input_url: str) -> None:
        work_list = tuple(enumerate(playlist.tracks, 1))

        def process_track(work_list: tuple[int, Track]) -> None:
            track_number, track = work_list
            url = str(track.url) if track.url else input_url
            output_path = playlist_track_path(output_dir, playlist, track, track_number)
            artwork = self.parent.client.fetch_content(track.artwork_url)
            try:
                self.parent.download_track_audio(track, output_path)
                embed_track_metadata(track, output_path, url, artwork)
            except ValueError as e:
                print(f"Skipping track {track.id}: {e}")

        with ThreadPoolExecutor(max_workers=8) as executor:
            _ = list(executor.map(process_track, work_list))

    def art(self, playlist_id: str, output_dir: Path, /) -> None:
        playlist = self.parent.client.get_playlist(playlist_id)  # TODO: this could be significantly cheaper
        artwork = self.parent.client.fetch_content(playlist.artwork_url)
        output_path = playlist_artwork_path(output_dir, playlist)
        save_artwork(artwork, output_path)


class ProfileDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def media(self, handle: str, output_dir: Path, input_url: str, /) -> None:
        # TODO: download all public playlists?
        _ = input_url
        self.art(handle, output_dir)

    def art(self, handle: str, output_dir: Path, /) -> None:
        profile = self.parent.client.get_profile(handle)
        artwork = self.parent.client.fetch_content(profile.artwork_url)
        output_path = profile_artwork_path(output_dir, profile)
        save_artwork(artwork, output_path)


class PinsDownloader:
    def __init__(self, parent: Downloader) -> None:
        self.parent: Downloader = parent

    def download(self, download_type: DownloadType, output_dir: Path) -> None:
        if download_type == DownloadType.MEDIA:
            self.media(output_dir)
        elif download_type == DownloadType.ART:
            self.art(output_dir)

    def media(self, output_dir: Path) -> None:
        fallback_url = ""  # TODO: feels bad?
        for pin in self.parent.client.get_pins():
            if pin.track:
                TrackDownloader(self.parent).download_track(pin.track, output_dir, fallback_url)
            elif pin.album:
                AlbumDownloader(self.parent).download_tracks([pin.album], output_dir, fallback_url)
            elif pin.artist:
                AlbumDownloader(self.parent).download_tracks(pin.artist.albums, output_dir, fallback_url)
            elif pin.playlist:
                PlaylistDownloader(self.parent).download_tracks(pin.playlist, output_dir, fallback_url)

    def art(self, output_dir: Path) -> None:
        for pin in self.parent.client.get_pins():  # TODO: this could be significantly cheaper
            if pin.artwork_url:
                artwork = self.parent.client.fetch_content(pin.artwork_url)
                output_path = pin_artwork_path(output_dir, pin)
                save_artwork(artwork, output_path)
