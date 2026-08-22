from enum import Enum, auto
from urllib.parse import parse_qs, urlparse

from amdl.config import APPLE_MUSIC_HOSTS


class AppleMusicUrlType(Enum):
    ALBUM = auto()
    SONG = auto()
    ARTIST = auto()
    PLAYLIST = auto()
    MUSIC_VIDEO = auto()
    STATION = auto()

    LIBRARY_ALBUM = auto()
    LIBRARY_SONG = auto()
    LIBRARY_ARTIST = auto()
    LIBRARY_PLAYLIST = auto()

    PROFILE = auto()
    CURATOR = auto()
    APPLE_CURATOR = auto()
    RECORD_LABEL = auto()


def parse_apple_music_url(url: str) -> tuple[AppleMusicUrlType, str]:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL must use HTTP or HTTPS")

    if parsed.hostname not in APPLE_MUSIC_HOSTS:
        raise ValueError("URL is not an Apple Music URL")

    parts = tuple(part for part in parsed.path.split("/") if part)

    if not parts:
        raise ValueError("Could not parse Apple Music URL: empty path")

    # /profile/{name}
    if parts[0] == "profile":
        if len(parts) != 2:
            raise ValueError("Invalid Apple Music profile URL")
        return AppleMusicUrlType.PROFILE, parts[1]

    if len(parts) < 2:
        raise ValueError("Could not parse Apple Music URL: missing resource type")

    storefront, resource = parts[0], parts[1]

    if len(storefront) != 2:
        raise ValueError(f"Invalid Apple Music storefront: {storefront}")

    # /{storefront}/library/{resource}/{id}
    if resource == "library":
        return _parse_library_url(parts)

    # /{storefront}/{resource}/...
    return _parse_catalog_url(resource, parts, parsed.query)


def _parse_library_url(parts: tuple[str, ...]) -> tuple[AppleMusicUrlType, str]:
    if len(parts) != 4:
        raise ValueError("Invalid Apple Music library URL")

    _, _, resource, resource_id = parts

    match resource:
        case "albums":
            return AppleMusicUrlType.LIBRARY_ALBUM, resource_id
        case "songs":
            return AppleMusicUrlType.LIBRARY_SONG, resource_id
        case "artists":
            return AppleMusicUrlType.LIBRARY_ARTIST, resource_id
        case "playlist" | "playlists":
            return AppleMusicUrlType.LIBRARY_PLAYLIST, resource_id
        case _:
            raise ValueError(f"Unsupported Apple Music library URL type: {resource}")


def _parse_catalog_url(resource: str, parts: tuple[str, ...], query: str) -> tuple[AppleMusicUrlType, str]:
    if len(parts) < 3:
        raise ValueError("Could not parse Apple Music URL: path too short")

    resource_id = parts[-1]

    # /us/album/album-name/123456789?i=987654321
    if resource == "album":
        song_ids = parse_qs(query).get("i")

        if song_ids:
            if len(song_ids) != 1 or not song_ids[0]:
                raise ValueError("Invalid Apple Music song ID in 'i' parameter")
            return AppleMusicUrlType.SONG, song_ids[0]

        return AppleMusicUrlType.ALBUM, resource_id

    match resource:
        case "song":
            return AppleMusicUrlType.SONG, resource_id
        case "artist":
            return AppleMusicUrlType.ARTIST, resource_id
        case "playlist":
            return AppleMusicUrlType.PLAYLIST, resource_id
        case "music-video":
            return AppleMusicUrlType.MUSIC_VIDEO, resource_id
        case "station":
            return AppleMusicUrlType.STATION, resource_id
        case "curator":
            return AppleMusicUrlType.CURATOR, resource_id
        case "apple-curator":
            return AppleMusicUrlType.APPLE_CURATOR, resource_id
        case "record-label":
            return AppleMusicUrlType.RECORD_LABEL, resource_id
        case _:
            raise ValueError(f"Unsupported Apple Music URL type: {resource}")
