from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from amdl.models.common import AppleMusicArtwork
from amdl.models.track import AppleMusicTrackCatalogRelationship


class AppleMusicAlbumAttributes(BaseModel):
    name: str
    artist_name: str = Field(alias="artistName")
    release_date: date = Field(alias="releaseDate")
    artwork: AppleMusicArtwork
    url: HttpUrl | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    @field_validator("name", mode="before")
    @classmethod
    def strip_single_ep(cls, name: str) -> str:
        return name.removesuffix(" - Single").removesuffix(" - EP")


class AppleMusicAlbumCatalogRelationship(BaseModel):
    data: list[AppleMusicAlbum]


class AppleMusicAlbumRelationships(BaseModel):
    catalog: AppleMusicAlbumCatalogRelationship | None = None
    tracks: AppleMusicTrackCatalogRelationship | None = None


class AppleMusicAlbum(BaseModel):
    id: str
    attributes: AppleMusicAlbumAttributes
    relationships: AppleMusicAlbumRelationships | None = None


class AppleMusicAlbumResponse(BaseModel):
    data: list[AppleMusicAlbum]
