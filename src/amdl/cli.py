import logging
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from rich.highlighter import ReprHighlighter
from rich.logging import RichHandler
lazy import keyring

from amdl.config import KEYRING_NAME

if TYPE_CHECKING:
    from rich.console import Console

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


def _resolve_directory(directory: Path | None, *, save_dir: bool) -> Path:
    if directory is None:
        saved_dir = keyring.get_password(KEYRING_NAME, "directory")
        return Path(saved_dir).expanduser() if saved_dir else Path.cwd()

    if save_dir:
        logger.info('Saving output directory "%s" for subsequent runs', directory)
        keyring.set_password(KEYRING_NAME, "directory", str(directory))

    return directory


def _configure_logging(console: Console, *, debug_mode: bool) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if debug_mode else logging.INFO,
        handlers=[
            RichHandler(
                show_time=False,
                show_level=False,
                show_path=False,
                console=console,
                highlighter=ReprHighlighter(),
            )
        ],
    )


def _validate_arguments(arguments: ParsedArguments, parser: ArgumentParser) -> None:
    if arguments.logout and arguments.url is not None:
        parser.error("--logout cannot be used with a URL")
    if arguments.logout and arguments.directory is not None:
        parser.error("--logout cannot be used with --directory")
    if arguments.directory is not None and arguments.url is None:
        parser.error("--directory requires a URL")
    if arguments.url is None and not arguments.logout:
        parser.error("a URL is required unless --logout is specified")
    if arguments.save_dir and arguments.directory is None:
        parser.error("--save-dir requires --directory is specified")


def _create_parser() -> ArgumentParser:
    parser = ArgumentParser(description="Download tracks from Apple Music.")
    _ = parser.add_argument("url", nargs="?", type=str, help="Apple Music URL to download")
    _ = parser.add_argument("-d", "--directory", type=Path, help="Directory to download to")
    _ = parser.add_argument("--save-dir", action="store_true", help="Remember specified directory for future runs")
    _ = parser.add_argument("--logout", action="store_true", help="Clear stored Apple Music credentials")
    _ = parser.add_argument("--debug", action="store_true", help="Display debug logging")
    return parser


def parse_arguments(*, console: Console) -> Arguments:
    parser = _create_parser()
    args = parser.parse_args()

    parsed = ParsedArguments(
        url=cast("str | None", args.url),
        directory=cast("Path | None", args.directory),
        save_dir=cast("bool", args.save_dir),
        logout=cast("bool", args.logout),
        debug=cast("bool", args.debug),
    )

    _validate_arguments(parsed, parser)
    _configure_logging(console, debug_mode=parsed.debug)

    directory = _resolve_directory(parsed.directory, save_dir=parsed.save_dir)
    logger.debug('Determined output directory: "%s"', directory)

    return Arguments(parsed.url, directory, parsed.save_dir, parsed.logout, parsed.debug)
