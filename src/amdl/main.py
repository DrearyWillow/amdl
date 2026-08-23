from pathlib import Path

from amdl.apple_music.auth import AppleMusicAuthenticator
from amdl.apple_music.urls import parse_apple_music_url
from amdl.cli import ArgParser, define_logger
from amdl.config import SAVE_DIRECTORY
from amdl.downloader import Downloader


def main() -> None:
    args = ArgParser.parse()
    define_logger(args.debug)
    auth = AppleMusicAuthenticator()

    if args.logout:
        auth.clear_credentials()
        return

    if not auth.login():
        raise SystemExit("Authentication failed")

    if not args.url:
        raise SystemExit("Error: A valid Apple Music URL is required.")

    am_type, resource_id = parse_apple_music_url(args.url)
    config_dir = Path(SAVE_DIRECTORY).expanduser() if SAVE_DIRECTORY else None
    output_dir = args.directory or config_dir or Path.cwd()

    with Downloader(auth) as d:
        d.download(am_type, resource_id, output_dir, args.url)


if __name__ == "__main__":
    main()
