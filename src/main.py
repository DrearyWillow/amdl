import base64
import re
import subprocess
from argparse import ArgumentParser
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self, TypeVar, cast, overload

import keyring
import m3u8
from keyring.errors import PasswordDeleteError
from mutagen.mp4 import MP4, MP4Cover
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
_T = TypeVar("_T", bound=JSON)
NO_DEFAULT = sentinel("NO_DEFAULT")


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


@dataclass
class Track:
    library_id: str = ""
    catalog_id: str = ""
    track_name: str = ""
    artist_name: str = ""
    album_name: str = ""
    artwork_url: str = ""
    release_date: str = ""
    track_number: int = 1

    @property
    def id(self) -> str:
        return self.catalog_id or self.library_id


@dataclass
class Album:
    library_id: str = ""
    album_name: str = ""
    catalog_id: str = ""
    artist_name: str = ""
    artwork_url: str = ""
    release_date: str = ""
    tracks: list[Track] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.catalog_id or self.library_id


@dataclass(frozen=True)
class Arguments:
    url: str | None
    directory: Path | None
    only_artwork: bool
    logout: bool


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

    def get_track_info(self, track_id: str) -> JSON:
        path = f"me/library/songs/{track_id}" if is_library_track(track_id) else f"catalog/us/songs/{track_id}"
        return self.get(path, params={"include": "artists,albums,catalog"})

    def get_catalog_tracks(self, track_ids: list[str]) -> JSON:
        path = "catalog/us/songs"
        params = {
            "ids": ",".join(track_ids),
            "include": "artists,albums",
            "extend": "inFavorites",
        }
        return self.get(path, params=params)


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
            error_msg = error_messages.get(status, status) if isinstance(status, int) else "Unknown"
            raise ValueError(f"License error: {error_msg}")

        license_data = data.get("license")
        if not isinstance(license_data, str) or not license_data:
            raise ValueError("No license data received from Apple")

        return base64.b64decode(license_data)


class AppleMusicDownloaderCore:
    def __init__(self, session: Session):
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
    def extract_playlist_url(playback: PlaybackData) -> str:
        quality_priorities = ("28:ctrp256", "32:ctrp64")
        for song in playback.songs:
            for target_flavor in quality_priorities:
                for asset in song.assets:
                    if asset.url and asset.flavor == target_flavor:
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
    def __init__(self, session: AppleMusicSession):
        self.amp: AppleMusicPlayback = AppleMusicPlayback(session)
        self.http: Session = session.http
        self.core: AppleMusicDownloaderCore = AppleMusicDownloaderCore(self.http)
        self.drm: WidevineDRM = WidevineDRM()
        self.drm.set_service_certificate(self.amp.get_service_certificate())

    def prepare_track(self, track_id: str) -> tuple[str, str]:
        print(f"Preparing track {track_id} for playback")
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
    def embed_track_metadata(track: Track, path: Path, artwork: bytes | None = None) -> None:
        mp4 = MP4(path)

        tags = mp4.tags
        if tags is None:
            mp4.add_tags()
            tags = mp4.tags
        assert tags is not None

        tags["\xa9nam"] = track.track_name
        tags["\xa9ART"] = track.artist_name
        tags["\xa9alb"] = track.album_name
        tags["\xa9day"] = track.release_date
        tags["trkn"] = [(track.track_number, 0)]

        if artwork:
            tags["covr"] = [MP4Cover(artwork)]

        mp4.save()  # pyright: ignore[reportUnknownMemberType]



class Converter:
    class Traverse:
        """
        Safely traverse nested dicts and lists.

        Initialize with a JSON-like object, then chain `[]` access
        to walk the structure. Call the instance to finalize and
        retrieve a value.

        Each key can be:
            - str: dict key lookup; when applied to a list, extracts
                that key from each item (fan-out)
            - int: list index

        Example:
            count: int = Traverse(obj)["data"][0]["attributes"]["trackCount"](0)

        Call parameters:
            default:
                Value returned if the path does not resolve, or if the
                resolved value's type does not match the type of default.

        Notes:
            - Missing keys or out-of-range indices are ignored.
            - Empty results (`None`, `{}`) are filtered out.
        """

        def __init__(self, obj: JSON) -> None:
            self.items: list[JSON] = [obj]

        @overload
        def __call__(self) -> JSON: ...
        @overload
        def __call__(self, default: _T) -> _T: ...
        def __call__(self, default: JSON | NO_DEFAULT = NO_DEFAULT) -> JSON:
            results: list[JSON] = [item for item in self.items if item not in (None, {})]
            return_default = default if default is not NO_DEFAULT else None
            if results and (default is NO_DEFAULT or isinstance(results[0], type(default))):
                return results[0]
            return return_default

        def __getitem__(self, key: str | int) -> Self:
            self.items = [x for item in self.items for x in self.collect(item, key)]
            return self

        def collect(self, node: JSON, key: str | int) -> list[JSON]:
            if isinstance(key, str):
                if isinstance(node, list):
                    return [x for item in node for x in self.collect(item, key)]
                if isinstance(node, dict) and key in node:
                    return [node[key]]
            elif isinstance(node, list):
                try:
                    return [node[key]]
                except IndexError:
                    pass
            return []

    # @classmethod
    # def artwork_url(cls, artwork_data: JSON) -> str:
    #     url = cls.Traverse(artwork_data)["url"]("")
    #     height = cls.Traverse(artwork_data)["height"](9999)
    #     width = cls.Traverse(artwork_data)["width"](9999)
    #     return url.replace("{w}", str(width)).replace("{h}", str(height)).replace("{c}", "bb")
    
    @classmethod
    def artwork_url(cls, url: str) -> str:
        return url.replace("{w}", "9999").replace("{h}", "9999").replace("{c}", "bb")

    @classmethod
    def track(cls, track_data: JSON, album: Album | None = None) -> Track:
        data = cls.Traverse(track_data)["data"][0](track_data)
        cat_data = cls.Traverse(data)["relationships"]["catalog"]["data"][0](cast(dict[str, JSON], {}))
        cat_track = cls.track(cat_data) if cat_data else Track()
        attrs = cls.Traverse(data)["attributes"](cast(dict[str, JSON], {}))
        play_params = cls.Traverse(attrs)["playParams"](cast(dict[str, JSON], {}))
        track_id = cls.Traverse(data)["id"]("") or cls.Traverse(play_params)["id"]("")
        return Track(
            library_id=track_id if is_library_track(track_id) else "",
            catalog_id=(cat_track.catalog_id or cls.Traverse(play_params)["catalogId"](""))
            if is_library_track(track_id)
            else track_id,
            track_name=cast(str, attrs.get("name") or cat_track.track_name or "Unknown Track"),
            artist_name=cat_track.artist_name
            or cls.Traverse(attrs)["artistName"]("")
            or (album.artist_name if album else "Unknown Artist"),
            album_name=cat_track.album_name
            or cls.Traverse(attrs)["albumName"]("")
            or (album.album_name if album else "Unknown Album"),
            artwork_url=cat_track.artwork_url
            or cls.artwork_url(cls.Traverse(attrs)["artwork"]["url"](""))
            or (album.artwork_url if album else ""),
            release_date=cat_track.release_date
            or cls.Traverse(attrs)["releaseDate"]("")
            or (album.release_date if album else ""),
            track_number=cls.Traverse(attrs)["trackNumber"](1),
        )

    @classmethod
    def album(cls, album_data: JSON) -> Album:
        data = cls.Traverse(album_data)["data"][0](album_data)
        attrs = cls.Traverse(data)["attributes"](cast(dict[str, JSON], {}))
        album_id = cls.Traverse(data)["id"]("")

        album = Album(
            library_id=album_id if is_library_album(album_id) else "",
            album_name=cls.Traverse(attrs)["name"]("").removesuffix(" - Single").removesuffix(" - EP"),
            catalog_id=cls.Traverse(data)["relationships"]["catalog"]["data"][0]["id"]("")
            if is_library_album(album_id)
            else album_id,
            artist_name=cls.Traverse(attrs)["artistName"](""),
            artwork_url=cls.artwork_url(cls.Traverse(attrs)["artwork"]["url"]("")),
            release_date=cls.Traverse(attrs)["releaseDate"]("0000-00-00"),
        )
        tracks_data = cast(list[dict[str, JSON]], cls.Traverse(data)["relationships"]["tracks"]["data"]([]))
        album.tracks = [cls.track(t, album) for t in tracks_data]
        # album.artwork_url = album.artwork_url or next(t.artwork_url for t in album.tracks)

        return album


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
        song = cls.sanitize_filename_component(track.track_name)
        return output_dir / artist / f"{song}.m4a"

    @classmethod
    def track_artwork(cls, output_dir: Path, track: Track) -> Path:
        artist = cls.sanitize_filename_component(track.artist_name)
        song = cls.sanitize_filename_component(track.track_name)
        return output_dir / f"{artist} - {song}.jpg"

    @classmethod
    def album_track(cls, output_dir: Path, album: Album, track: Track) -> Path:
        artist = cls.sanitize_filename_component(album.artist_name)
        album_name = cls.sanitize_filename_component(album.album_name)
        song = cls.sanitize_filename_component(track.track_name)
        return output_dir / artist / album_name / f"{track.track_number:02d} - {song}.m4a"

    @classmethod
    def album_artwork(cls, output_dir: Path, album: Album) -> Path:
        artist = cls.sanitize_filename_component(album.artist_name)
        album_name = cls.sanitize_filename_component(album.album_name)
        return output_dir / f"{artist} - {album_name}.jpg"


class ArgParser:
    @staticmethod
    def create_parser() -> ArgumentParser:
        parser = ArgumentParser(description="Download tracks from Apple Music.")

        _ = parser.add_argument(
            "url",
            nargs="?",
            help="Apple Music URL to download",
        )
        _ = parser.add_argument(
            "-d",
            "--directory",
            type=Path,
            help="Directory to download to",
        )
        _ = parser.add_argument(
            "--logout",
            action="store_true",
            help="Clear stored Apple Music credentials",
        )
        _ = parser.add_argument(
            "--art",
            "--artwork",
            "--cover",
            dest="only_artwork",
            action="store_true",
            help="Only download the provided URL's artwork",
        )

        return parser

    @staticmethod
    def validate(arguments: Arguments, parser: ArgumentParser) -> None:
        if arguments.logout and arguments.url is not None:
            parser.error("--logout cannot be used with a URL")
        if arguments.logout and arguments.directory is not None:
            parser.error("--logout cannot be used with --directory")
        if arguments.logout and arguments.only_artwork:
            parser.error("--logout cannot be used with --artwork")
        if not arguments.logout and arguments.url is None:
            parser.error("a URL is required unless --logout is specified")
        if arguments.directory is not None and arguments.url is None:
            parser.error("--directory requires a URL")
        if arguments.only_artwork and arguments.url is None:
            parser.error("--artwork requires a URL")

    @classmethod
    def parse(cls) -> Arguments:
        parser = cls.create_parser()
        args = parser.parse_args()

        url = cast(str | None, args.url)
        directory = cast(Path | None, args.directory)
        only_artwork = cast(bool, args.only_artwork)
        logout = cast(bool, args.logout)

        arguments = Arguments(url, directory, only_artwork, logout)
        cls.validate(arguments, parser)
        return arguments

    @staticmethod
    def apple_music_url(url: str) -> tuple[str, str]:
        prefix = f"{APPLE_MUSIC_URL}/"

        if not url.startswith(prefix):
            raise ValueError("URL is not Apple Music")

        parts = url.removeprefix(prefix).split("/")

        if len(parts) < 4:
            raise ValueError("Could not parse Apple Music URL")

        _, url_type, slug, am_id, *_ = parts
        if url_type == "library":
            url_type = slug

        return url_type, am_id


class DownloadManager:
    def __init__(self, session: AppleMusicSession) -> None:
        self.api: AppleMusicAPI = AppleMusicAPI(session)
        self.downloader: AppleMusicDownloader = AppleMusicDownloader(session)

    def track(self, track_id: str, output_dir: Path, only_artwork: bool) -> None:
        track_data = self.api.get_track_info(track_id)
        track = Converter.track(track_data)
        output_path = PathConstructor.track(output_dir, track)

        artwork = self.downloader.fetch_artwork(track.artwork_url)
        if only_artwork:
            output_path = PathConstructor.track_artwork(output_dir, track)
            self.downloader.save_artwork(artwork, output_path)
            return

        self.downloader.download_track(track, output_path)
        self.downloader.embed_track_metadata(track, output_path, artwork)



def main():
    args = ArgParser.parse()
    session = AppleMusicSession(Session())

    if args.logout:
        session.clear_credentials()
        return

    assert args.url is not None
    url_type, am_id = ArgParser.apple_music_url(args.url)

    if not session.login():
        raise SystemExit("Authentication failed")

    api = AppleMusicAPI(session)
    downloader = AppleMusicDownloader(session)

    output_dir = args.directory if args.directory else Path.cwd()

    if url_type.startswith("album"):
        album_data = api.get_album_info(am_id)
        album = Converter.album(album_data)

        artwork = downloader.fetch_artwork(album.artwork_url)
        if args.only_artwork:
            output_path = PathConstructor.album_artwork(output_dir, album)
            downloader.save_artwork(artwork, output_path)
            return

        for track in album.tracks:
            output_path = PathConstructor.album_track(output_dir, album, track)
            downloader.download_track(track, output_path)
            downloader.embed_track_metadata(track, output_path)

    elif url_type.startswith("song"):
        track_data = api.get_track_info(am_id)
        track = Converter.track(track_data)
        output_path = PathConstructor.track(output_dir, track)

        artwork = downloader.fetch_artwork(track.artwork_url)
        if args.only_artwork:
            output_path = PathConstructor.track_artwork(output_dir, track)
            downloader.save_artwork(artwork, output_path)
            return

        downloader.download_track(track, output_path)
        downloader.embed_track_metadata(track, output_path, artwork)

    else:
        raise SystemExit(f"Unsupported Apple Music URL type: {url_type}")


if __name__ == "__main__":
    main()
