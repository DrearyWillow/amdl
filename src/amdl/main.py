from pathlib import Path

from amdl.apple_music.auth import AppleMusicAuthenticator
from amdl.apple_music.urls import parse_apple_music_url
from amdl.cli import ArgParser
from amdl.config import SAVE_DIRECTORY
from amdl.downloader import Downloader


def main() -> None:
    args = ArgParser.parse()
    auth = AppleMusicAuthenticator()

    if args.logout:
        auth.clear_credentials()
        return

    assert args.url is not None
    url_type, am_id = parse_apple_music_url(args.url)

    if not auth.login():
        raise SystemExit("Authentication failed")

    config_dir = Path(SAVE_DIRECTORY).expanduser() if SAVE_DIRECTORY and Path(SAVE_DIRECTORY).exists() else None
    output_dir = args.directory or config_dir or Path.cwd()

    Downloader(auth).download(url_type, am_id, output_dir, args.only_artwork, args.url)


if __name__ == "__main__":
    main()
