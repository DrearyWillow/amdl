from datetime import date

from pydantic import HttpUrl

from amdl.domain.common import DomainModel


class Track(DomainModel):
    library_id: str | None = None
    catalog_id: str | None = None
    name: str
    artist_name: str
    album_name: str
    track_number: int
    release_date: date
    artwork_url: str
    url: HttpUrl | None
