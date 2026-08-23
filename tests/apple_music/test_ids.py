from amdl.apple_music.ids import (
    is_library_album,
    is_library_artist,
    is_library_playlist,
    is_library_track,
)


def test_is_library_album() -> None:
    assert is_library_album("l.123456") is True
    assert is_library_album("123456") is False
    assert is_library_album("i.123456") is False
    assert is_library_album("") is False


def test_is_library_track() -> None:
    assert is_library_track("i.987654") is True
    assert is_library_track("987654") is False
    assert is_library_track("l.987654") is False
    assert is_library_track("") is False


def test_is_library_artist() -> None:
    assert is_library_artist("r.123456") is True
    assert is_library_artist("123456") is False
    assert is_library_artist("i.123456") is False
    assert is_library_artist("") is False


def test_is_library_playlist() -> None:
    assert is_library_playlist("p.123456") is True
    assert is_library_playlist("123456") is False
    assert is_library_playlist("i.123456") is False
    assert is_library_playlist("") is False
