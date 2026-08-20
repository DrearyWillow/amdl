import base64
from collections.abc import Mapping
from typing import cast

from requests import Session

from amdl.apple_music.auth import AppleMusicAuthenticator
from amdl.apple_music.ids import is_library_album, is_library_artist, is_library_track
from amdl.apple_music.parsers import (
    AppleMusicAlbumParser,
    AppleMusicArtistParser,
    AppleMusicLicenseParser,
    AppleMusicPlaybackParser,
    AppleMusicTrackParser,
)
from amdl.config import (
    APPLE_MUSIC_API,
    APPLE_MUSIC_URL,
    LICENSE_URL,
    WEB_PLAYBACK_URL,
    WIDEVINE_CERT_URL,
)
from amdl.domain import Album, Artist, Playback, Track
from amdl.json_type import JSON


class AppleMusicClient:
    def __init__(self, auth: AppleMusicAuthenticator) -> None:
        self.http: Session = Session()
        self.auth: AppleMusicAuthenticator = auth

    def headers(self) -> dict[str, str]:
        creds = self.auth.credentials
        if creds is None:
            raise RuntimeError("Apple Music session is not authenticated")
        return {
            "Authorization": f"Bearer {creds.media_token}",
            "Music-User-Token": creds.user_token,
            "media-user-token": creds.user_token,
            "x-apple-music-user-token": creds.user_token,
            "Origin": APPLE_MUSIC_URL,
            "Referer": APPLE_MUSIC_URL,
        }

    def post(self, url: str, json: Mapping[str, str | bool]) -> JSON:
        response = self.http.post(url, headers=self.headers(), json=json)
        response.raise_for_status()
        return cast(JSON, response.json())

    def get(self, url: str, params: Mapping[str, str | int] | None = None) -> JSON:
        response = self.http.get(url, headers=self.headers(), params=params)
        print(f"{url} (GET) -> {response.status_code}")
        response.raise_for_status()
        return cast(JSON, response.json())

    def get_album(self, album_id: str) -> Album:
        if is_library_album(album_id):
            response = self.get(
                f"{APPLE_MUSIC_API}/me/library/albums/{album_id}",
                params={
                    "include": "catalog,artists,songs",
                    "include[songs]": "artists",
                },
            )
        else:
            response = self.get(
                f"{APPLE_MUSIC_API}/catalog/us/albums/{album_id}",
                params={
                    "include": "artists",
                    "include[songs]": "artists",
                },
            )
        return AppleMusicAlbumParser.parse(response)

    def get_track(self, track_id: str) -> Track:
        path = f"me/library/songs/{track_id}" if is_library_track(track_id) else f"catalog/us/songs/{track_id}"
        response = self.get(f"{APPLE_MUSIC_API}/{path}", params={"include": "albums,catalog"})
        # TODO: add back artists (in parser too)
        # https://github.com/DrearyWillow/coda/blob/master/src/coda/core/converters.py
        return AppleMusicTrackParser.parse(response)

    def get_artist(self, artist_id: str) -> Artist:
        if is_library_artist(artist_id):
            response = self.get(
                f"{APPLE_MUSIC_API}/me/library/artists/{artist_id}",
                params={"include": "catalog,albums", "include[albums]": "tracks"},
            )
        else:
            response = self.get(
                f"{APPLE_MUSIC_API}/catalog/us/artists/{artist_id}",
                params={"include": "albums", "include[albums]": "tracks"},
            )
        return AppleMusicArtistParser.parse(response)

    # def get_pins(self) -> Pins:
    #     return self.get(
    #         f"{APPLE_MUSIC_API}/me/library/pins",
    #         params={
    #             "include[library-artists]": "catalog",
    #             "include[library-songs]": "albums",
    #             "limit": 6,
    #         },
    #     )

    # def get_playlist(self, playlist_id: str) -> Playlist:
    #     return self.get(
    #         f"{APPLE_MUSIC_API}/me/library/playlists/{playlist_id}",
    #         params={"include": "tracks", "include[library-songs]": "albums,catalog"},
    #     )

    # def get_playlist_tracks(self, playlist_id: str, offset: int = 0, limit: int = 100) -> Playlist:
    #     return self.get(
    #         f"{APPLE_MUSIC_API}/me/library/playlists/{playlist_id}/tracks",
    #         params={"offset": offset, "limit": limit, "include[library-songs]": "artists,albums,catalog"},
    #     )

    # def get_profile_me(self) -> Profile:
    #     return self.get("me/social/profile", params={"include": "social-profile"})

    # def get_profile(self, handle: str) -> Profile:
    #     return self.get("social/us/social-profiles", params={"filter[handle]": handle})

    def get_service_certificate(self) -> bytes:
        return self.http.get(WIDEVINE_CERT_URL).content

    def get_playback(self, track_id: str) -> Playback:
        body = {"universalLibraryId": track_id} if is_library_track(track_id) else {"salableAdamId": track_id}
        return AppleMusicPlaybackParser.parse(self.post(WEB_PLAYBACK_URL, json=body))

    def get_license(self, challenge: str, kid_b64: str, track_id: str) -> bytes:
        kid_bytes = base64.b64decode(kid_b64)
        kid_encoded = base64.b64encode(kid_bytes).decode()
        response = self.post(
            LICENSE_URL,
            json={
                "challenge": challenge,
                "key-system": "com.widevine.alpha",
                "adamId": track_id,
                "isLibrary": is_library_track(track_id),
                "user-initiated": True,
                "uri": f"data:;base64,{kid_encoded}",
            },
        )
        return base64.b64decode(AppleMusicLicenseParser.parse(response))

    def fetch_content(self, url: str) -> bytes:
        response = self.http.get(url, timeout=10)
        response.raise_for_status()
        return response.content
