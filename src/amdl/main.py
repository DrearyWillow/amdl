from pathlib import Path

from amdl.apple_music import AppleMusicAuthenticator, AppleMusicUrlType, parse_apple_music_url
from amdl.cli import ArgParser
from amdl.config import SAVE_DIRECTORY
from amdl.downloader import Downloader, DownloadType


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
    download_type = DownloadType.ART if args.only_artwork else DownloadType.MEDIA

    if url_type in (
        AppleMusicUrlType.CURATOR,
        AppleMusicUrlType.APPLE_CURATOR,
        AppleMusicUrlType.RECORD_LABEL,
        AppleMusicUrlType.STATION,
        AppleMusicUrlType.MUSIC_VIDEO,
    ):
        raise NotImplementedError(f"URL `{url_type.name}` not supported")

    _ = Downloader(auth).download(download_type, url_type, am_id, output_dir, args.url)


if __name__ == "__main__":
    main()
