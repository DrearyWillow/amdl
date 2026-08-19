import re
from pathlib import Path

from amdl.domain import Album, Track


def sanitize_filename_component(value: str) -> str:
    value = value.strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = value.rstrip(". ")
    return value or "Unknown"


def track_path(output_dir: Path, track: Track) -> Path:
    artist = sanitize_filename_component(track.artist_name)
    song = sanitize_filename_component(track.name)
    return output_dir / artist / f"{song}.m4a"


def track_artwork_path(output_dir: Path, track: Track) -> Path:
    artist = sanitize_filename_component(track.artist_name)
    song = sanitize_filename_component(track.name)
    return output_dir / f"{artist} - {song}.jpg"


def album_track_path(output_dir: Path, album: Album, track: Track) -> Path:
    artist = sanitize_filename_component(album.artist_name)
    album_name = sanitize_filename_component(album.name)
    song = sanitize_filename_component(track.name)
    return output_dir / artist / album_name / f"{track.track_number:02d} - {song}.m4a"


def album_artwork_path(output_dir: Path, album: Album) -> Path:
    artist = sanitize_filename_component(album.artist_name)
    album_name = sanitize_filename_component(album.name)
    return output_dir / f"{artist} - {album_name}.jpg"
