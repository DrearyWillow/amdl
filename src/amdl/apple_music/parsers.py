from amdl.apple_music.schemas import (
    AppleMusicAlbum,
    AppleMusicAlbumResponse,
    AppleMusicLicenseResponse,
    AppleMusicPlaybackResponse,
    AppleMusicTrack,
    AppleMusicTrackResponse,
)
from amdl.domain import Album, Playback, Track
from amdl.json_type import JSON


class AppleMusicTrackParser:
    @classmethod
    def parse(cls, data: JSON) -> Track:
        response = AppleMusicTrackResponse.model_validate(data)
        resource = response.data[0]
        return cls.parse_track(resource)

    @classmethod
    def parse_track(cls, resource: AppleMusicTrack) -> Track:
        if cls._is_library_track(resource):
            catalog = cls._catalog_track(resource)
            catalog_id = catalog.id if catalog is not None else resource.attributes.play_params.catalog_id
            attributes = catalog.attributes if catalog is not None else resource.attributes
        else:
            catalog_id = resource.id
            attributes = resource.attributes

        return Track(
            library_id=resource.id,
            catalog_id=catalog_id,
            name=attributes.name,
            artist_name=attributes.artist_name,
            album_name=attributes.album_name,
            track_number=attributes.track_number,
            release_date=attributes.release_date,
            artwork_url=attributes.artwork.url,
            url=attributes.url,
        )

    @staticmethod
    def _catalog_track(resource: AppleMusicTrack) -> AppleMusicTrack | None:
        if resource.relationships is None:
            return None

        catalog = resource.relationships.catalog

        if catalog is None or not catalog.data:
            return None

        return catalog.data[0]

    @staticmethod
    def _is_library_track(resource: AppleMusicTrack) -> bool:
        return resource.id.startswith("i.")


class AppleMusicPlaybackParser:
    @classmethod
    def parse(cls, data: JSON) -> Playback:
        response = AppleMusicPlaybackResponse.model_validate(data)
        if (message := cls.failure_message(response)) is not None:
            raise ValueError(message)
        if response.song_list is None:
            raise ValueError("Playback response missing songs list")
        return Playback(songs=response.song_list)

    @staticmethod
    def failure_message(response: AppleMusicPlaybackResponse) -> str | None:
        if response.dialog and response.dialog.message:
            return response.dialog.message
        return response.customer_message or response.failure_type


class AppleMusicAlbumParser:
    @classmethod
    def parse(cls, data: JSON) -> Album:
        response = AppleMusicAlbumResponse.model_validate(data)
        resource = response.data[0]
        return cls.parse_album(resource)

    @classmethod
    def parse_album(cls, resource: AppleMusicAlbum) -> Album:
        if cls._is_library_album(resource):
            catalog = cls._catalog_album(resource)
            attributes = catalog.attributes if catalog is not None else resource.attributes
            library_id = resource.id
            catalog_id = catalog.id if catalog is not None else None
        else:
            attributes = resource.attributes
            library_id = None
            catalog_id = resource.id

        album = Album(
            library_id=library_id,
            catalog_id=catalog_id,
            name=attributes.name,
            artist_name=attributes.artist_name,
            artwork_url=attributes.artwork.url,
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

    @staticmethod
    def _is_library_album(resource: AppleMusicAlbum) -> bool:
        return resource.id.startswith("l.")


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
            raise ValueError(f"License error: {error_msg}")

    @staticmethod
    def check_license(licence: str) -> None:
        if not licence:
            raise ValueError("No license data received from Apple")
