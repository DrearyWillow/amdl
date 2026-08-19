from datetime import date

from pydantic import Field, HttpUrl

from amdl.domain.common import DomainModel
from amdl.domain.track import Track


class Album(DomainModel):
    library_id: str | None = None
    catalog_id: str | None = None
    name: str
    artist_name: str
    release_date: date
    artwork_url: str
    url: HttpUrl | None = None
    tracks: list[Track] = Field(default_factory=list)
