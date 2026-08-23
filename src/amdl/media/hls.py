lazy import m3u8

from amdl.domain import PlaybackSong


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


def parse_hls_playlist(playlist_url: str) -> PlaybackSong:
    media_url = extract_media_url(playlist_url)
    kid = extract_kid(playlist_url)
    return PlaybackSong(url=media_url, kid=kid)
