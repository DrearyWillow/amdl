from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
