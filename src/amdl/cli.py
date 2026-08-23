import logging
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import cast

lazy import keyring

from amdl.config import KEYRING_NAME

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Arguments:
    url: str | None
    directory: Path
    save_dir: bool
    logout: bool
    debug: bool


@dataclass(frozen=True)
class ParsedArguments:
    url: str | None
    directory: Path | None
    save_dir: bool
    logout: bool
    debug: bool


class ArgParser:
    @staticmethod
    def create_parser() -> ArgumentParser:
        parser = ArgumentParser(description="Download tracks from Apple Music.")
        _ = parser.add_argument("url", nargs="?", type=str, help="Apple Music URL to download")
        _ = parser.add_argument("-d", "--directory", type=Path, help="Directory to download to")
        _ = parser.add_argument("--save-dir", action="store_true", help="Remember specified directory for future runs")
        _ = parser.add_argument("--logout", action="store_true", help="Clear stored Apple Music credentials")
        _ = parser.add_argument("--debug", action="store_true", help="Display debug logging")
        return parser

    @staticmethod
    def validate(arguments: ParsedArguments, parser: ArgumentParser) -> None:
        if arguments.logout and arguments.url is not None:
            parser.error("--logout cannot be used with a URL")
        if arguments.logout and arguments.directory is not None:
            parser.error("--logout cannot be used with --directory")
        if arguments.url is None and not arguments.logout:
            parser.error("a URL is required unless --logout is specified")
        if arguments.directory is not None and arguments.url is None:
            parser.error("--directory requires a URL")
        if arguments.save_dir and arguments.directory is None:
            parser.error("--save-dir requires --directory is specified")

    @classmethod
    def parse(cls) -> Arguments:
        parser = cls.create_parser()
        args = parser.parse_args()

        parsed = ParsedArguments(
            url=cast(str | None, args.url),
            directory=cast(Path | None, args.directory),
            save_dir=cast(bool, args.save_dir),
            logout=cast(bool, args.logout),
            debug=cast(bool, args.debug),
        )

        cls.validate(parsed, parser)
        cls.define_logger(parsed.debug)
        directory = cls.directory(parsed.directory, parsed.save_dir)
        logger.debug(f"Determined output directory: {directory}")
        return Arguments(parsed.url, directory, parsed.save_dir, parsed.logout, parsed.debug)

    @staticmethod
    def directory(directory: Path | None, save_dir: bool) -> Path:
        if directory is not None:
            if save_dir:
                logger.info(f"Saving output directory `{directory}` for subsequent runs")
                keyring.set_password(KEYRING_NAME, "directory", str(directory))
            return directory

        saved_dir = keyring.get_password(KEYRING_NAME, "directory")
        return Path(saved_dir).expanduser() if saved_dir else Path.cwd()

    @staticmethod
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
