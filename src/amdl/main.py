from rich.console import Console
from rich.theme import Theme

from amdl.cli import Logout, parse_arguments
lazy from amdl.apple_music.auth import AppleMusicAuthenticator
lazy from amdl.apple_music.urls import parse_apple_music_url
lazy from amdl.downloader import Downloader


def main() -> None:
    console = Console(theme=Theme({"repr.str": "magenta"}))
    action = parse_arguments(console)

    auth = AppleMusicAuthenticator()
    if isinstance(action, Logout):
        auth.logout()
        return
    auth.login()

    am_type, resource_id = parse_apple_music_url(action.url)

    with Downloader(auth, console=console) as d:
        d.download(am_type, resource_id, action.directory, action.url)


if __name__ == "__main__":  # pragma: no cover
    main()
