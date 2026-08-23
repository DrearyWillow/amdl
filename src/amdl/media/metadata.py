import logging
from pathlib import Path

from mutagen.mp4 import MP4, MP4Cover

from amdl.domain import Track

logger = logging.getLogger(__name__)


def embed_track_metadata(track: Track, path: Path, url: str | None = None, artwork: bytes | None = None) -> None:
    logger.debug(
        f"Embedding metadata: {track.name=}, {track.track_number=}, {track.artist_name=}, {track.album_name=}, {track.release_date=}"
    )

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


def save_artwork(image_bytes: bytes, output_path: Path) -> None:
    if output_path.exists():
        logger.info(f"Skipping artwork: {output_path} already exists")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("wb") as file:
        _ = file.write(image_bytes)

    logger.info(f"Downloaded artwork to {output_path}")
