from pathlib import Path

from amdl.apple_music import AppleMusicAuthenticator, parse_apple_music_url
from amdl.cli import ArgParser
from amdl.config import SAVE_DIRECTORY
from amdl.downloader import Downloader


def main() -> None:
    args = ArgParser.parse()
    auth = AppleMusicAuthenticator()

    if args.logout:
        auth.clear_credentials()
        return

    if not args.url:
        raise SystemExit("Error: A valid Apple Music URL is required.")

    if not auth.login():
        raise SystemExit("Authentication failed")

    url_type, am_id = parse_apple_music_url(args.url)
    config_dir = Path(SAVE_DIRECTORY).expanduser() if SAVE_DIRECTORY else None
    output_dir = args.directory or config_dir or Path.cwd()

    downloader = Downloader(auth)
    if args.only_artwork:
        downloader.art(url_type, am_id, output_dir)
    else:
        downloader.media(url_type, am_id, output_dir, args.url)


if __name__ == "__main__":
    main()
