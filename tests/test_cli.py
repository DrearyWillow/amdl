from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from amdl.cli import Download, Logout, parse_arguments
from amdl.config import KEYRING_NAME


@pytest.fixture
def console() -> Console:
    return Console()


def test_download_with_url(console: Console) -> None:
    with (
        patch("sys.argv", [KEYRING_NAME, "https://music.apple.com/us/song/test/123"]),
        patch("amdl.cli.keyring.get_password", return_value=None),
    ):
        result = parse_arguments(console)

    assert result == Download(
        url="https://music.apple.com/us/song/test/123",
        directory=Path.cwd(),
    )


def test_download_with_directory(console: Console, tmp_path: Path) -> None:
    with (
        patch(
            "sys.argv",
            [KEYRING_NAME, "-d", str(tmp_path), "https://music.apple.com/us/song/test/123"],
        ),
        patch("amdl.cli.keyring.get_password") as get_password,
        patch("amdl.cli.keyring.set_password") as set_password,
    ):
        result = parse_arguments(console)

    assert result == Download(
        url="https://music.apple.com/us/song/test/123",
        directory=tmp_path,
    )
    get_password.assert_not_called()
    set_password.assert_not_called()


def test_download_with_saved_directory(
    console: Console,
    tmp_path: Path,
) -> None:
    with (
        patch(
            "sys.argv",
            [KEYRING_NAME, "https://music.apple.com/us/song/test/123"],
        ),
        patch(
            "amdl.cli.keyring.get_password",
            return_value=str(tmp_path),
        ) as get_password,
    ):
        result = parse_arguments(console)

    assert result == Download(
        url="https://music.apple.com/us/song/test/123",
        directory=tmp_path,
    )
    get_password.assert_called_once_with(KEYRING_NAME, "directory")


def test_download_with_no_saved_directory(console: Console) -> None:
    with (
        patch(
            "sys.argv",
            [KEYRING_NAME, "https://music.apple.com/us/song/test/123"],
        ),
        patch("amdl.cli.keyring.get_password", return_value=None) as get_password,
    ):
        result = parse_arguments(console)

    assert result == Download(
        url="https://music.apple.com/us/song/test/123",
        directory=Path.cwd(),
    )
    get_password.assert_called_once_with(KEYRING_NAME, "directory")


def test_save_directory(console: Console, tmp_path: Path) -> None:
    with (
        patch(
            "sys.argv",
            [
                KEYRING_NAME,
                "--save-dir",
                "-d",
                str(tmp_path),
                "https://music.apple.com/us/song/test/123",
            ],
        ),
        patch("amdl.cli.keyring.set_password") as set_password,
    ):
        result = parse_arguments(console)

    assert result == Download(
        url="https://music.apple.com/us/song/test/123",
        directory=tmp_path,
    )
    set_password.assert_called_once_with(KEYRING_NAME, "directory", str(tmp_path))


def test_logout(console: Console) -> None:
    with (
        patch("sys.argv", [KEYRING_NAME, "--logout"]),
        patch("amdl.cli.keyring.get_password") as get_password,
        patch("amdl.cli.keyring.set_password") as set_password,
    ):
        result = parse_arguments(console)

    assert isinstance(result, Logout)
    get_password.assert_not_called()
    set_password.assert_not_called()


@pytest.mark.parametrize(
    "argv",
    [
        [KEYRING_NAME],
        [KEYRING_NAME, "--save-dir"],
    ],
)
def test_missing_url(console: Console, argv: list[str]) -> None:
    with patch("sys.argv", argv), pytest.raises(SystemExit):
        parse_arguments(console)


def test_save_dir_requires_directory(console: Console) -> None:
    with (
        patch(
            "sys.argv",
            [KEYRING_NAME, "--save-dir", "https://music.apple.com/us/song/test/123"],
        ),
        pytest.raises(SystemExit),
    ):
        parse_arguments(console)


@pytest.mark.parametrize(
    "argv",
    [
        [KEYRING_NAME, "--logout", "https://music.apple.com/us/song/test/123"],
        [KEYRING_NAME, "--logout", "--directory", "downloads"],
        [KEYRING_NAME, "--logout", "--save-dir"],
    ],
)
def test_logout_rejects_download_arguments(
    console: Console,
    argv: list[str],
) -> None:
    with (
        patch("sys.argv", argv),
        patch("amdl.cli.keyring.get_password") as get_password,
        patch("amdl.cli.keyring.set_password") as set_password,
        pytest.raises(SystemExit),
    ):
        parse_arguments(console)

    get_password.assert_not_called()
    set_password.assert_not_called()
