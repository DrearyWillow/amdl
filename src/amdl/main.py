import logging

from amdl.cli import ArgParser
lazy from amdl.apple_music.auth import AppleMusicAuthenticator
lazy from amdl.apple_music.urls import parse_apple_music_url
lazy from amdl.downloader import Downloader

logger = logging.getLogger(__name__)


def main() -> None:
    args = ArgParser.parse()
    auth = AppleMusicAuthenticator()

    if args.logout:
        auth.clear_credentials()
        return

    if not auth.login():
        logger.warning("Authentication failed. Clearing credentials and prompting login.")
        if not auth.login():
            raise SystemExit("Authentication failed.")

    if not args.url:
        raise SystemExit("Error: A valid Apple Music URL is required.")

    am_type, resource_id = parse_apple_music_url(args.url)

    with Downloader(auth) as d:
        d.download(am_type, resource_id, args.directory, args.url)


if __name__ == "__main__":
    main()
