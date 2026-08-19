from pydantic import BaseModel

from amdl.models.playback import AppleMusicPlaybackSong


class Playback(BaseModel):
    songs: list[AppleMusicPlaybackSong]

