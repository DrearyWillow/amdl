from amdl.domain.track import Track
from amdl.json_type import JSON
from amdl.models.track import AppleMusicTrack, AppleMusicTrackResponse


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
