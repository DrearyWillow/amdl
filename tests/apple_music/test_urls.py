import pytest

from amdl.apple_music.urls import AppleMusicUrlType, parse_apple_music_url


class TestAppleMusicUrlType:
    @pytest.mark.parametrize(
        "input_str, expected",
        [
            ("album", AppleMusicUrlType.ALBUM),
            ("albums", AppleMusicUrlType.ALBUM),
            ("album-something", AppleMusicUrlType.ALBUM),
            ("song", AppleMusicUrlType.SONG),
            ("songs", AppleMusicUrlType.SONG),
            ("song-something", AppleMusicUrlType.SONG),
        ],
    )
    def test_from_str_valid(self, input_str: str, expected: AppleMusicUrlType) -> None:
        assert AppleMusicUrlType.from_str(input_str) == expected

    @pytest.mark.parametrize("input_str", ["playlist", "artist", "12345", ""])
    def test_from_str_invalid_raises(self, input_str: str) -> None:
        with pytest.raises(ValueError, match="Unsupported Apple Music URL type"):
            _ = AppleMusicUrlType.from_str(input_str)


class TestParseAppleMusicUrl:
    @pytest.mark.parametrize(
        "url, expected_type, expected_id",
        [
            (
                "https://music.apple.com/us/album/album-title/123456789",
                AppleMusicUrlType.ALBUM,
                "123456789",
            ),
            (
                "https://music.apple.com/us/album/123456789",
                AppleMusicUrlType.ALBUM,
                "123456789",
            ),
            (
                "https://music.apple.com/gb/song/song-title/987654321",
                AppleMusicUrlType.SONG,
                "987654321",
            ),
        ],
    )
    def test_parse_catalog_urls(self, url: str, expected_type: AppleMusicUrlType, expected_id: str) -> None:
        url_type, am_id = parse_apple_music_url(url)
        assert url_type == expected_type
        assert am_id == expected_id

    @pytest.mark.parametrize(
        "url, expected_type, expected_id",
        [
            (
                "https://music.apple.com/us/library/album/l.abc1234",
                AppleMusicUrlType.ALBUM,
                "l.abc1234",
            ),
            (
                "https://music.apple.com/us/library/song/i.xyz9876",
                AppleMusicUrlType.SONG,
                "i.xyz9876",
            ),
        ],
    )
    def test_parse_library_urls(self, url: str, expected_type: AppleMusicUrlType, expected_id: str) -> None:
        url_type, am_id = parse_apple_music_url(url)
        assert url_type == expected_type
        assert am_id == expected_id

    def test_parse_invalid_netloc_raises(self) -> None:
        url = "https://spotify.com/us/album/album-title/123456789"
        with pytest.raises(ValueError, match="URL is not an Apple Music URL"):
            _ = parse_apple_music_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://music.apple.com",
            "https://music.apple.com/us",
            "https://music.apple.com/us/album",
        ],
    )
    def test_parse_path_too_short_raises(self, url: str) -> None:
        with pytest.raises(ValueError, match="path too short"):
            _ = parse_apple_music_url(url)

    def test_parse_library_path_too_short_raises(self) -> None:
        url = "https://music.apple.com/us/library/album"
        with pytest.raises(ValueError, match="Invalid Apple Music library URL"):
            _ = parse_apple_music_url(url)
