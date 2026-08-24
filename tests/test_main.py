from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from amdl.main import main


class TestMain:
    @staticmethod
    def test_main() -> None:
        args = MagicMock()
        args.logout = False
        args.url = "https://music.apple.com/us/album/test/123"
        args.directory = Path("downloads")

        auth = MagicMock()
        downloader = MagicMock()
        downloader.__enter__.return_value = downloader

        with (
            patch("amdl.main.parse_arguments", return_value=args) as parse_arguments,
            patch("amdl.main.AppleMusicAuthenticator", return_value=auth) as authenticator,
            patch("amdl.main.parse_apple_music_url", return_value=("album", "123")) as parse_url,
            patch("amdl.main.Downloader", return_value=downloader) as downloader_class,
        ):
            main()

        parse_arguments.assert_called_once_with()
        authenticator.assert_called_once_with()
        auth.startup.assert_called_once_with(logout=False)
        parse_url.assert_called_once_with(args.url)
        downloader_class.assert_called_once_with(auth)
        downloader.download.assert_called_once_with(
            "album",
            "123",
            args.directory,
            args.url,
        )
        downloader.__enter__.assert_called_once_with()
        downloader.__exit__.assert_called_once()

    @staticmethod
    def test_main_missing_url() -> None:
        args = MagicMock()
        args.logout = False
        args.url = ""
        args.directory = Path("downloads")

        auth = MagicMock()

        with (
            patch("amdl.main.parse_arguments", return_value=args),
            patch("amdl.main.AppleMusicAuthenticator", return_value=auth),
            patch("amdl.main.parse_apple_music_url") as parse_url,
            patch("amdl.main.Downloader") as downloader,
            pytest.raises(
                SystemExit,
                match=r"Error: A valid Apple Music URL is required\.",
            ),
        ):
            main()

        auth.startup.assert_called_once_with(logout=False)
        parse_url.assert_not_called()
        downloader.assert_not_called()
