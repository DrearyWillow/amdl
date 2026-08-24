import base64
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from amdl.media.downloader import MediaDownloader


class TestMediaDownloader:
    @staticmethod
    def make_downloader() -> MediaDownloader:
        client = MagicMock()
        downloader = MediaDownloader.__new__(MediaDownloader)
        downloader.client = client
        downloader.decryptor = Path("mp4decrypt")
        return downloader

    @staticmethod
    def test_init() -> None:
        client = MagicMock()

        with patch("amdl.media.downloader.Path.exists", return_value=True):
            downloader = MediaDownloader(client)

        assert downloader.client is client
        assert downloader.decryptor.name == "mp4decrypt"

    @staticmethod
    def test_init_requires_decryptor() -> None:
        client = MagicMock()

        with (
            patch("amdl.media.downloader.Path.exists", return_value=False),
            pytest.raises(FileNotFoundError, match="mp4decrypt missing at"),
        ):
            MediaDownloader(client)

    @staticmethod
    def test_download_encrypted(tmp_path: Path) -> None:
        downloader = TestMediaDownloader.make_downloader()
        client = cast("MagicMock", downloader.client)
        client.fetch_content.return_value = b"encrypted media"

        output_path = tmp_path / "song.m4a"

        result = downloader.download_encrypted("https://example.com/song.m4a", output_path)

        encrypted_path = tmp_path / "song.m4a.encrypted"

        client.fetch_content.assert_called_once_with("https://example.com/song.m4a")
        assert result == encrypted_path
        assert encrypted_path.read_bytes() == b"encrypted media"

    @staticmethod
    def test_decrypt() -> None:
        downloader = TestMediaDownloader.make_downloader()

        encrypted_path = Path("song.m4a.encrypted")
        output_path = Path("song.m4a")

        kid = base64.b64encode(b"kid").decode()
        key = base64.b64encode(b"key").decode()

        result = MagicMock()
        result.returncode = 0

        with patch("amdl.media.downloader.subprocess.run", return_value=result) as run:
            downloader.decrypt(encrypted_path, output_path, kid, key)

        run.assert_called_once_with(
            [downloader.decryptor, "--key", "6b6964:6b6579", encrypted_path, output_path],
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def test_decrypt_raises_when_mp4decrypt_fails() -> None:
        downloader = TestMediaDownloader.make_downloader()

        result = MagicMock()
        result.returncode = 1
        result.stderr = "decryption failed"

        with (
            patch("amdl.media.downloader.subprocess.run", return_value=result),
            pytest.raises(RuntimeError, match="mp4decrypt failed: decryption failed"),
        ):
            downloader.decrypt(
                Path("song.m4a.encrypted"),
                Path("song.m4a"),
                base64.b64encode(b"kid").decode(),
                base64.b64encode(b"key").decode(),
            )

    @staticmethod
    def test_download_and_decrypt(tmp_path: Path) -> None:
        downloader = TestMediaDownloader.make_downloader()

        encrypted_path = tmp_path / "song.m4a.encrypted"
        output_path = tmp_path / "song.m4a"

        with (
            patch.object(downloader, "download_encrypted", return_value=encrypted_path) as download_encrypted,
            patch.object(downloader, "decrypt") as decrypt,
        ):
            encrypted_path.touch()

            downloader.download_and_decrypt("https://example.com/song.m4a", output_path, "kid", "key")

        download_encrypted.assert_called_once_with("https://example.com/song.m4a", output_path)
        decrypt.assert_called_once_with(encrypted_path, output_path, "kid", "key")
        assert not encrypted_path.exists()

    @staticmethod
    def test_download_direct(tmp_path: Path) -> None:
        downloader = TestMediaDownloader.make_downloader()
        client = cast("MagicMock", downloader.client)
        client.fetch_content.return_value = b"media"
        output_path = tmp_path / "song.m4a"
        downloader.download_direct("https://example.com/song.m4a", output_path)
        client.fetch_content.assert_called_once_with("https://example.com/song.m4a")
        assert output_path.read_bytes() == b"media"

    @staticmethod
    def test_download_without_kid_uses_direct_download() -> None:
        downloader = TestMediaDownloader.make_downloader()
        output_path = Path("song.m4a")

        with (
            patch.object(downloader, "download_direct") as download_direct,
            patch.object(downloader, "download_and_decrypt") as download_and_decrypt,
        ):
            downloader.download("https://example.com/song.m4a", output_path, None, None)

        download_direct.assert_called_once_with("https://example.com/song.m4a", output_path)
        download_and_decrypt.assert_not_called()

    @staticmethod
    def test_download_requires_key_when_kid_is_provided() -> None:
        downloader = TestMediaDownloader.make_downloader()
        output_path = Path("song.m4a")

        with (
            patch.object(downloader, "download_direct") as download_direct,
            patch.object(downloader, "download_and_decrypt") as download_and_decrypt,
            pytest.raises(ValueError, match="DRM key required when KID is provided"),
        ):
            downloader.download("https://example.com/song.m4a", output_path, "kid", None)

        download_direct.assert_not_called()
        download_and_decrypt.assert_not_called()

    @staticmethod
    def test_download_with_kid_and_key_uses_decryption() -> None:
        downloader = TestMediaDownloader.make_downloader()
        output_path = Path("song.m4a")

        with (
            patch.object(downloader, "download_direct") as download_direct,
            patch.object(downloader, "download_and_decrypt") as download_and_decrypt,
        ):
            downloader.download("https://example.com/song.m4a", output_path, "kid", "key")

        download_direct.assert_not_called()
        download_and_decrypt.assert_called_once_with("https://example.com/song.m4a", output_path, "kid", "key")
