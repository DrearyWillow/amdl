import base64
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import keyring
import m3u8
from keyring.errors import PasswordDeleteError
from playwright.sync_api import BrowserContext, sync_playwright
from pywidevine import PSSH, Cdm, Device
from pywidevine.license_protocol_pb2 import WidevinePsshData
from requests import Session

APPLE_MUSIC_URL = "https://music.apple.com"
APPLE_MUSIC_API = "https://amp-api.music.apple.com/v1"
WEB_PLAYBACK_URL = "https://play.music.apple.com/WebObjects/MZPlay.woa/wa/webPlayback"
WIDEVINE_CERT_URL = "https://play.itunes.apple.com/WebObjects/MZPlay.woa/wa/widevineCert"
LICENSE_URL = "https://play.itunes.apple.com/WebObjects/MZPlay.woa/wa/acquireWebPlaybackLicense"
KEYRING_NAME = "AppleMusicDownloader"

type JSON = str | int | float | bool | None | list[JSON] | dict[str, JSON]

# TODO:
# arg parsing / options
# filename options
# albums


def is_library_album(album_id: str) -> bool:
    return album_id.startswith("l.")


def is_library_track(track_id: str) -> bool:
    return track_id.startswith("i.")


@dataclass
class AppleMusicCredentials:
    user_token: str
    media_token: str


@dataclass
class PlaybackAsset:
    flavor: str | None
    url: str | None


@dataclass
class PlaybackSong:
    assets: list[PlaybackAsset]


@dataclass
class PlaybackData:
    raw: dict[str, JSON]

    @property
    def failed(self) -> bool:
        return self.failure_message is not None

    @property
    def failure_message(self) -> str | None:
        if "dialog" in self.raw and isinstance(self.raw["dialog"], dict) and "message" in self.raw["dialog"]:
            message = cast(str, self.raw["dialog"]["message"])
        else:
            message = self.raw.get("customerMessage") or self.raw.get("failureType")
        return str(message) if message else None

    @property
    def songs(self) -> list[PlaybackSong]:
        return [
            PlaybackSong(
                assets=[
                    PlaybackAsset(flavor=asset.get("flavor"), url=asset.get("URL")) for asset in song.get("assets", [])
                ]
            )
            for song in cast(list[dict[str, list[dict[str, str]]]], self.raw.get("songList", []))
        ]


class AppleMusicSession:
    def __init__(self, http: Session):
        self.http: Session = http
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
        try:
            keyring.delete_password(KEYRING_NAME, "user_token")
            keyring.delete_password(KEYRING_NAME, "media_token")
        except PasswordDeleteError:
            pass

    def headers(self) -> dict[str, str]:
        if self.credentials is None:
            raise RuntimeError("Apple Music session is not authenticated")
        return {
            "Authorization": f"Bearer {self.credentials.media_token}",
            "Music-User-Token": self.credentials.user_token,
            "media-user-token": self.credentials.user_token,
            "x-apple-music-user-token": self.credentials.user_token,
            "Origin": APPLE_MUSIC_URL,
            "Referer": APPLE_MUSIC_URL,
        }

    def post(self, url: str, json: Mapping[str, JSON]) -> JSON:
        response = self.http.post(url, headers=self.headers(), json=json)
        print(f"{url} (POST) -> {response.status_code}")
        response.raise_for_status()
        return cast(JSON, response.json())

    def get(self, url: str, params: dict[str, str] | None = None) -> JSON:
        response = self.http.get(url, headers=self.headers(), params=params)
        print(f"{url} (GET) -> {response.status_code}")
        response.raise_for_status()
        return cast(JSON, response.json())

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
    def _acquire_media_token(context: BrowserContext):
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
    def __init__(self, auth: AppleMusicSession):
        self.session: AppleMusicSession = auth

    def get(self, path: str, params: dict[str, str]) -> JSON:
        return self.session.get(f"{APPLE_MUSIC_API}/{path}", params=params)

    def get_album_info(self, album_id: str) -> JSON:
        print(f"Fetching album: {album_id}")
        if is_library_album(album_id):
            return self._get_library_album(album_id)
        return self._get_catalog_album(album_id)

    def _get_catalog_album(self, album_id: str) -> JSON:
        return self.get(
            f"catalog/us/albums/{album_id}",
            params={
                "include": "artists,library",
                "include[songs]": "artists,library",
                "extend": "inFavorites,isCompilation",
                "extend[songs]": "inFavorites",
            },
        )

    def _get_library_album(self, album_id: str) -> JSON:
        return self.get(
            f"me/library/albums/{album_id}",
            params={
                "include": "catalog,artists,songs",
                "include[songs]": "artists",
                "extend": "inFavorites,isCompilation",
                "extend[songs]": "inFavorites",
            },
        )


class AppleMusicPlayback:
    def __init__(self, session: AppleMusicSession):
        self.session: AppleMusicSession = session

    def get_service_certificate(self) -> bytes:
        return self.session.http.get(WIDEVINE_CERT_URL).content

    def get_playback(self, track_id: str) -> PlaybackData:
        body = {"universalLibraryId": track_id} if is_library_track(track_id) else {"salableAdamId": track_id}
        playback = PlaybackData(cast(dict[str, JSON], self.session.post(WEB_PLAYBACK_URL, json=body)))
        if playback.failed:
            print(f"Got webplayback response: {playback=}")
            raise RuntimeError(playback.failure_message)
        return playback

    def get_license(self, challenge: str, kid_b64: str, track_id: str) -> bytes:
        kid_bytes = base64.b64decode(kid_b64)
        kid_encoded = base64.b64encode(kid_bytes).decode()
        data = cast(
            dict[str, JSON],
            self.session.post(
                LICENSE_URL,
                json={
                    "challenge": challenge,
                    "key-system": "com.widevine.alpha",
                    "adamId": track_id,
                    "isLibrary": is_library_track(track_id),
                    "user-initiated": True,
                    "uri": f"data:;base64,{kid_encoded}",
                },
            ),
        )

        status = cast(int | str, data.get("status"))
        if status != 0:
            error_messages = {
                -1001: "Invalid PSSH.",
                -1002: "You do not own this title.",
                -1004: "Maximum number of simultaneous streams exceeded.",
                -1017: "This content is geo-restricted.",
                -1021: "Device has insufficient security level.",
            }
            error_msg = (
                error_messages.get(status, f"License error: {status}")
                if isinstance(status, int)
                else "License error: Unknown"
            )
            print(f"License error {status}: {error_msg}")
            raise ValueError(error_msg)

        license_data = data.get("license")
        if not isinstance(license_data, str) or not license_data:
            print("No license data in response")
            raise ValueError("No license data received from Apple")

        return base64.b64decode(license_data)


class TrackDownloader:
    def __init__(self, session: Session):
        self.http: Session = session
        self.decryptor: str = os.path.join(os.path.dirname(__file__), "mp4decrypt")
        assert os.path.exists(self.decryptor), f"mp4decrypt missing at {self.decryptor}"

    def download_encrypted(self, media_url: str, output_path: str) -> str:
        response = self.http.get(media_url)
        response.raise_for_status()
        encrypted_path = f"{output_path}.encrypted"
        with open(encrypted_path, "wb") as file:
            _ = file.write(response.content)
        return encrypted_path

    def decrypt(self, encrypted_path: str, output_path: str, kid: str, key: str) -> None:
        kid_hex = base64.b64decode(kid).hex()
        key_hex = base64.b64decode(key).hex()
        cmd = [self.decryptor, "--key", f"{kid_hex}:{key_hex}", encrypted_path, output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(f"mp4decrypt failed: {result.stderr}")

    def download_and_decrypt(self, media_url: str, output_path: str, kid: str, key: str) -> None:
        encrypted_path = self.download_encrypted(media_url, output_path)
        self.decrypt(encrypted_path, output_path, kid, key)
        if os.path.exists(encrypted_path):
            os.remove(encrypted_path)


class WidevineDRM:
    def __init__(self) -> None:
        device_path: str = os.path.join(os.path.dirname(__file__), "device.wvd")
        assert os.path.exists(device_path), f"Widevine device file not found at {device_path}."
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

        # Get content key
        content_key = next(k.key for k in keys if k.type == "CONTENT")
        return base64.b64encode(bytes(content_key)).decode("utf-8")


class HLSParser:
    @staticmethod
    def extract_playlist_url(playback: PlaybackData) -> str:
        quality_priorities = [
            ("28:ctrp256", "256kbps high quality"),
            ("32:ctrp64", "64kbps standard quality"),
        ]
        for song in playback.songs:
            for target_flavor, quality_name in quality_priorities:
                for asset in song.assets:
                    if asset.url and asset.flavor == target_flavor:
                        print(f"Using {quality_name} stream (flavor: {asset.flavor})")
                        return asset.url
        raise ValueError("No suitable playback URL found")

    @staticmethod
    def extract_kid(playlist_url: str) -> str:
        playlist = m3u8.load(playlist_url)
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


class AppleMusicDownloader:
    def __init__(self, amp: AppleMusicPlayback):
        self.amp: AppleMusicPlayback = amp
        self.drm: WidevineDRM = WidevineDRM()
        self.track_downloader: TrackDownloader = TrackDownloader(amp.session.http)
        cert = self.amp.get_service_certificate()
        self.drm.set_service_certificate(cert)

    def prepare_track(self, track_id: str) -> tuple[str, str]:
        print(f"Preparing track {track_id} for playback")
        playback = self.amp.get_playback(track_id)
        playlist_url = HLSParser.extract_playlist_url(playback)
        media_url = HLSParser.extract_media_url(playlist_url)
        kid = HLSParser.extract_kid(playlist_url)
        return media_url, kid

    def download_track(self, track_id: str, output_path: str) -> None:
        media_url, kid = self.prepare_track(track_id)
        challenge = self.drm.get_license_challenge(kid)
        license_data = self.amp.get_license(challenge, kid, track_id)
        key = self.drm.parse_license_and_get_key(license_data)
        self.track_downloader.download_and_decrypt(media_url, output_path, kid, key)
        print(f"Downloaded track {track_id} to {output_path}")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <Apple Music URL>")
    argument = sys.argv[1]

    session = AppleMusicSession(Session())
    if argument == "--logout":
        session.clear_credentials()
        return
    if not session.login():
        raise SystemExit("Authentication failed")

    parts = argument.split("/")
    if len(parts) < 7:
        raise SystemExit("Could not parse Apple Music URL")
    _, _, _, _, url_type, slug, am_id, *_ = parts

    # api = AppleMusicAPI(session)
    amp = AppleMusicPlayback(session)
    downloader = AppleMusicDownloader(amp)

    if url_type.startswith("album"):
        # api.get_album_info(am_id)
        print("not supported yet :)")
    elif url_type.startswith("song"):
        downloader.download_track(am_id, f"{slug}.m4a")
    else:
        print("unsupported url")


if __name__ == "__main__":
    main()
