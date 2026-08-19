from enum import Enum, auto
from urllib.parse import parse_qs, urlparse

from amdl.config import APPLE_MUSIC_URL


class AppleMusicUrlType(Enum):
    ALBUM = auto()
    SONG = auto()

    @classmethod
    def from_str(cls, url_type: str) -> AppleMusicUrlType:
        if url_type.startswith("album"):
            return cls.ALBUM
        if url_type.startswith("song"):
            return cls.SONG
        raise ValueError(f"Unsupported Apple Music URL type: {url_type}")


def parse_apple_music_url(url: str) -> tuple[AppleMusicUrlType, str]:
    parsed = urlparse(url)

    if parsed.netloc != urlparse(APPLE_MUSIC_URL).netloc:
        raise ValueError("URL is not an Apple Music URL")

    parts = [p for p in parsed.path.strip("/").split("/") if p]

    if len(parts) < 3:
        raise ValueError("Could not parse Apple Music URL: path too short")

    if parts[1] == "library":
        if len(parts) < 4:
            raise ValueError("Invalid Apple Music library URL")
        url_type = parts[2]
        am_id = parts[3]
        return AppleMusicUrlType.from_str(url_type), am_id

    url_type = parts[1]
    am_id = parts[-1]

    if url_type == "library" and parsed.query:
        for field, values in parse_qs(parsed.query).items():
            if field == "i":
                url_type = "song"
                am_id = values[0]
                break

    return AppleMusicUrlType.from_str(url_type), am_id
