from dataclasses import dataclass

lazy import m3u8

from amdl.domain import Playback


@dataclass
class HLSPlaylist:
    media_url: str
    kid: str


def extract_playlist_url(playback: Playback) -> str:
    quality_priorities = ("28:ctrp256", "32:ctrp64")
    for song in playback.songs:
        for target_flavor in quality_priorities:
            for asset in song.assets:
                if asset.url and asset.flavor == target_flavor:
                    return str(asset.url)
    raise ValueError("No suitable playback URL found")


def extract_kid(playlist_url: str) -> str:
    playlist = m3u8.load(str(playlist_url))
    if not playlist.keys or not playlist.keys[0] or not isinstance(playlist.keys[0].uri, str):
        raise ValueError("No encryption key found in playlist")
    return playlist.keys[0].uri.replace("data:;base64,", "")


def extract_media_url(playlist_url: str) -> str:
    if not playlist_url.endswith(".aac.wa.m3u8"):
        return playlist_url
    playlist = m3u8.load(playlist_url)
    filename = playlist.files[1] if len(playlist.files) > 1 else playlist.files[0]
    parts = playlist_url.split("/")
    base_url = "/".join(parts[:-1])
    return f"{base_url}/{filename}"


def get_hls_playlist(playback: Playback) -> HLSPlaylist:
    playlist_url = extract_playlist_url(playback)
    media_url = extract_media_url(playlist_url)
    kid = extract_kid(playlist_url)
    return HLSPlaylist(media_url, kid)
