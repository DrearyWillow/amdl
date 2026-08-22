from pathlib import Path

from amdl.apple_music import (
    AppleMusicAuthenticator,
    AppleMusicType,
    parse_apple_music_url,
)
from amdl.cli import ArgParser, define_logger
from amdl.config import SAVE_DIRECTORY
from amdl.downloader import Downloader, DownloadType


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
    download_type = DownloadType.ART if args.only_artwork else DownloadType.MEDIA
    config_dir = Path(SAVE_DIRECTORY).expanduser() if SAVE_DIRECTORY else None
    output_dir = args.directory or config_dir or Path.cwd()

    if am_type in {
        AppleMusicType.PROFILE,
        AppleMusicType.MUSIC_VIDEO,
        AppleMusicType.STATION,
        AppleMusicType.CURATOR,
        AppleMusicType.APPLE_CURATOR,
        AppleMusicType.RECORD_LABEL,
    }:
        raise NotImplementedError(f"URL type `{am_type.name}` not supported")

    with Downloader(auth) as d:
        d.download(download_type, am_type, resource_id, output_dir, args.url)


if __name__ == "__main__":
    main()
