import base64
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from requests import Session

from amdl.apple_music.client import AppleMusicClient
from amdl.config import (
    APPLE_MUSIC_API,
    APPLE_MUSIC_URL,
    LICENSE_URL,
    WEB_PLAYBACK_URL,
    WIDEVINE_CERT_URL,
)
from amdl.domain import Album, Artist, PlaybackSong, Playlist, Track


class TestAppleMusicClient:
    @staticmethod
    def make_client() -> AppleMusicClient:
        auth = MagicMock()

        media_value = "media-token"
        user_value = "user-token"
        auth.credentials = MagicMock(
            media_token=media_value,
            user_token=user_value,
        )

        client = AppleMusicClient(auth)
        client.http = cast("Session", MagicMock(spec=Session))
        return client

    @staticmethod
    def test_headers() -> None:
        client = TestAppleMusicClient.make_client()

        assert client.headers() == {
            "Authorization": "Bearer media-token",
            "Music-User-Token": "user-token",
            "media-user-token": "user-token",
            "x-apple-music-user-token": "user-token",
            "Origin": APPLE_MUSIC_URL,
            "Referer": APPLE_MUSIC_URL,
        }

    @staticmethod
    def test_headers_requires_authentication() -> None:
        auth = MagicMock()
        auth.credentials = None
        client = AppleMusicClient(auth)

        with pytest.raises(
            RuntimeError,
            match="Apple Music session is not authenticated",
        ):
            client.headers()

    @staticmethod
    def test_post() -> None:
        client = TestAppleMusicClient.make_client()
        http = cast("MagicMock", client.http)

        response = MagicMock()
        response.json.return_value = {"data": []}
        http.post.return_value = response

        result = client.post(
            "https://example.com",
            {"foo": "bar"},
        )

        http.post.assert_called_once_with(
            "https://example.com",
            headers=client.headers(),
            json={"foo": "bar"},
        )
        response.raise_for_status.assert_called_once()
        response.json.assert_called_once()
        assert result == {"data": []}

    @staticmethod
    def test_get() -> None:
        client = TestAppleMusicClient.make_client()
        http = cast("MagicMock", client.http)

        response = MagicMock()
        response.json.return_value = {"data": []}
        http.get.return_value = response

        result = client.get(
            "https://example.com",
            params={"limit": 10},
        )

        http.get.assert_called_once_with(
            "https://example.com",
            headers=client.headers(),
            params={"limit": 10},
        )
        response.raise_for_status.assert_called_once()
        response.json.assert_called_once()
        assert result == {"data": []}

    @staticmethod
    def test_get_album_catalog() -> None:
        client = TestAppleMusicClient.make_client()
        album = MagicMock(spec=Album)

        with (
            patch(
                "amdl.apple_music.client.is_library_album",
                return_value=False,
            ) as is_library,
            patch(
                "amdl.apple_music.client.AppleMusicAlbumParser.parse",
                return_value=album,
            ) as parse,
            patch.object(
                client,
                "get",
                return_value={"data": []},
            ) as get,
        ):
            result = client.get_album("123")

        is_library.assert_called_once_with("123")
        get.assert_called_once_with(
            f"{APPLE_MUSIC_API}/catalog/us/albums/123",
            params=None,
        )
        parse.assert_called_once_with({"data": []})
        assert result is album

    @staticmethod
    def test_get_album_library() -> None:
        client = TestAppleMusicClient.make_client()
        album = MagicMock(spec=Album)

        with (
            patch(
                "amdl.apple_music.client.is_library_album",
                return_value=True,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicAlbumParser.parse",
                return_value=album,
            ),
            patch.object(
                client,
                "get",
                return_value={"data": []},
            ) as get,
        ):
            result = client.get_album("l.123")

        get.assert_called_once_with(
            f"{APPLE_MUSIC_API}/me/library/albums/l.123",
            params={"include": "catalog,songs"},
        )
        assert result is album

    @staticmethod
    def test_get_track_catalog() -> None:
        client = TestAppleMusicClient.make_client()
        track = MagicMock(spec=Track)

        with (
            patch(
                "amdl.apple_music.client.is_library_track",
                return_value=False,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicTrackParser.parse",
                return_value=track,
            ) as parse,
            patch.object(
                client,
                "get",
                return_value={"data": []},
            ) as get,
        ):
            result = client.get_track("123")

        get.assert_called_once_with(
            f"{APPLE_MUSIC_API}/catalog/us/songs/123",
            params={"include": "albums,catalog"},
        )
        parse.assert_called_once_with({"data": []})
        assert result is track

    @staticmethod
    def test_get_track_library() -> None:
        client = TestAppleMusicClient.make_client()
        track = MagicMock(spec=Track)

        with (
            patch(
                "amdl.apple_music.client.is_library_track",
                return_value=True,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicTrackParser.parse",
                return_value=track,
            ),
            patch.object(
                client,
                "get",
                return_value={"data": []},
            ) as get,
        ):
            result = client.get_track("l.123")

        get.assert_called_once_with(
            f"{APPLE_MUSIC_API}/me/library/songs/l.123",
            params={"include": "albums,catalog"},
        )
        assert result is track

    @staticmethod
    def test_get_artist_catalog() -> None:
        client = TestAppleMusicClient.make_client()
        artist = MagicMock(spec=Artist)

        with (
            patch(
                "amdl.apple_music.client.is_library_artist",
                return_value=False,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicArtistParser.parse",
                return_value=artist,
            ) as parse,
            patch.object(
                client,
                "get",
                return_value={"data": []},
            ) as get,
        ):
            result = client.get_artist("123")

        get.assert_called_once_with(
            f"{APPLE_MUSIC_API}/catalog/us/artists/123",
            params={
                "include": "catalog,albums",
                "include[albums]": "tracks",
            },
        )
        parse.assert_called_once_with({"data": []})
        assert result is artist

    @staticmethod
    def test_get_artist_library() -> None:
        client = TestAppleMusicClient.make_client()
        artist = MagicMock(spec=Artist)

        with (
            patch(
                "amdl.apple_music.client.is_library_artist",
                return_value=True,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicArtistParser.parse",
                return_value=artist,
            ),
            patch.object(
                client,
                "get",
                return_value={"data": []},
            ) as get,
        ):
            result = client.get_artist("l.123")

        get.assert_called_once_with(
            f"{APPLE_MUSIC_API}/me/library/artists/l.123",
            params={
                "include": "catalog,albums",
                "include[albums]": "tracks",
            },
        )
        assert result is artist

    @staticmethod
    def test_get_playlist_catalog() -> None:
        client = TestAppleMusicClient.make_client()
        playlist = MagicMock(spec=Playlist)
        playlist.tracks = []

        response = MagicMock()
        response.data = []
        response.next = None

        with (
            patch(
                "amdl.apple_music.client.is_library_playlist",
                return_value=False,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaylistParser.parse",
                return_value=playlist,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaylistTracksResponse.model_validate",
                return_value=response,
            ) as model_validate,
            patch.object(
                client,
                "get",
                side_effect=[
                    {"data": []},
                    {"data": []},
                ],
            ) as get,
        ):
            result = client.get_playlist("123")

        get.assert_any_call(
            f"{APPLE_MUSIC_API}/catalog/us/playlists/123",
        )
        get.assert_any_call(
            f"{APPLE_MUSIC_API}/catalog/us/playlists/123/tracks",
            params={
                "offset": 0,
                "limit": 100,
                "include[library-songs]": "artists,catalog",
            },
        )
        model_validate.assert_called_once_with({"data": []})
        assert result is playlist
        assert playlist.tracks == []

    @staticmethod
    def test_get_playlist_library() -> None:
        client = TestAppleMusicClient.make_client()
        playlist = MagicMock(spec=Playlist)
        playlist.tracks = []

        response = MagicMock()
        response.data = []
        response.next = None

        with (
            patch(
                "amdl.apple_music.client.is_library_playlist",
                return_value=True,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaylistParser.parse",
                return_value=playlist,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaylistTracksResponse.model_validate",
                return_value=response,
            ),
            patch.object(
                client,
                "get",
                side_effect=[
                    {"data": []},
                    {"data": []},
                ],
            ) as get,
        ):
            result = client.get_playlist("l.123")

        get.assert_any_call(
            f"{APPLE_MUSIC_API}/me/library/playlists/l.123",
        )
        get.assert_any_call(
            f"{APPLE_MUSIC_API}/me/library/playlists/l.123/tracks",
            params={
                "offset": 0,
                "limit": 100,
                "include[library-songs]": "artists,catalog",
            },
        )
        assert result is playlist

    @staticmethod
    def test_get_playlist_tracks() -> None:
        client = TestAppleMusicClient.make_client()
        playlist = MagicMock(spec=Playlist)
        playlist.tracks = []

        track = MagicMock(spec=Track)
        response = MagicMock()
        response.data = [MagicMock()]
        response.next = None

        with (
            patch(
                "amdl.apple_music.client.is_library_playlist",
                return_value=False,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaylistParser.parse",
                return_value=playlist,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaylistTracksResponse.model_validate",
                return_value=response,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicTrackParser.parse_track",
                return_value=track,
            ) as parse_track,
            patch.object(
                client,
                "get",
                side_effect=[
                    {"data": []},
                    {"data": []},
                ],
            ),
        ):
            result = client.get_playlist("123")

        parse_track.assert_called_once_with(response.data[0])
        assert result.tracks == [track]

    @staticmethod
    def test_get_playlist_paginates() -> None:
        client = TestAppleMusicClient.make_client()
        playlist = MagicMock(spec=Playlist)
        playlist.tracks = []

        first_track = MagicMock(spec=Track)
        second_track = MagicMock(spec=Track)

        first_response = MagicMock()
        first_response.data = [MagicMock()]
        first_response.next = "https://example.com/tracks?offset=100"

        second_response = MagicMock()
        second_response.data = [MagicMock()]
        second_response.next = None

        with (
            patch(
                "amdl.apple_music.client.is_library_playlist",
                return_value=False,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaylistParser.parse",
                return_value=playlist,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaylistTracksResponse.model_validate",
                side_effect=[first_response, second_response],
            ),
            patch(
                "amdl.apple_music.client.AppleMusicTrackParser.parse_track",
                side_effect=[first_track, second_track],
            ),
            patch.object(
                client,
                "get",
                side_effect=[
                    {"data": []},
                    {"data": []},
                    {"data": []},
                ],
            ) as get,
        ):
            result = client.get_playlist("123")

        assert result.tracks == [first_track, second_track]
        expected_request_count = 3
        assert get.call_count == expected_request_count

        get.assert_any_call(
            f"{APPLE_MUSIC_API}/catalog/us/playlists/123/tracks",
            params={
                "offset": 100,
                "limit": 100,
                "include[library-songs]": "artists,catalog",
            },
        )

    @staticmethod
    def test_get_service_certificate() -> None:
        client = TestAppleMusicClient.make_client()
        http = cast("MagicMock", client.http)

        response = MagicMock()
        response.content = b"certificate"
        http.get.return_value = response

        result = client.get_service_certificate()

        http.get.assert_called_once_with(WIDEVINE_CERT_URL)
        assert result == b"certificate"

    @staticmethod
    def test_get_playback_catalog() -> None:
        client = TestAppleMusicClient.make_client()
        playback = MagicMock(spec=PlaybackSong)

        with (
            patch(
                "amdl.apple_music.client.is_library_track",
                return_value=False,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaybackParser.parse",
                return_value=playback,
            ) as parse,
            patch.object(
                client,
                "post",
                return_value={"data": []},
            ) as post,
        ):
            result = client.get_playback("123")

        post.assert_called_once_with(
            WEB_PLAYBACK_URL,
            json={"salableAdamId": "123"},
        )
        parse.assert_called_once_with({"data": []})
        assert result is playback

    @staticmethod
    def test_get_playback_library() -> None:
        client = TestAppleMusicClient.make_client()
        playback = MagicMock(spec=PlaybackSong)

        with (
            patch(
                "amdl.apple_music.client.is_library_track",
                return_value=True,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicPlaybackParser.parse",
                return_value=playback,
            ),
            patch.object(
                client,
                "post",
                return_value={"data": []},
            ) as post,
        ):
            result = client.get_playback("l.123")

        post.assert_called_once_with(
            WEB_PLAYBACK_URL,
            json={"universalLibraryId": "l.123"},
        )
        assert result is playback

    @staticmethod
    def test_get_license() -> None:
        client = TestAppleMusicClient.make_client()

        challenge = "challenge"
        kid = base64.b64encode(b"kid").decode()
        license_data = base64.b64encode(b"license").decode()

        with (
            patch(
                "amdl.apple_music.client.is_library_track",
                return_value=False,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicLicenseParser.parse",
                return_value=license_data,
            ),
            patch.object(
                client,
                "post",
                return_value={"data": []},
            ) as post,
        ):
            result = client.get_license(challenge, kid, "123")

        post.assert_called_once_with(
            LICENSE_URL,
            json={
                "challenge": challenge,
                "key-system": "com.widevine.alpha",
                "adamId": "123",
                "isLibrary": False,
                "user-initiated": True,
                "uri": f"data:;base64,{kid}",
            },
        )
        assert result == b"license"

    @staticmethod
    def test_get_license_library() -> None:
        client = TestAppleMusicClient.make_client()
        kid = base64.b64encode(b"kid").decode()

        with (
            patch(
                "amdl.apple_music.client.is_library_track",
                return_value=True,
            ),
            patch(
                "amdl.apple_music.client.AppleMusicLicenseParser.parse",
                return_value=base64.b64encode(b"license").decode(),
            ),
            patch.object(
                client,
                "post",
                return_value={"data": []},
            ) as post,
        ):
            result = client.get_license("challenge", kid, "l.123")

        assert result == b"license"
        assert post.call_args.kwargs["json"]["isLibrary"] is True

    @staticmethod
    def test_fetch_content() -> None:
        client = TestAppleMusicClient.make_client()
        http = cast("MagicMock", client.http)

        response = MagicMock()
        response.content = b"content"
        http.get.return_value = response

        result = client.fetch_content("https://example.com/file")

        http.get.assert_called_once_with(
            "https://example.com/file",
            timeout=10,
        )
        response.raise_for_status.assert_called_once()
        assert result == b"content"
