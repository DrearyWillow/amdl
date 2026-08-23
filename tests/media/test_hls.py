import m3u8
import pytest

from amdl.domain import PlaybackSong
from amdl.media.hls import extract_kid, extract_media_url, parse_hls_playlist


def playlist_with_key() -> m3u8.M3U8:
    playlist = m3u8.M3U8()
    playlist.keys = [
        m3u8.Key(
            method="AES-128",
            base_uri="https://example.com/",
            uri="data:;base64,a2V5"
        )
    ]
    return playlist


def playlist_without_key() -> m3u8.M3U8:
    playlist = m3u8.M3U8()
    playlist.keys = []
    return playlist


def playlist_with_multiple_files() -> m3u8.M3U8:
    playlist = m3u8.M3U8()
    playlist.files = ["first.m4a", "second.m4a"]
    return playlist


def playlist_with_one_file() -> m3u8.M3U8:
    playlist = m3u8.M3U8()
    playlist.files = ["only.m4a"]
    return playlist


def load_playlist_with_key(_: str) -> m3u8.M3U8:
    return playlist_with_key()


def load_playlist_without_key(_: str) -> m3u8.M3U8:
    return playlist_without_key()


def load_playlist_with_multiple_files(_: str) -> m3u8.M3U8:
    return playlist_with_multiple_files()


def load_playlist_with_one_file(_: str) -> m3u8.M3U8:
    return playlist_with_one_file()


def mock_extract_media_url(_: str) -> str:
    return "https://example.com/audio.m4a"


def mock_extract_kid(_: str) -> str:
    return "test-kid"


def test_extract_kid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "amdl.media.hls.m3u8.load",
        load_playlist_with_key,
    )

    assert extract_kid("https://example.com/playlist.m3u8") == "a2V5"


def test_extract_kid_missing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "amdl.media.hls.m3u8.load",
        load_playlist_without_key,
    )

    with pytest.raises(ValueError, match="No encryption key found in playlist"):
        _ = extract_kid("https://example.com/playlist.m3u8")


def test_extract_media_url_non_aac_playlist() -> None:
    url = "https://example.com/playlist.m3u8"

    assert extract_media_url(url) == url


def test_extract_media_url_multiple_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "amdl.media.hls.m3u8.load",
        load_playlist_with_multiple_files,
    )

    url = "https://example.com/path/playlist.aac.wa.m3u8"

    assert extract_media_url(url) == "https://example.com/path/second.m4a"


def test_extract_media_url_single_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "amdl.media.hls.m3u8.load",
        load_playlist_with_one_file,
    )

    url = "https://example.com/path/playlist.aac.wa.m3u8"

    assert extract_media_url(url) == "https://example.com/path/only.m4a"


def test_parse_hls_playlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "amdl.media.hls.extract_media_url",
        mock_extract_media_url,
    )
    monkeypatch.setattr(
        "amdl.media.hls.extract_kid",
        mock_extract_kid,
    )

    assert parse_hls_playlist("https://example.com/playlist.m3u8") == PlaybackSong(
        url="https://example.com/audio.m4a",
        kid="test-kid",
    )
