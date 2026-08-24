import logging
from argparse import ArgumentParser
from pathlib import Path
from unittest.mock import patch

import pytest

from amdl.cli import (
    Arguments,
    ParsedArguments,
    _configure_logging,  # pyright: ignore[reportPrivateUsage]
    _resolve_directory,  # pyright: ignore[reportPrivateUsage]
    _validate_arguments,  # pyright: ignore[reportPrivateUsage]
    parse_arguments,
)
from amdl.config import KEYRING_NAME


class TestResolveDirectory:
    @staticmethod
    def test_explicit_directory(tmp_path: Path) -> None:
        assert _resolve_directory(tmp_path, save_dir=False) == tmp_path

    @staticmethod
    def test_explicit_directory_saved(tmp_path: Path) -> None:
        with patch("amdl.cli.keyring.set_password") as set_password:
            result = _resolve_directory(tmp_path, save_dir=True)

        assert result == tmp_path
        set_password.assert_called_once_with(KEYRING_NAME, "directory", str(tmp_path))

    @staticmethod
    def test_saved_directory(tmp_path: Path) -> None:
        with patch("amdl.cli.keyring.get_password", return_value=str(tmp_path)):
            result = _resolve_directory(None, save_dir=False)
        assert result == tmp_path

    @staticmethod
    def test_saved_directory_is_expanded(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/home/test")
        with patch("amdl.cli.keyring.get_password", return_value="~/music"):
            result = _resolve_directory(None, save_dir=False)

        assert result == Path("/home/test/music")

    @staticmethod
    def test_no_saved_directory_uses_current_directory(tmp_path: Path) -> None:
        with (
            patch("amdl.cli.keyring.get_password", return_value=None),
            patch("amdl.cli.Path.cwd", return_value=tmp_path),
        ):
            result = _resolve_directory(None, save_dir=False)

        assert result == tmp_path

    @staticmethod
    def test_empty_saved_directory_uses_current_directory(tmp_path: Path) -> None:
        with (
            patch("amdl.cli.keyring.get_password", return_value=""),
            patch("amdl.cli.Path.cwd", return_value=tmp_path),
        ):
            result = _resolve_directory(None, save_dir=False)

        assert result == tmp_path


class TestConfigureLogging:
    @staticmethod
    def test_normal_logging() -> None:
        with patch("amdl.cli.logging.basicConfig") as basic_config:
            _configure_logging(debug_mode=False)

        basic_config.assert_called_once_with(
            format="%(message)s",
            level=logging.INFO,
        )

    @staticmethod
    def test_debug_logging() -> None:
        with patch("amdl.cli.logging.basicConfig") as basic_config:
            _configure_logging(debug_mode=True)

        basic_config.assert_called_once_with(
            format="\033[36m%(asctime)s:%(msecs)03d\033[0m "
            "\033[37m%(levelname)s\033[0m "
            "\033[35m%(name)s\033[0m %(message)s",
            level=logging.DEBUG,
            datefmt="%H:%M:%S",
        )


class TestValidateArguments:
    @pytest.mark.parametrize(
        "arguments",
        [
            # --logout + URL
            ParsedArguments(
                url="https://music.apple.com/us/album/foo/123",
                directory=None,
                save_dir=False,
                logout=True,
                debug=False,
            ),
            # --logout + --directory
            ParsedArguments(
                url=None,
                directory=Path("/music"),
                save_dir=False,
                logout=True,
                debug=False,
            ),
            # no URL and no --logout
            ParsedArguments(
                url=None,
                directory=None,
                save_dir=False,
                logout=False,
                debug=False,
            ),
            # --directory without URL
            ParsedArguments(
                url=None,
                directory=Path("/music"),
                save_dir=False,
                logout=False,
                debug=False,
            ),
            # --save-dir without --directory
            ParsedArguments(
                url="https://music.apple.com/us/album/foo/123",
                directory=None,
                save_dir=True,
                logout=False,
                debug=False,
            ),
        ],
    )
    @staticmethod
    def test_invalid_arguments(arguments: ParsedArguments) -> None:
        parser = ArgumentParser()

        with pytest.raises(SystemExit):
            _validate_arguments(arguments, parser)

    @staticmethod
    @pytest.mark.parametrize(
        "arguments",
        [
            ParsedArguments(
                url="https://music.apple.com/us/album/foo/123",
                directory=None,
                save_dir=False,
                logout=False,
                debug=False,
            ),
            ParsedArguments(
                url="https://music.apple.com/us/album/foo/123",
                directory=Path("/music"),
                save_dir=False,
                logout=False,
                debug=False,
            ),
            ParsedArguments(
                url="https://music.apple.com/us/album/foo/123",
                directory=Path("/music"),
                save_dir=True,
                logout=False,
                debug=False,
            ),
            ParsedArguments(
                url=None,
                directory=None,
                save_dir=False,
                logout=True,
                debug=False,
            ),
        ],
    )
    def test_valid_arguments(arguments: ParsedArguments) -> None:
        parser = ArgumentParser()
        _validate_arguments(arguments, parser)


class TestParseArguments:
    @staticmethod
    def test_url_only() -> None:
        with (
            patch("sys.argv", ["amdl", "https://music.apple.com/us/album/foo/123"]),
            patch("amdl.cli._resolve_directory", return_value=Path("/music")),
            patch("amdl.cli._configure_logging") as configure_logging,
        ):
            result = parse_arguments()

        assert result == Arguments(
            url="https://music.apple.com/us/album/foo/123",
            directory=Path("/music"),
            save_dir=False,
            logout=False,
            debug=False,
        )
        configure_logging.assert_called_once_with(debug_mode=False)

    @staticmethod
    def test_all_options(tmp_path: Path) -> None:
        url = "https://music.apple.com/us/album/foo/123"

        with (
            patch(
                "sys.argv",
                [
                    "amdl",
                    url,
                    "--directory",
                    str(tmp_path),
                    "--save-dir",
                    "--debug",
                ],
            ),
            patch("amdl.cli._configure_logging") as configure_logging,
        ):
            result = parse_arguments()

        assert result == Arguments(
            url=url,
            directory=tmp_path,
            save_dir=True,
            logout=False,
            debug=True,
        )
        configure_logging.assert_called_once_with(debug_mode=True)

    @staticmethod
    def test_logout() -> None:
        with (
            patch("sys.argv", ["amdl", "--logout"]),
            patch("amdl.cli._resolve_directory", return_value=Path("/music")),
            patch("amdl.cli._configure_logging"),
        ):
            result = parse_arguments()

        assert result == Arguments(
            url=None,
            directory=Path("/music"),
            save_dir=False,
            logout=True,
            debug=False,
        )

    @staticmethod
    @pytest.mark.parametrize(
        "arguments",
        [
            ["https://music.apple.com/us/album/foo/123", "--logout"],
            ["--logout", "--directory", "/music"],
            ["--directory", "/music"],
            ["--save-dir"],
            [],
        ],
    )
    def test_invalid_command_line(arguments: list[str]) -> None:
        with patch("sys.argv", ["amdl", *arguments]), pytest.raises(SystemExit):
            parse_arguments()

    @staticmethod
    def test_directory_is_resolved(tmp_path: Path) -> None:
        url = "https://music.apple.com/us/album/foo/123"

        with (
            patch(
                "sys.argv",
                ["amdl", url, "--directory", str(tmp_path)],
            ),
            patch("amdl.cli._configure_logging"),
            patch("amdl.cli._resolve_directory", return_value=Path("/resolved")) as resolve,
        ):
            result = parse_arguments()

        resolve.assert_called_once_with(tmp_path, save_dir=False)
        assert result.directory == Path("/resolved")
