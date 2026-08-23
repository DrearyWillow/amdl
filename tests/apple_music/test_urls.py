import pytest

from amdl.apple_music.urls import AppleMusicType, parse_apple_music_url


class TestParseAppleMusicUrl:
    @pytest.mark.parametrize(
        "url, expected_type, expected_id",
        [
            # Albums
            ("https://music.apple.com/us/album/album-title/123456789", AppleMusicType.ALBUM, "123456789"),
            ("https://music.apple.com/gb/album/album-title/123456789", AppleMusicType.ALBUM, "123456789"),
            # Songs
            ("https://music.apple.com/us/song/song-title/987654321", AppleMusicType.SONG, "987654321"),
            # Artists
            ("https://music.apple.com/us/artist/artist-name/123456789", AppleMusicType.ARTIST, "123456789"),
            # Playlists
            ("https://music.apple.com/us/playlist/playlist-name/pl.abc123", AppleMusicType.PLAYLIST, "pl.abc123"),
        ],
    )
    def test_parse_catalog_urls(self, url: str, expected_type: AppleMusicType, expected_id: str) -> None:
        url_type, am_id = parse_apple_music_url(url)
        assert url_type == expected_type
        assert am_id == expected_id

    @pytest.mark.parametrize(
        "url, expected_id",
        [
            ("https://music.apple.com/us/album/album-title/123456789?i=987654321", "987654321"),
            ("https://music.apple.com/us/album/album-title/123456789?i=987654321&ls=1", "987654321"),
        ],
    )
    def test_parse_album_song_urls(self, url: str, expected_id: str) -> None:
        url_type, am_id = parse_apple_music_url(url)

        assert url_type == AppleMusicType.SONG
        assert am_id == expected_id

    @pytest.mark.parametrize(
        "url, expected_type, expected_id",
        [
            (
                "https://music.apple.com/library/playlist/p.zp6KmqEimaVK87K",
                AppleMusicType.PLAYLIST,
                "p.zp6KmqEimaVK87K",
            ),
            ("https://music.apple.com/library/artists/r.abc123", AppleMusicType.ARTIST, "r.abc123"),
            ("https://music.apple.com/library/albums/l.abc123", AppleMusicType.ALBUM, "l.abc123"),
            ("https://music.apple.com/library/songs/i.abc123", AppleMusicType.SONG, "i.abc123"),
            ("https://music.apple.com/us/library/playlist/p.abc123", AppleMusicType.PLAYLIST, "p.abc123"),
        ],
    )
    def test_parse_library_urls(self, url: str, expected_type: AppleMusicType, expected_id: str) -> None:
        url_type, am_id = parse_apple_music_url(url)
        assert url_type == expected_type
        assert am_id == expected_id

    @pytest.mark.parametrize(
        "url",
        [
            "https://spotify.com/us/album/album-title/123456789",
            "https://example.com/us/song/song-title/123456789",
        ],
    )
    def test_parse_invalid_host_raises(self, url: str) -> None:
        with pytest.raises(ValueError, match="URL is not an Apple Music URL"):
            _ = parse_apple_music_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://music.apple.com/us/album/album-title/123456789",
            "music.apple.com/us/album/album-title/123456789",
        ],
    )
    def test_parse_invalid_scheme_raises(self, url: str) -> None:
        with pytest.raises(ValueError, match="URL must use HTTP or HTTPS"):
            _ = parse_apple_music_url(url)

    @pytest.mark.parametrize(
        "url, message",
        [
            ("https://music.apple.com", "empty path"),
            ("https://music.apple.com/", "empty path"),
            ("https://music.apple.com/us", "missing resource type"),
        ],
    )
    def test_parse_short_path_raises(self, url: str, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            _ = parse_apple_music_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://music.apple.com/usa/album/album-title/123456789",
            "https://music.apple.com/u/album/album-title/123456789",
            "https://music.apple.com/123/album/album-title/123456789",
        ],
    )
    def test_parse_invalid_storefront_raises(self, url: str) -> None:
        with pytest.raises(ValueError, match="Invalid Apple Music storefront"):
            _ = parse_apple_music_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://music.apple.com/us/library",
            "https://music.apple.com/us/library/album",
            "https://music.apple.com/us/library/albums",
            "https://music.apple.com/us/library/albums/l.abc/extra",
        ],
    )
    def test_parse_invalid_library_url_raises(self, url: str) -> None:
        with pytest.raises(ValueError, match="Invalid Apple Music library URL"):
            _ = parse_apple_music_url(url)

    def test_parse_unsupported_library_type_raises(self) -> None:
        url = "https://music.apple.com/us/library/videos/v.abc123"
        with pytest.raises(ValueError, match="Unsupported Apple Music library URL type: videos"):
            _ = parse_apple_music_url(url)

    @pytest.mark.parametrize(
        "url, expected",
        [
            ("https://music.apple.com/us/album", "path too short"),
            ("https://music.apple.com/us/song", "path too short"),
        ],
    )
    def test_parse_catalog_path_too_short_raises(self, url: str, expected: str) -> None:
        with pytest.raises(ValueError, match=expected):
            _ = parse_apple_music_url(url)

    @pytest.mark.parametrize("resource", ["unknown", "video", "track", "albums", "songs"])
    def test_parse_unsupported_catalog_type_raises(self, resource: str) -> None:
        url = f"https://music.apple.com/us/{resource}/name/123456789"

        with pytest.raises(ValueError, match=f"Unsupported Apple Music URL type: {resource}"):
            _ = parse_apple_music_url(url)

    @pytest.mark.parametrize("query", ["?i=", "?i=123&i=456"])
    def test_parse_invalid_album_song_parameter_raises(self, query: str) -> None:
        url = f"https://music.apple.com/us/album/album-title/123456789{query}"
        with pytest.raises(ValueError, match="Invalid Apple Music song ID in 'i' parameter"):
            _ = parse_apple_music_url(url)
