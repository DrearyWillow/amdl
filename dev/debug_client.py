import json
from collections.abc import Mapping

from amdl.apple_music.auth import AppleMusicAuthenticator
from amdl.apple_music.client import AppleMusicClient
from amdl.json_type import JSON

ID = "961113790"
FILENAME = "dev/output.json"


def patch_client(client: AppleMusicClient) -> AppleMusicClient:
    original_get = client.get

    def patched_get(url: str, params: Mapping[str, str | int] | None = None) -> JSON:
        response = original_get(url, params)
        with open(FILENAME, "w") as f:
            json.dump(response, f, indent=2)
        return response

    client.get = patched_get  # type: ignore[method-assign]
    return client


def main() -> None:
    auth = AppleMusicAuthenticator()

    if not auth.login():
        raise SystemExit("Authentication failed")

    patched = patch_client(AppleMusicClient(auth))

    print(patched.get_album(ID))


if __name__ == "__main__":
    main()
