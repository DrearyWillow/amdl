import logging
from json import dump
from pathlib import Path
from typing import TYPE_CHECKING

from amdl.apple_music.auth import AppleMusicAuthenticator
from amdl.apple_music.client import AppleMusicClient

if TYPE_CHECKING:
    from collections.abc import Mapping

    from amdl.json_type import JSON

logger = logging.getLogger(__name__)

ID = "961113790"
FILENAME = Path("dev/output.json")


def patch_client(client: AppleMusicClient) -> AppleMusicClient:
    original_get = client.get
    original_post = client.post

    def patched_get(url: str, params: Mapping[str, str | int] | None = None) -> JSON:
        response = original_get(url, params)
        with FILENAME.open("w", encoding="utf-8") as f:
            dump(response, f, indent=2)
        return response

    def patched_post(url: str, json: Mapping[str, str | bool]) -> JSON:
        response = original_post(url, json)
        with FILENAME.open("w", encoding="utf-8") as f:
            dump(response, f, indent=2)
        return response

    client.get = patched_get  # type: ignore[method-assign]
    client.post = patched_post  # type: ignore[method-assign]

    return client


def main() -> None:
    auth = AppleMusicAuthenticator()
    auth.login()
    patched = patch_client(AppleMusicClient(auth))
    logger.debug(patched.get_album(ID))


if __name__ == "__main__":
    main()
