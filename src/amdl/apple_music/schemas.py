from datetime import date
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class AppleMusicArtwork(BaseModel):
    url: str

    @field_validator("url", mode="before")
    @classmethod
    def assign_dimensions(cls, url: str) -> str:
        return url.replace("{w}", "9999").replace("{h}", "9999").replace("{c}", "bb")


class AppleMusicPlayParams(BaseModel):
    id: str
    catalog_id: str | None = Field(default=None, alias="catalogId")

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)


# License


class AppleMusicLicenseResponse(BaseModel):
    status: int
    license: str


# Playback


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
    song_list: list[AppleMusicPlaybackSong] | None = Field(default=None, alias="songList")

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)


# Album


class AppleMusicAlbumAttributes(BaseModel):
    name: str
    artist_name: str = Field(alias="artistName")
    release_date: date | None = Field(default=None, alias="releaseDate")
    artwork: AppleMusicArtwork
    url: HttpUrl | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    @field_validator("name", mode="before")
    @classmethod
    def strip_single_ep(cls, name: str) -> str:
        return name.removesuffix(" - Single").removesuffix(" - EP")

    @field_validator("release_date", mode="before")
    @classmethod
    def normalize_release_date(cls, value: str | date) -> str | date:
        if isinstance(value, str) and len(value) == 4 and value.isdigit():
            return date(int(value), 1, 1)
        return value


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


# Track


class AppleMusicTrackAttributes(BaseModel):
    name: str
    artist_name: str = Field(alias="artistName")
    album_name: str = Field(alias="albumName")
    track_number: int = Field(alias="trackNumber")
    release_date: date | None = Field(default=None, alias="releaseDate")
    artwork: AppleMusicArtwork
    play_params: AppleMusicPlayParams | None = Field(default=None, alias="playParams")
    url: HttpUrl | None = None

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    @field_validator("album_name", mode="before")
    @classmethod
    def strip_single_ep(cls, name: str) -> str:
        return name.removesuffix(" - Single").removesuffix(" - EP")

    @field_validator("release_date", mode="before")
    @classmethod
    def normalize_release_date(cls, value: str | date) -> str | date:
        if isinstance(value, str) and len(value) == 4 and value.isdigit():
            return date(int(value), 1, 1)
        return value


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


# Artist


class AppleMusicArtistCatalogRelationship(BaseModel):
    data: list[AppleMusicArtist]


class AppleMusicArtistAlbumRelationship(BaseModel):
    data: list[AppleMusicAlbum]


class AppleMusicArtistRelationships(BaseModel):
    catalog: AppleMusicArtistCatalogRelationship | None = None
    albums: AppleMusicArtistAlbumRelationship | None = None


class AppleMusicArtistAttributes(BaseModel):
    artwork: AppleMusicArtwork | None = None
    name: str


class AppleMusicArtist(BaseModel):
    id: str
    attributes: AppleMusicArtistAttributes
    relationships: AppleMusicArtistRelationships | None = None


class AppleMusicArtistResponse(BaseModel):
    data: list[AppleMusicArtist]


# Playlist


class AppleMusicPlaylistTracksResponse(BaseModel):
    next: str | None = None
    data: list[AppleMusicTrack]


class AppleMusicPlaylistAttributes(BaseModel):
    artwork: AppleMusicArtwork
    name: str


class AppleMusicPlaylist(BaseModel):
    id: str
    attributes: AppleMusicPlaylistAttributes


class AppleMusicPlaylistResponse(BaseModel):
    data: list[AppleMusicPlaylist]
