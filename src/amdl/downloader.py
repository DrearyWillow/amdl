from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# from typing import Protocol
from amdl.apple_music import AppleMusicAuthenticator, AppleMusicClient, AppleMusicUrlType
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


class Downloader:
    def __init__(self, auth: AppleMusicAuthenticator) -> None:
        self.client: AppleMusicClient = AppleMusicClient(auth)
        self.media_downloader: MediaDownloader = MediaDownloader(self.client)
        self.drm: WidevineDRM = WidevineDRM(self.client)

    def media(self, am_type: AppleMusicUrlType, am_id: str, output_dir: Path, input_url: str) -> None:
        match am_type:
            case AppleMusicUrlType.ALBUM:
                AlbumDownloader(self).media(am_id, output_dir, input_url)
            case AppleMusicUrlType.SONG:
                TrackDownloader(self).media(am_id, output_dir, input_url)

    def art(self, am_type: AppleMusicUrlType, am_id: str, output_dir: Path) -> None:
        match am_type:
            case AppleMusicUrlType.ALBUM:
                AlbumDownloader(self).art(am_id, output_dir)
            case AppleMusicUrlType.SONG:
                TrackDownloader(self).art(am_id, output_dir)

    def download_track_audio(self, track: Track, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        playback = self.client.get_playback(track.id)

        playlist_url = HLSManifest.extract_playlist_url(playback)
        media_url = HLSManifest.extract_media_url(playlist_url)
        kid = HLSManifest.extract_kid(playlist_url)

        key = self.drm.get_content_key(kid, track.id)
        self.media_downloader.download_and_decrypt(media_url, output_path, kid, key)

        print(f"Downloaded track {track.id} to {output_path}")


# class DownloadHandler(Protocol):
#     def media(self, am_id: str, output_dir: Path, input_url: str) -> None: ...
#     def art(self, am_id: str, output_dir: Path) -> None: ...


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
        self.parent.download_track_audio(track, output_path)
        embed_track_metadata(track, output_path, url, artwork)

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
            self.parent.download_track_audio(track, output_path)
            embed_track_metadata(track, output_path, url, artwork)

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

        def process_track(work_list: tuple[Track, int]) -> None:
            track, track_number = work_list
            url = str(track.url) if track.url else input_url
            output_path = playlist_track_path(output_dir, playlist, track, track_number)
            artwork = self.parent.client.fetch_content(track.artwork_url)
            self.parent.download_track_audio(track, output_path)
            embed_track_metadata(track, output_path, url, artwork)

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

    def media(self, _: str, output_dir: Path, input_url: str, /) -> None:
        for pin in self.parent.client.get_pins():
            if pin.track:
                TrackDownloader(self.parent).download_track(pin.track, output_dir, input_url)
            elif pin.album:
                AlbumDownloader(self.parent).download_tracks([pin.album], output_dir, input_url)
            elif pin.artist:
                AlbumDownloader(self.parent).download_tracks(pin.artist.albums, output_dir, input_url)
            elif pin.playlist:
                PlaylistDownloader(self.parent).download_tracks(pin.playlist, output_dir, input_url)

    def art(self, output_dir: Path, /) -> None:
        for pin in self.parent.client.get_pins():
            if pin.artwork_url:
                artwork = self.parent.client.fetch_content(pin.artwork_url)
                output_path = pin_artwork_path(output_dir, pin)
                save_artwork(artwork, output_path)
