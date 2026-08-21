from datetime import date
from typing import Self

from pydantic import BaseModel, Field, HttpUrl, model_validator

from amdl.apple_music.schemas import AppleMusicPlaybackSong


class DomainModel(BaseModel):
    library_id: str | None = None
    catalog_id: str | None = None

    @model_validator(mode="after")
    def has_id(self) -> Self:
        if self.library_id is None and self.catalog_id is None:
            raise ValueError("A library or catalog ID is required")
        return self

    @property
    def id(self) -> str:
        if self.catalog_id is not None:
            return self.catalog_id
        if self.library_id is not None:
            return self.library_id
        raise AssertionError("A library or catalog ID is required")


class Track(DomainModel):
    library_id: str | None = None
    catalog_id: str | None = None
    name: str
    artist_name: str
    album_name: str
    track_number: int
    release_date: date | None = None
    artwork_url: str
    url: HttpUrl | None = None


class Album(DomainModel):
    library_id: str | None = None
    catalog_id: str | None = None
    name: str
    artist_name: str
    release_date: date | None = None
    artwork_url: str
    url: HttpUrl | None = None
    tracks: list[Track] = Field(default_factory=list)


class Artist(BaseModel):
    artist_id: str
    name: str
    artwork_url: str
    albums: list[Album]


class Playback(BaseModel):
    songs: list[AppleMusicPlaybackSong]


class Profile(BaseModel):
    username: str
    handle: str
    artwork_url: str


class Playlist(BaseModel):
    id: str
    name: str
    artwork_url: str
    tracks: list[Track] = Field(default_factory=list)


class Pin(BaseModel):
    id: str
    type: str
    name: str
    artwork_url: str | None = None
    artist_name: str | None = None
    track: Track | None = None
    album: Album | None = None
    artist: Artist | None = None
    playlist: Playlist | None = None
