import re
from pathlib import Path

from amdl.domain import Album, Artist, Pin, Playlist, Profile, Track

AUDIO = "m4a"
IMAGE = "jpg"


def sanitize_filename_component(value: str) -> str:
    value = value.strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = value.rstrip(". ")
    return value or "Unknown"


def track_path(output_dir: Path, track: Track) -> Path:
    artist = sanitize_filename_component(track.artist_name)
    song = sanitize_filename_component(track.name)
    return output_dir / artist / f"{song}.{AUDIO}"


def track_artwork_path(output_dir: Path, track: Track) -> Path:
    artist = sanitize_filename_component(track.artist_name)
    song = sanitize_filename_component(track.name)
    return output_dir / f"{artist} - {song}.{IMAGE}"


def album_track_path(output_dir: Path, album: Album, track: Track) -> Path:
    artist = sanitize_filename_component(album.artist_name)
    album_name = sanitize_filename_component(album.name)
    song = sanitize_filename_component(track.name)
    return output_dir / artist / album_name / f"{track.track_number:02d} - {song}.{AUDIO}"


def album_artwork_path(output_dir: Path, album: Album) -> Path:
    artist = sanitize_filename_component(album.artist_name)
    album_name = sanitize_filename_component(album.name)
    return output_dir / f"{artist} - {album_name}.{IMAGE}"


def artist_artwork_path(output_dir: Path, artist: Artist) -> Path:
    name = sanitize_filename_component(artist.name)
    return output_dir / f"{name}.{IMAGE}"


def playlist_track_path(output_dir: Path, playlist: Playlist, track: Track, track_number: int) -> Path:
    playlist_name = sanitize_filename_component(playlist.name)
    artist = sanitize_filename_component(track.artist_name)
    song = sanitize_filename_component(track.name)
    width = max(2, len(str(len(playlist.tracks))))
    return output_dir / playlist_name / f"{track_number:0{width}d} - {artist} - {song}.{AUDIO}"


def playlist_artwork_path(output_dir: Path, playlist: Playlist) -> Path:
    playlist_name = sanitize_filename_component(playlist.name)
    return output_dir / playlist_name / f"cover.{IMAGE}"


def profile_artwork_path(output_dir: Path, profile: Profile) -> Path:
    handle = sanitize_filename_component(profile.handle)
    username = sanitize_filename_component(profile.username)
    return output_dir / handle / f"{username}.{IMAGE}"

def pin_artwork_path(output_dir: Path, pin: Pin):
    name = sanitize_filename_component(pin.name)
    if pin.artist_name:
        artist_name = sanitize_filename_component(pin.artist_name)
        return output_dir / "Apple Music Pins" / f"{artist_name} - {name}.{IMAGE}"
    return output_dir / "Apple Music Pins" / f"{name}.{IMAGE}"
