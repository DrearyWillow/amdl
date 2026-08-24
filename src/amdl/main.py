from rich.console import Console
from rich.theme import Theme

from amdl.cli import parse_arguments
lazy from amdl.apple_music.auth import AppleMusicAuthenticator
lazy from amdl.apple_music.urls import parse_apple_music_url
lazy from amdl.downloader import Downloader


def main() -> None:
    console = Console(theme=Theme({"repr.str": "magenta"}))
    args = parse_arguments(console=console)

    auth = AppleMusicAuthenticator()
    auth.startup(logout=args.logout)

    if not args.url:
        raise SystemExit("Error: A valid Apple Music URL is required.")

    am_type, resource_id = parse_apple_music_url(args.url)

    with Downloader(auth, console=console) as d:
        d.download(am_type, resource_id, args.directory, args.url)


if __name__ == "__main__":  # pragma: no cover
    main()
