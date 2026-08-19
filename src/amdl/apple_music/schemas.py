from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


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


class AppleMusicArtwork(BaseModel):
    url: str

    @field_validator("url", mode="before")
    @classmethod
    def artwork_url(cls, url: str) -> str:
        return url.replace("{w}", "9999").replace("{h}", "9999").replace("{c}", "bb")


class AppleMusicPlayParams(BaseModel):
    id: str
    catalog_id: str | None = Field(default=None, alias="catalogId")

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)


class AppleMusicLicenseResponse(BaseModel):
    status: int
    license: str


class AppleMusicPlaybackAsset(BaseModel):
    flavor: str
    url: HttpUrl = Field(alias="URL")

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)


class AppleMusicPlaybackSong(BaseModel):
    assets: list[AppleMusicPlaybackAsset]


class AppleMusicPlaybackDialog(BaseModel):
    message: str | None = None


class AppleMusicPlaybackResponse(BaseModel):
    customer_message: str | None = Field(default=None, alias="customerMessage")
    failure_type: str | None = Field(default=None, alias="failureType")
    dialog: AppleMusicPlaybackDialog | None = None
    song_list: list[AppleMusicPlaybackSong] | None = Field(
        default=None, alias="songList"
    )

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)


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
