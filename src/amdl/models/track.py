from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from amdl.models.common import AppleMusicArtwork, AppleMusicPlayParams


class AppleMusicTrackAttributes(BaseModel):
    name: str
    artist_name: str = Field(alias="artistName")
    album_name: str = Field(alias="albumName")
    track_number: int = Field(alias="trackNumber")
    release_date: date = Field(alias="releaseDate")
    artwork: AppleMusicArtwork
    play_params: AppleMusicPlayParams = Field(alias="playParams")
    url: HttpUrl | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    @field_validator("album_name", mode="before")
    @classmethod
    def strip_single_ep(cls, name: str) -> str:
        return name.removesuffix(" - Single").removesuffix(" - EP")


class AppleMusicTrackCatalogRelationship(BaseModel):
    data: list[AppleMusicTrack]


class AppleMusicTrackRelationships(BaseModel):
    catalog: AppleMusicTrackCatalogRelationship | None = None


class AppleMusicTrack(BaseModel):
    id: str
    attributes: AppleMusicTrackAttributes
    relationships: AppleMusicTrackRelationships | None = None


class AppleMusicTrackResponse(BaseModel):
    data: list[AppleMusicTrack]

