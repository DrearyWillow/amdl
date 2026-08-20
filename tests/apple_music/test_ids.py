from amdl.apple_music.ids import is_library_album, is_library_track


def test_is_library_album() -> None:
    assert is_library_album("l.123456") is True
    assert is_library_album("123456") is False
    assert is_library_album("") is False


def test_is_library_track() -> None:
    assert is_library_track("i.987654") is True
    assert is_library_track("987654") is False
    assert is_library_track("") is False
