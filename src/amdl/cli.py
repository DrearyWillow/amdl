from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class Arguments:
    url: str | None
    directory: Path | None
    only_artwork: bool
    logout: bool


class ArgParser:
    @staticmethod
    def create_parser() -> ArgumentParser:
        parser = ArgumentParser(description="Download tracks from Apple Music.")
        _ = parser.add_argument("url", nargs="?", help="Apple Music URL to download")
        _ = parser.add_argument("-d", "--directory", type=Path, help="Directory to download to")
        _ = parser.add_argument("--logout", action="store_true", help="Clear stored Apple Music credentials")
        _ = parser.add_argument("--art", dest="only_artwork", action="store_true", help="Only download artwork")
        return parser

    @staticmethod
    def validate(arguments: Arguments, parser: ArgumentParser) -> None:
        if arguments.logout and arguments.url is not None:
            parser.error("--logout cannot be used with a URL")
        if arguments.logout and arguments.directory is not None:
            parser.error("--logout cannot be used with --directory")
        if arguments.logout and arguments.only_artwork:
            parser.error("--logout cannot be used with --artwork")
        if not arguments.logout and arguments.url is None:
            parser.error("a URL is required unless --logout is specified")
        if arguments.directory is not None and arguments.url is None:
            parser.error("--directory requires a URL")
        if arguments.only_artwork and arguments.url is None:
            parser.error("--artwork requires a URL")

    @classmethod
    def parse(cls) -> Arguments:
        parser = cls.create_parser()
        args = parser.parse_args()

        url = cast(str | None, args.url)
        directory = cast(Path | None, args.directory)
        only_artwork = cast(bool, args.only_artwork)
        logout = cast(bool, args.logout)

        arguments = Arguments(url, directory, only_artwork, logout)
        cls.validate(arguments, parser)
        return arguments
