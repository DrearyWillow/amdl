from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from amdl.cli import Download, Logout
from amdl.main import main


class TestMain:
    @staticmethod
    def test_download() -> None:
        url = "https://music.apple.com/us/album/test/123"
        directory = Path("downloads")
        action = Download(url=url, directory=directory)

        console = Console()
        auth = MagicMock()
        downloader = MagicMock()
        downloader.__enter__.return_value = downloader

        with (
            patch("amdl.main.Console", return_value=console),
            patch("amdl.main.parse_arguments", return_value=action) as parse_arguments,
            patch("amdl.main.AppleMusicAuthenticator", return_value=auth) as authenticator,
            patch("amdl.main.parse_apple_music_url", return_value=("album", "123")) as parse_url,
            patch("amdl.main.Downloader", return_value=downloader) as downloader_class,
        ):
            main()

        parse_arguments.assert_called_once_with(console)
        authenticator.assert_called_once_with()
        auth.login.assert_called_once_with()
        parse_url.assert_called_once_with(url)
        downloader_class.assert_called_once_with(auth, console=console)
        downloader.download.assert_called_once_with("album", "123", directory, url)
        downloader.__enter__.assert_called_once_with()
        downloader.__exit__.assert_called_once()

    @staticmethod
    def test_logout() -> None:
        action = Logout()

        console = Console()
        auth = MagicMock()
        downloader = MagicMock()

        with (
            patch("amdl.main.Console", return_value=console),
            patch("amdl.main.parse_arguments", return_value=action) as parse_arguments,
            patch("amdl.main.AppleMusicAuthenticator", return_value=auth) as authenticator,
            patch("amdl.main.Downloader", return_value=downloader),
            patch("amdl.main.parse_apple_music_url") as parse_url,
        ):
            main()

        parse_arguments.assert_called_once_with(console)
        authenticator.assert_called_once_with()
        auth.logout.assert_called_once_with()
        parse_url.assert_not_called()
        downloader.assert_not_called()

    @staticmethod
    def test_invalid_url() -> None:
        url = "not-an-apple-music-url"
        action = Download(
            url=url,
            directory=Path("downloads"),
        )

        console = Console()
        auth = MagicMock()

        with (
            patch("amdl.main.Console", return_value=console),
            patch("amdl.main.parse_arguments", return_value=action),
            patch("amdl.main.AppleMusicAuthenticator", return_value=auth),
            patch(
                "amdl.main.parse_apple_music_url", side_effect=SystemExit("Error: A valid Apple Music URL is required.")
            ) as parse_url,
            patch("amdl.main.Downloader") as downloader,
            pytest.raises(SystemExit, match=r"Error: A valid Apple Music URL is required\."),
        ):
            main()

        auth.login.assert_called_once_with()
        parse_url.assert_called_once_with(url)
        downloader.assert_not_called()
