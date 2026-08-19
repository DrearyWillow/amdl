import base64
import re
import subprocess
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import keyring
import m3u8
from keyring.errors import PasswordDeleteError
from mutagen.mp4 import MP4, MP4Cover
from playwright.sync_api import BrowserContext, sync_playwright
from pywidevine import PSSH, Cdm, Device
from pywidevine.license_protocol_pb2 import WidevinePsshData
from requests import Session

from amdl.arguments import ArgParser
from amdl.config import (
    APPLE_MUSIC_API,
    APPLE_MUSIC_URL,
    KEYRING_NAME,
    LICENSE_URL,
    SAVE_DIRECTORY,
    WEB_PLAYBACK_URL,
    WIDEVINE_CERT_URL,
)
from amdl.domain.album import Album
from amdl.domain.playback import Playback
from amdl.domain.track import Track
from amdl.json_type import JSON
from amdl.parser.album import AppleMusicAlbumParser
from amdl.parser.license import AppleMusicLicenseParser
from amdl.parser.playback import AppleMusicPlaybackParser
from amdl.parser.track import AppleMusicTrackParser


def is_library_album(album_id: str) -> bool:
    return album_id.startswith("l.")


def is_library_track(track_id: str) -> bool:
    return track_id.startswith("i.")


@dataclass
class AppleMusicCredentials:
    user_token: str
    media_token: str


class AppleMusicAuth:
    def __init__(self) -> None:
        self.credentials: AppleMusicCredentials | None = None

    def login(self) -> bool:
        credentials = self._load_credentials()
        if credentials is not None:
            self.credentials = credentials
            return True
        self.clear_credentials()

        credentials = self._browser_login()
        if credentials is None:
            return False

        self.credentials = credentials
        self._save_credentials(credentials)
        return True

    def clear_credentials(self) -> None:
        self.credentials = None
        for key in ("user_token", "media_token"):
            try:
                keyring.delete_password(KEYRING_NAME, key)
            except PasswordDeleteError:
                pass

    def _load_credentials(self) -> AppleMusicCredentials | None:
        user_token = keyring.get_password(KEYRING_NAME, "user_token")
        media_token = keyring.get_password(KEYRING_NAME, "media_token")
        return AppleMusicCredentials(user_token, media_token) if user_token and media_token else None

    def _save_credentials(self, credentials: AppleMusicCredentials) -> None:
        keyring.set_password(KEYRING_NAME, "user_token", credentials.user_token)
        keyring.set_password(KEYRING_NAME, "media_token", credentials.media_token)

    def _browser_login(self) -> AppleMusicCredentials | None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            try:
                context = browser.new_context()
                page = context.new_page()
                _ = page.goto(APPLE_MUSIC_URL)

                while True:
                    user_token = self._find_user_token(context)
                    if user_token is not None:
                        media_token = self._acquire_media_token(context)
                        return AppleMusicCredentials(user_token, media_token)
                    page.wait_for_timeout(500)
            finally:
                browser.close()

    @staticmethod
    def _find_user_token(context: BrowserContext) -> str | None:
        for cookie in context.cookies():
            if cookie.get("name") == "media-user-token":
                return cookie.get("value")
        return None

    @staticmethod
    def _acquire_media_token(context: BrowserContext) -> str:
        # fetch main page
        response = context.request.get(APPLE_MUSIC_URL)
        html = response.text()

        # find index JS file
        match = re.search(r'/assets/index[^"]*\.js', html)
        if not match:
            raise RuntimeError("Could not find index JS URI")
        index_js_uri = match.group(0)

        # fetch index JS file
        response = context.request.get(f"{APPLE_MUSIC_URL}{index_js_uri}")
        js = response.text()

        # extract the JWT token (starts with eyJ)
        # https://github.com/xiaohaiya/musicdl/commit/2526730caa4ebf3982d10903d91211549ec57505
        match = re.search(r'"(eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)"', js)
        if not match:
            raise RuntimeError("Could not find media token in JS")
        token = match.group(1)
        return token


class AppleMusicAPI:
    def __init__(self, http: Session, auth: AppleMusicAuth) -> None:
        self.http: Session = http
        self.auth: AppleMusicAuth = auth

    def headers(self) -> dict[str, str]:
        creds = self.auth.credentials
        if creds is None:
            raise RuntimeError("Apple Music session is not authenticated")
        return {
            "Authorization": f"Bearer {creds.media_token}",
            "Music-User-Token": creds.user_token,
            "media-user-token": creds.user_token,
            "x-apple-music-user-token": creds.user_token,
            "Origin": APPLE_MUSIC_URL,
            "Referer": APPLE_MUSIC_URL,
        }

    def post(self, url: str, json: Mapping[str, str | bool]) -> JSON:
        response = self.http.post(url, headers=self.headers(), json=json)
        response.raise_for_status()
        return cast(JSON, response.json())

    def get(self, url: str, params: dict[str, str] | None = None) -> JSON:
        response = self.http.get(url, headers=self.headers(), params=params)
        print(f"{url} (GET) -> {response.status_code}")
        response.raise_for_status()
        return cast(JSON, response.json())

    def get_album(self, album_id: str) -> Album:
        params = {"include": "catalog,songs"} if is_library_album(album_id) else None
        response = self.get(f"{APPLE_MUSIC_API}/me/library/albums/{album_id}", params=params)
        return AppleMusicAlbumParser.parse(response)

    def get_track(self, track_id: str) -> Track:
        path = f"me/library/songs/{track_id}" if is_library_track(track_id) else f"catalog/us/songs/{track_id}"
        response = self.get(f"{APPLE_MUSIC_API}/{path}", params={"include": "albums,catalog"})
        return AppleMusicTrackParser.parse(response)


class AppleMusicPlayback:
    def __init__(self, session: AppleMusicAPI) -> None:
        self.session: AppleMusicAPI = session

    def get_service_certificate(self) -> bytes:
        return self.session.http.get(WIDEVINE_CERT_URL).content

    def get_playback(self, track_id: str) -> Playback:
        body = {"universalLibraryId": track_id} if is_library_track(track_id) else {"salableAdamId": track_id}
        return AppleMusicPlaybackParser.parse(self.session.post(WEB_PLAYBACK_URL, json=body))

    def get_license(self, challenge: str, kid_b64: str, track_id: str) -> bytes:
        kid_bytes = base64.b64decode(kid_b64)
        kid_encoded = base64.b64encode(kid_bytes).decode()
        response = self.session.post(
            LICENSE_URL,
            json={
                "challenge": challenge,
                "key-system": "com.widevine.alpha",
                "adamId": track_id,
                "isLibrary": is_library_track(track_id),
                "user-initiated": True,
                "uri": f"data:;base64,{kid_encoded}",
            },
        )
        return base64.b64decode(AppleMusicLicenseParser.parse(response))


class WidevineDRM:
    def __init__(self) -> None:
        device_path: Path = Path(__file__).parent / "device.wvd"
        assert device_path.exists(), f"Widevine device file not found at {device_path}"
        self.device: Device = Device.load(device_path)
        self.cdm: Cdm = Cdm.from_device(self.device)
        self.session_id: bytes = self.cdm.open()

    def set_service_certificate(self, cert: bytes) -> None:
        _ = self.cdm.set_service_certificate(self.session_id, cert)

    def generate_pssh(self, kid_b64: str) -> PSSH:
        """Generate PSSH (Protection Scheme Specific Header) from Key ID"""
        kid = base64.standard_b64decode(kid_b64)
        wv_data = WidevinePsshData(key_ids=[kid], algorithm="AESCTR", protection_scheme=0x63656E63)
        pssh = PSSH.new(system_id=PSSH.SystemId.Widevine, init_data=wv_data, version=0)
        return pssh

    def get_license_challenge(self, kid_b64: str) -> str:
        """Generate license challenge for key request"""
        pssh = self.generate_pssh(kid_b64)
        challenge = base64.b64encode(self.cdm.get_license_challenge(self.session_id, pssh)).decode()
        return challenge

    def parse_license_and_get_key(self, license_data: bytes) -> str:
        """Parse license and extract content key"""
        self.cdm.parse_license(self.session_id, license_data)
        keys = self.cdm.get_keys(self.session_id)
        content_key = next(k.key for k in keys if k.type == "CONTENT")
        return base64.b64encode(bytes(content_key)).decode("utf-8")


class HLSParser:
    @staticmethod
    def extract_playlist_url(playback: Playback) -> str:
        quality_priorities = ("28:ctrp256", "32:ctrp64")
        for song in playback.songs:
            for target_flavor in quality_priorities:
                for asset in song.assets:
                    if asset.url and asset.flavor == target_flavor:
                        return str(asset.url)
        raise ValueError("No suitable playback URL found")

    @staticmethod
    def extract_kid(playlist_url: str) -> str:
        playlist = m3u8.load(str(playlist_url))
        if not playlist.keys or not playlist.keys[0] or not isinstance(playlist.keys[0].uri, str):
            raise ValueError("No encryption key found in playlist")
        return playlist.keys[0].uri.replace("data:;base64,", "")

    @staticmethod
    def extract_media_url(playlist_url: str) -> str:
        if not playlist_url.endswith(".aac.wa.m3u8"):
            return playlist_url
        playlist = m3u8.load(playlist_url)
        filename = playlist.files[1] if len(playlist.files) > 1 else playlist.files[0]
        parts = playlist_url.split("/")
        base_url = "/".join(parts[:-1])
        return f"{base_url}/{filename}"


class PathConstructor:
    @staticmethod
    def sanitize_filename_component(value: str) -> str:
        value = value.strip()
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
        value = value.rstrip(". ")
        return value or "Unknown"

    @classmethod
    def track(cls, output_dir: Path, track: Track) -> Path:
        artist = cls.sanitize_filename_component(track.artist_name)
        song = cls.sanitize_filename_component(track.name)
        return output_dir / artist / f"{song}.m4a"

    @classmethod
    def track_artwork(cls, output_dir: Path, track: Track) -> Path:
        artist = cls.sanitize_filename_component(track.artist_name)
        song = cls.sanitize_filename_component(track.name)
        return output_dir / f"{artist} - {song}.jpg"

    @classmethod
    def album_track(cls, output_dir: Path, album: Album, track: Track) -> Path:
        artist = cls.sanitize_filename_component(album.artist_name)
        album_name = cls.sanitize_filename_component(album.name)
        song = cls.sanitize_filename_component(track.name)
        return output_dir / artist / album_name / f"{track.track_number:02d} - {song}.m4a"

    @classmethod
    def album_artwork(cls, output_dir: Path, album: Album) -> Path:
        artist = cls.sanitize_filename_component(album.artist_name)
        album_name = cls.sanitize_filename_component(album.name)
        return output_dir / f"{artist} - {album_name}.jpg"


class AppleMusicDownloaderCore:
    def __init__(self, session: Session) -> None:
        self.http: Session = session
        self.decryptor: Path = Path(__file__).parent / "mp4decrypt"
        assert self.decryptor.exists(), f"mp4decrypt missing at {self.decryptor}"

    def download_encrypted(self, media_url: str, output_path: Path) -> Path:
        response = self.http.get(media_url)
        response.raise_for_status()
        encrypted_path = output_path.with_suffix(output_path.suffix + ".encrypted")
        with encrypted_path.open("wb") as file:
            _ = file.write(response.content)
        return encrypted_path

    def decrypt(self, encrypted_path: Path, output_path: Path, kid: str, key: str) -> None:
        kid_hex = base64.b64decode(kid).hex()
        key_hex = base64.b64decode(key).hex()
        cmd = [self.decryptor, "--key", f"{kid_hex}:{key_hex}", encrypted_path, output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"mp4decrypt failed: {result.stderr}")

    def download_and_decrypt(self, media_url: str, output_path: Path, kid: str, key: str) -> None:
        encrypted_path = self.download_encrypted(media_url, output_path)
        self.decrypt(encrypted_path, output_path, kid, key)
        encrypted_path.unlink(missing_ok=True)


class AppleMusicDownloader:
    def __init__(self, api: AppleMusicAPI) -> None:
        self.amp: AppleMusicPlayback = AppleMusicPlayback(api)
        self.http: Session = api.http
        self.core: AppleMusicDownloaderCore = AppleMusicDownloaderCore(self.http)
        self.drm: WidevineDRM = WidevineDRM()
        self.drm.set_service_certificate(self.amp.get_service_certificate())

    def prepare_track(self, track_id: str) -> tuple[str, str]:
        playback = self.amp.get_playback(track_id)
        playlist_url = HLSParser.extract_playlist_url(playback)
        media_url = HLSParser.extract_media_url(playlist_url)
        kid = HLSParser.extract_kid(playlist_url)
        return media_url, kid

    def download_track(self, track: Track, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        media_url, kid = self.prepare_track(track.id)
        challenge = self.drm.get_license_challenge(kid)
        license_data = self.amp.get_license(challenge, kid, track.id)
        key = self.drm.parse_license_and_get_key(license_data)
        self.core.download_and_decrypt(media_url, output_path, kid, key)
        print(f"Downloaded track {track.id} to {output_path}")

    def fetch_artwork(self, url: str) -> bytes:
        response = self.http.get(url, timeout=10)
        response.raise_for_status()
        return response.content

    @staticmethod
    def save_artwork(image_bytes: bytes, output_path: Path) -> None:
        with output_path.open("wb") as file:
            _ = file.write(image_bytes)
        print(f"Downloaded artwork to {output_path}")

    @staticmethod
    def embed_track_metadata(track: Track, path: Path, url: str | None = None, artwork: bytes | None = None) -> None:
        mp4 = MP4(path)

        if mp4.tags is None:
            mp4.add_tags()
        tags = mp4.tags
        assert tags is not None

        tags["\xa9nam"] = track.name
        tags["\xa9ART"] = track.artist_name
        tags["\xa9alb"] = track.album_name
        tags["\xa9day"] = str(track.release_date)
        tags["trkn"] = [(track.track_number, 0)]

        if url:
            tags["\xa9url"] = url
            tags["purl"] = [url]
        if artwork:
            tags["covr"] = [MP4Cover(artwork)]

        mp4.save()  # pyright: ignore[reportUnknownMemberType]


class DownloadManager:
    def __init__(self, api: AppleMusicAPI) -> None:
        self.api: AppleMusicAPI = api
        self.downloader: AppleMusicDownloader = AppleMusicDownloader(api)

    def track(self, track_id: str, output_dir: Path, only_artwork: bool, input_url: str) -> None:
        track = self.api.get_track(track_id)
        output_path = PathConstructor.track(output_dir, track)

        artwork = self.downloader.fetch_artwork(track.artwork_url)
        if only_artwork:
            output_path = PathConstructor.track_artwork(output_dir, track)
            self.downloader.save_artwork(artwork, output_path)
            return

        self.downloader.download_track(track, output_path)
        self.downloader.embed_track_metadata(track, output_path, str(track.url) or input_url, artwork)

    def album(self, album_id: str, output_dir: Path, only_artwork: bool, input_url: str) -> None:
        album = self.api.get_album(album_id)
        url = str(album.url or next(t.url for t in album.tracks) or input_url)

        artwork = self.downloader.fetch_artwork(album.artwork_url)
        if only_artwork:
            output_path = PathConstructor.album_artwork(output_dir, album)
            self.downloader.save_artwork(artwork, output_path)
            return

        def download(track: Track) -> None:
            output_path = PathConstructor.album_track(output_dir, album, track)
            self.downloader.download_track(track, output_path)
            self.downloader.embed_track_metadata(track, output_path, url, artwork)

        with ThreadPoolExecutor(max_workers=8) as executor:
            _ = executor.map(download, album.tracks)


def main() -> None:
    args = ArgParser.parse()
    auth = AppleMusicAuth()

    if args.logout:
        auth.clear_credentials()
        return

    assert args.url is not None
    url_type, am_id = ArgParser.apple_music_url(args.url)

    if not auth.login():
        raise SystemExit("Authentication failed")

    manager = DownloadManager(AppleMusicAPI(Session(), auth))
    output_dir = args.directory or Path(SAVE_DIRECTORY).expanduser() if SAVE_DIRECTORY else Path.cwd()

    if url_type.startswith("album"):
        manager.album(am_id, output_dir, args.only_artwork, args.url)
    elif url_type.startswith("song"):
        manager.track(am_id, output_dir, args.only_artwork, args.url)
    else:
        raise SystemExit(f"Unsupported Apple Music URL type: {url_type}")


if __name__ == "__main__":
    main()
