from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from amdl.apple_music import AppleMusicAuthenticator, AppleMusicClient, AppleMusicUrlType
from amdl.domain import Track
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


class Downloader:
    def __init__(self, auth: AppleMusicAuthenticator) -> None:
        self.client: AppleMusicClient = AppleMusicClient(auth)
        self.media_downloader: MediaDownloader = MediaDownloader(self.client)
        self.drm: WidevineDRM = WidevineDRM(self.client)

    def media(self, am_type: AppleMusicUrlType, am_id: str, output_dir: Path, input_url: str) -> None:
        match am_type:
            case AppleMusicUrlType.ALBUM:
                self.album(am_id, output_dir, input_url)
            case AppleMusicUrlType.SONG:
                self.track(am_id, output_dir, input_url)

    def art(self, am_type: AppleMusicUrlType, am_id: str, output_dir: Path) -> None:
        match am_type:
            case AppleMusicUrlType.ALBUM:
                self.album_artwork(am_id, output_dir)
            case AppleMusicUrlType.SONG:
                self.track_artwork(am_id, output_dir)

    def track(self, track_id: str, output_dir: Path, input_url: str) -> None:
        track = self.client.get_track(track_id)
        output_path = track_path(output_dir, track)
        url = str(track.url or input_url)
        artwork =  self.client.fetch_content(track.artwork_url)
        self._download_track_audio(track, output_path)
        embed_track_metadata(track, output_path, url, artwork)

    def track_artwork(self, track_id: str, output_dir: Path) -> None:
        track = self.client.get_track(track_id)
        artwork = self.client.fetch_content(track.artwork_url)
        output_path = track_artwork_path(output_dir, track)
        save_artwork(artwork, output_path)

    def album(self, album_id: str, output_dir: Path, input_url: str) -> None:
        album = self.client.get_album(album_id)
        url = str(album.url or next((t.url for t in album.tracks if t.url is not None), None) or input_url)
        artwork = self.client.fetch_content(album.artwork_url)

        def download(track: Track) -> None:
            output_path = album_track_path(output_dir, album, track)
            self._download_track_audio(track, output_path)
            embed_track_metadata(track, output_path, url, artwork)

        with ThreadPoolExecutor(max_workers=8) as executor:
            _ = executor.map(download, album.tracks)

    def album_artwork(self, album_id: str, output_dir: Path) -> None:
        album = self.client.get_album(album_id)
        artwork = self.client.fetch_content(album.artwork_url)
        output_path = album_artwork_path(output_dir, album)
        save_artwork(artwork, output_path)

    def _download_track_audio(self, track: Track, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        playback = self.client.get_playback(track.id)

        playlist_url = HLSManifest.extract_playlist_url(playback)
        media_url = HLSManifest.extract_media_url(playlist_url)
        kid = HLSManifest.extract_kid(playlist_url)

        key = self.drm.get_content_key(kid, track.id)
        self.media_downloader.download_and_decrypt(media_url, output_path, kid, key)

        print(f"Downloaded track {track.id} to {output_path}")
