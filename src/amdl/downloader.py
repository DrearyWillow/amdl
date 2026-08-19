from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from amdl.apple_music.auth import AppleMusicAuthenticator
from amdl.apple_music.client import AppleMusicClient
from amdl.apple_music.urls import AppleMusicUrlType
from amdl.domain import Track
from amdl.media.downloader import MediaDownloader
from amdl.media.drm import WidevineDRM
from amdl.media.hls import HLSManifest
from amdl.media.metadata import embed_track_metadata, save_artwork
from amdl.media.paths import album_artwork_path, album_track_path, track_artwork_path, track_path


class Downloader:
    def __init__(self, auth: AppleMusicAuthenticator) -> None:
        self.client: AppleMusicClient = AppleMusicClient(auth)
        self.media: MediaDownloader = MediaDownloader(self.client)
        self.drm: WidevineDRM = WidevineDRM()
        self.drm.set_service_certificate(self.client.get_service_certificate())

    def download(
        self, am_type: AppleMusicUrlType, am_id: str, output_dir: Path, only_artwork: bool, input_url: str
    ) -> None:
        if am_type == AppleMusicUrlType.ALBUM:
            self.album(am_id, output_dir, only_artwork, input_url)
        elif am_type == AppleMusicUrlType.SONG:
            self.track(am_id, output_dir, only_artwork, input_url)

    def track(self, track_id: str, output_dir: Path, only_artwork: bool, input_url: str) -> None:
        track = self.client.get_track(track_id)
        output_path = track_path(output_dir, track)

        artwork = self.client.fetch_content(track.artwork_url)
        if only_artwork:
            output_path = track_artwork_path(output_dir, track)
            save_artwork(artwork, output_path)
            return

        self._download_track(track, output_path)
        embed_track_metadata(track, output_path, str(track.url or input_url), artwork)

    def album(self, album_id: str, output_dir: Path, only_artwork: bool, input_url: str) -> None:
        album = self.client.get_album(album_id)
        url = str(album.url or next((t.url for t in album.tracks if t.url is not None), None) or input_url)

        artwork = self.client.fetch_content(album.artwork_url)
        if only_artwork:
            output_path = album_artwork_path(output_dir, album)
            save_artwork(artwork, output_path)
            return

        def download(track: Track) -> None:
            output_path = album_track_path(output_dir, album, track)
            self._download_track(track, output_path)
            embed_track_metadata(track, output_path, url, artwork)

        with ThreadPoolExecutor(max_workers=8) as executor:
            _ = executor.map(download, album.tracks)

    def _download_track(self, track: Track, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        playback = self.client.get_playback(track.id)

        playlist_url = HLSManifest.extract_playlist_url(playback)
        media_url = HLSManifest.extract_media_url(playlist_url)
        kid = HLSManifest.extract_kid(playlist_url)

        challenge = self.drm.get_license_challenge(kid)
        license_data = self.client.get_license(challenge, kid, track.id)
        key = self.drm.parse_license_and_get_key(license_data)

        self.media.download_and_decrypt(media_url, output_path, kid, key)

        print(f"Downloaded track {track.id} to {output_path}")
