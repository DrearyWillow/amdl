from collections.abc import Mapping
from json import dump

from amdl.apple_music.auth import AppleMusicAuthenticator
from amdl.apple_music.client import AppleMusicClient
from amdl.json_type import JSON

# ID = "l.p7MSx1z"
ID = "i.NJvNOVXTP90VpGV"
FILENAME = "dev/output.json"


def patch_client(client: AppleMusicClient) -> AppleMusicClient:
    original_get = client.get
    original_post = client.post

    def patched_get(url: str, params: Mapping[str, str | int] | None = None) -> JSON:
        response = original_get(url, params)
        with open(FILENAME, "w") as f:
            dump(response, f, indent=2)
        return response
    client.get = patched_get  # type: ignore[method-assign]

    def patched_post(url: str, json: Mapping[str, str | bool]) -> JSON:
        response = original_post(url, json)
        with open(FILENAME, "w") as f:
            dump(response, f, indent=2)
        return response
    client.post = patched_post  # type: ignore[method-assign]

    return client


def main() -> None:
    auth = AppleMusicAuthenticator()

    if not auth.login():
        raise SystemExit("Authentication failed")

    patched = patch_client(AppleMusicClient(auth))

    # print(patched.get_album(ID))
    print(patched.get_playback(ID))


if __name__ == "__main__":
    main()
