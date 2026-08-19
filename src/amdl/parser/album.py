from amdl.domain.album import Album
from amdl.json_type import JSON
from amdl.models.album import AppleMusicAlbum, AppleMusicAlbumResponse
from amdl.parser.track import AppleMusicTrackParser


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
