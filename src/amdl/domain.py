from datetime import date

from pydantic import BaseModel, Field, HttpUrl

from amdl.apple_music.schemas import AppleMusicPlaybackSong


class Track(BaseModel):
    id: str
    name: str
    artist_name: str
    album_name: str
    track_number: int
    release_date: date | None = None
    artwork_url: str
    url: HttpUrl | None = None


class Album(BaseModel):
    id: str
    name: str
    artist_name: str
    release_date: date | None = None
    artwork_url: str
    url: HttpUrl | None = None
    tracks: list[Track] = Field(default_factory=list)


class Artist(BaseModel):
    id: str
    name: str
    artwork_url: str | None = None
    albums: list[Album]


class Playlist(BaseModel):
    id: str
    name: str
    artwork_url: str
    tracks: list[Track] = Field(default_factory=list)


class Playback(BaseModel):
    songs: list[AppleMusicPlaybackSong]
