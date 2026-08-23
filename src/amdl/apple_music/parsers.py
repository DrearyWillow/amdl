import logging
from typing import TYPE_CHECKING

from amdl.apple_music.ids import is_library_album, is_library_track
from amdl.domain import Album, Artist, PlaybackSong, Playlist, Track
from amdl.media.hls import parse_hls_playlist
lazy from amdl.apple_music.schemas import (
    AppleMusicAlbum,
    AppleMusicAlbumResponse,
    AppleMusicArtist,
    AppleMusicArtistResponse,
    AppleMusicLicenseResponse,
    AppleMusicPlaybackResponse,
    AppleMusicPlaylist,
    AppleMusicPlaylistResponse,
    AppleMusicTrack,
    AppleMusicTrackResponse,
)

if TYPE_CHECKING:
    from amdl.json_type import JSON

logger = logging.getLogger(__name__)


class AppleMusicTrackParser:
    @classmethod
    def parse(cls, data: JSON) -> Track:
        response = AppleMusicTrackResponse.model_validate(data)
        resource = response.data[0]
        return cls.parse_track(resource)

    @classmethod
    def parse_track(cls, resource: AppleMusicTrack) -> Track:
        if is_library_track(resource.id):
            catalog = cls._catalog_track(resource)
            track_id = cls._library_track_id(resource, catalog)
            attributes = catalog.attributes if catalog is not None else resource.attributes
        else:
            track_id = resource.id
            attributes = resource.attributes

        return Track(
            id=track_id,
            name=attributes.name,
            artist_name=attributes.artist_name,
            album_name=attributes.album_name,
            track_number=attributes.track_number,
            release_date=attributes.release_date,
            artwork_url=attributes.artwork.url if attributes.artwork else None,
            url=attributes.url,
        )

    @staticmethod
    def _library_track_id(resource: AppleMusicTrack, catalog: AppleMusicTrack | None) -> str:
        if catalog is not None:
            return catalog.id
        if resource.attributes.play_params and resource.attributes.play_params.catalog_id:
            return resource.attributes.play_params.catalog_id
        return resource.id

    @staticmethod
    def _catalog_track(resource: AppleMusicTrack) -> AppleMusicTrack | None:
        if resource.relationships is None:
            return None

        catalog = resource.relationships.catalog

        if catalog is None or not catalog.data:
            return None

        return catalog.data[0]


class AppleMusicArtistParser:
    @classmethod
    def parse(cls, data: JSON) -> Artist:
        response = AppleMusicArtistResponse.model_validate(data)
        resource = response.data[0]
        artist = cls.parse_artist(resource)
        logger.debug("Found %d albums in artist", {len(artist.albums)})
        return artist

    @classmethod
    def parse_artist(cls, resource: AppleMusicArtist) -> Artist:
        catalog = cls._catalog_artist(resource)
        attributes = catalog.attributes if catalog is not None else resource.attributes

        return Artist(
            id=catalog.id if catalog else resource.id,
            name=attributes.name,
            artwork_url=attributes.artwork.url if attributes.artwork else None,
            albums=cls._albums(resource, catalog),
        )

    @staticmethod
    def _albums(resource: AppleMusicArtist, catalog: AppleMusicArtist | None) -> list[Album]:
        if catalog and catalog.relationships and catalog.relationships.albums:
            return [AppleMusicAlbumParser.parse_album(a) for a in catalog.relationships.albums.data]
        if resource.relationships and resource.relationships.albums:
            return [AppleMusicAlbumParser.parse_album(a) for a in resource.relationships.albums.data]
        raise ValueError("Artist has no albums.")

    @staticmethod
    def _catalog_artist(resource: AppleMusicArtist) -> AppleMusicArtist | None:
        if resource.relationships is None:
            return None

        catalog = resource.relationships.catalog

        if catalog is None or not catalog.data:
            return None

        return catalog.data[0]


class AppleMusicPlaylistParser:
    @classmethod
    def parse(cls, data: JSON) -> Playlist:
        response = AppleMusicPlaylistResponse.model_validate(data)
        resource = response.data[0]
        playlist = cls.parse_playlist(resource)
        logger.debug("Found %d tracks in playlist", len(playlist.tracks))
        return playlist

    @classmethod
    def parse_playlist(cls, resource: AppleMusicPlaylist) -> Playlist:
        return Playlist(
            id=resource.id,
            name=resource.attributes.name,
            artwork_url=resource.attributes.artwork.url if resource.attributes.artwork else None,
        )


class AppleMusicAlbumParser:
    @classmethod
    def parse(cls, data: JSON) -> Album:
        response = AppleMusicAlbumResponse.model_validate(data)
        resource = response.data[0]
        album = cls.parse_album(resource)
        logger.debug("Found %d tracks in album", len(album.tracks))
        return album

    @classmethod
    def parse_album(cls, resource: AppleMusicAlbum) -> Album:
        if is_library_album(resource.id):
            catalog = cls._catalog_album(resource)
            attributes = catalog.attributes if catalog is not None else resource.attributes
            album_id = catalog.id if catalog is not None else resource.id
        else:
            attributes = resource.attributes
            album_id = resource.id

        album = Album(
            id=album_id,
            name=attributes.name,
            artist_name=attributes.artist_name,
            artwork_url=attributes.artwork.url if attributes.artwork else None,
            release_date=attributes.release_date,
            url=attributes.url,
        )

        relationships = resource.relationships
        if relationships is None or relationships.tracks is None or not relationships.tracks.data:
            raise ValueError("Album has no tracks.")

        album.tracks = [AppleMusicTrackParser.parse_track(t) for t in relationships.tracks.data]

        return album

    @staticmethod
    def _catalog_album(resource: AppleMusicAlbum) -> AppleMusicAlbum | None:
        if resource.relationships is None:
            return None

        catalog = resource.relationships.catalog

        if catalog is None or not catalog.data:
            return None

        return catalog.data[0]


class AppleMusicPlaybackParser:
    QUALITY_PRIORITIES: tuple[str, str] = ("28:ctrp256", "32:ctrp64")

    @classmethod
    def parse(cls, data: JSON) -> PlaybackSong:
        response = AppleMusicPlaybackResponse.model_validate(data)

        if (message := cls.failure_message(response)) is not None:
            raise ValueError(message)
        if not response.song_list:
            raise ValueError("Playback response missing songs list")

        for song in response.song_list:
            for target_flavor in cls.QUALITY_PRIORITIES:
                for asset in song.assets:
                    if asset.flavor == target_flavor:
                        return parse_hls_playlist(str(asset.url))

            # direct download with no encryption
            for asset in song.assets:
                if asset.flavor is None:
                    return PlaybackSong(url=str(asset.url))

        raise ValueError("No suitable playback URL found")

    @staticmethod
    def failure_message(response: AppleMusicPlaybackResponse) -> str | None:
        if response.dialog and response.dialog.message:
            return response.dialog.message
        return response.customer_message or response.failure_type


class AppleMusicLicenseParser:
    @classmethod
    def parse(cls, data: JSON) -> str:
        response = AppleMusicLicenseResponse.model_validate(data)
        cls.check_status(response.status)
        cls.check_license(response.license)
        return response.license

    @staticmethod
    def check_status(status: int) -> None:
        if status != 0:
            error_messages = {
                -1001: "Invalid PSSH.",
                -1002: "You do not own this title.",
                -1004: "Maximum number of simultaneous streams exceeded.",
                -1017: "This content is geo-restricted.",
                -1021: "Device has insufficient security level.",
            }
            error_msg = error_messages.get(status, status) or "Unknown"
            msg = f"License error: {error_msg}"
            raise ValueError(msg)

    @staticmethod
    def check_license(licence: str) -> None:
        if not licence:
            raise ValueError("No license data received from Apple")
