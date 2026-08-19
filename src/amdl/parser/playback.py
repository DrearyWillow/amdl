from amdl.domain.playback import Playback
from amdl.json_type import JSON
from amdl.models.playback import AppleMusicPlaybackResponse


class AppleMusicPlaybackParser:
    @classmethod
    def parse(cls, data: JSON) -> Playback:
        response = AppleMusicPlaybackResponse.model_validate(data)
        if (message := cls.failure_message(response)) is not None:
            raise ValueError(message)
        if response.song_list is None:
            raise ValueError("Playback response missing songs list")
        return Playback(songs=response.song_list)

    @staticmethod
    def failure_message(response: AppleMusicPlaybackResponse) -> str | None:
        if response.dialog and response.dialog.message:
            return response.dialog.message
        return response.customer_message or response.failure_type
