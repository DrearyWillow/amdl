import base64
import logging
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlparse

from requests import Session

from amdl.apple_music.ids import is_library_album, is_library_artist, is_library_playlist, is_library_track
from amdl.apple_music.schemas import AppleMusicPlaylistTracksResponse
from amdl.config import (
    APPLE_MUSIC_API,
    APPLE_MUSIC_URL,
    LICENSE_URL,
    WEB_PLAYBACK_URL,
    WIDEVINE_CERT_URL,
)
lazy from amdl.apple_music.parsers import (
    AppleMusicAlbumParser,
    AppleMusicArtistParser,
    AppleMusicLicenseParser,
    AppleMusicPlaybackParser,
    AppleMusicPlaylistParser,
    AppleMusicTrackParser,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from amdl.apple_music.auth import AppleMusicAuthenticator
    from amdl.domain import Album, Artist, PlaybackSong, Playlist, Track
    from amdl.json_type import JSON

logger = logging.getLogger(__name__)


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
        return cast("JSON", response.json())

    def get(self, url: str, params: Mapping[str, str | int] | None = None) -> JSON:
        response = self.http.get(url, headers=self.headers(), params=params)
        response.raise_for_status()
        return cast("JSON", response.json())

    def get_album(self, album_id: str) -> Album:
        library = is_library_album(album_id)
        route = "me/library/albums" if library else "catalog/us/albums"
        params = {"include": "catalog,songs"} if library else None
        response = self.get(f"{APPLE_MUSIC_API}/{route}/{album_id}", params=params)
        return AppleMusicAlbumParser.parse(response)

    def get_track(self, track_id: str) -> Track:
        route = "me/library/songs" if is_library_track(track_id) else "catalog/us/songs"
        response = self.get(f"{APPLE_MUSIC_API}/{route}/{track_id}", params={"include": "albums,catalog"})
        return AppleMusicTrackParser.parse(response)

    def get_artist(self, artist_id: str) -> Artist:
        route = "me/library/artists" if is_library_artist(artist_id) else "catalog/us/artists"
        response = self.get(
            f"{APPLE_MUSIC_API}/{route}/{artist_id}",
            params={"include": "catalog,albums", "include[albums]": "tracks"},
        )
        return AppleMusicArtistParser.parse(response)

    def get_playlist(self, playlist_id: str) -> Playlist:
        route = "me/library/playlists" if is_library_playlist(playlist_id) else "catalog/us/playlists"

        def get_playlist_tracks(playlist_id: str, offset: int = 0, limit: int = 100) -> list[Track]:
            response = AppleMusicPlaylistTracksResponse.model_validate(
                self.get(
                    f"{APPLE_MUSIC_API}/{route}/{playlist_id}/tracks",
                    params={"offset": offset, "limit": limit, "include[library-songs]": "artists,catalog"},
                ),
            )
            tracks = [AppleMusicTrackParser.parse_track(t) for t in response.data]
            if response.next and (offsets := parse_qs(urlparse(response.next).query).get("offset")):
                tracks.extend(get_playlist_tracks(playlist_id, int(offsets[0]), limit))
            return tracks

        playlist = AppleMusicPlaylistParser.parse(self.get(f"{APPLE_MUSIC_API}/{route}/{playlist_id}"))
        playlist.tracks = get_playlist_tracks(playlist_id)
        return playlist

    def get_service_certificate(self) -> bytes:
        return self.http.get(WIDEVINE_CERT_URL).content

    def get_playback(self, track_id: str) -> PlaybackSong:
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
