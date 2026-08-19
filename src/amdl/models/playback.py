from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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
