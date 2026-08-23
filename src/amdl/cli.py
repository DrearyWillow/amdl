import logging
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class Arguments:
    url: str | None
    directory: Path | None
    logout: bool
    debug: bool


class ArgParser:
    @staticmethod
    def create_parser() -> ArgumentParser:
        parser = ArgumentParser(description="Download tracks from Apple Music.")
        _ = parser.add_argument("url", nargs="?", help="Apple Music URL to download")
        _ = parser.add_argument("-d", "--directory", type=Path, help="Directory to download to")
        _ = parser.add_argument("--logout", action="store_true", help="Clear stored Apple Music credentials")
        _ = parser.add_argument("--debug", action="store_true", help="Display debug logging")
        return parser

    @staticmethod
    def validate(arguments: Arguments, parser: ArgumentParser) -> None:
        if arguments.logout and arguments.url is not None:
            parser.error("--logout cannot be used with a URL")
        if arguments.logout and arguments.directory is not None:
            parser.error("--logout cannot be used with --directory")
        if arguments.url is None and not arguments.logout:
            parser.error("a URL is required unless --logout or --pins is specified")
        if arguments.directory is not None and arguments.url is None:
            parser.error("--directory requires a URL")

    @classmethod
    def parse(cls) -> Arguments:
        parser = cls.create_parser()
        args = parser.parse_args()

        arguments = Arguments(
            url=cast(str | None, args.url),
            directory=cast(Path | None, args.directory),
            logout=cast(bool, args.logout),
            debug=cast(bool, args.debug),
        )

        cls.validate(arguments, parser)
        return arguments


def define_logger(debug_mode: bool) -> None:
    RESET = "\033[0m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    if not debug_mode:
        logging.basicConfig(format="%(message)s", level=logging.INFO)
        return

    fmt = f"{CYAN}%(asctime)s:%(msecs)03d{RESET} {WHITE}%(levelname)s{RESET} {MAGENTA}%(name)s{RESET} %(message)s"
    logging.basicConfig(format=fmt, level=logging.DEBUG, datefmt="%H:%M:%S")
