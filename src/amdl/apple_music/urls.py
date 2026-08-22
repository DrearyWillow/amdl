from enum import Enum, auto
from urllib.parse import parse_qs, urlparse

from amdl.config import APPLE_MUSIC_HOSTS


class AppleMusicType(Enum):
    ALBUM = auto()
    SONG = auto()
    ARTIST = auto()
    PLAYLIST = auto()


def parse_apple_music_url(url: str) -> tuple[AppleMusicType, str]:
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
        raise ValueError(f"Unsupported Apple Music URL type: {parts[0]}")

    # /library/{resource}/{id}
    if parts[0] == "library":
        return _parse_library_url(parts)

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


def _parse_library_url(parts: tuple[str, ...]) -> tuple[AppleMusicType, str]:
    if parts[0] == "library":
        if len(parts) != 3:
            raise ValueError("Invalid Apple Music library URL")
        _, resource, resource_id = parts
    else:
        if len(parts) != 4:
            raise ValueError("Invalid Apple Music library URL")
        _, _, resource, resource_id = parts

    match resource:
        case "album" | "albums":
            return AppleMusicType.ALBUM, resource_id
        case "song" | "songs":
            return AppleMusicType.SONG, resource_id
        case "artist" | "artists":
            return AppleMusicType.ARTIST, resource_id
        case "playlist" | "playlists":
            return AppleMusicType.PLAYLIST, resource_id
        case _:
            raise ValueError(f"Unsupported Apple Music library URL type: {resource}")


def _parse_catalog_url(resource: str, parts: tuple[str, ...], query: str) -> tuple[AppleMusicType, str]:
    if len(parts) < 4:
        raise ValueError("Could not parse Apple Music URL: path too short")

    resource_id = parts[-1]

    # /us/album/album-name/123456789?i=987654321
    if resource == "album":
        if song_ids := parse_qs(query, keep_blank_values=True).get("i"):
            if len(song_ids) != 1 or not song_ids[0]:
                raise ValueError("Invalid Apple Music song ID in 'i' parameter")
            return AppleMusicType.SONG, song_ids[0]
        return AppleMusicType.ALBUM, resource_id

    match resource:
        case "song":
            return AppleMusicType.SONG, resource_id
        case "artist":
            return AppleMusicType.ARTIST, resource_id
        case "playlist":
            return AppleMusicType.PLAYLIST, resource_id
        case _:
            raise ValueError(f"Unsupported Apple Music URL type: {resource}")
