import base64
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from amdl.apple_music.client import AppleMusicClient


class MediaDownloader:
    def __init__(self, client: AppleMusicClient) -> None:
        self.client: AppleMusicClient = client
        self.decryptor: Path = Path(__file__).parent / "mp4decrypt"
        if not self.decryptor.exists():
            msg = f"mp4decrypt missing at {self.decryptor}"
            raise FileNotFoundError(msg)

    def download_encrypted(self, media_url: str, output_path: Path) -> Path:
        media = self.client.fetch_content(media_url)
        encrypted_path = output_path.with_suffix(output_path.suffix + ".encrypted")
        with encrypted_path.open("wb") as file:
            _ = file.write(media)
        return encrypted_path

    def decrypt(self, encrypted_path: Path, output_path: Path, kid: str, key: str) -> None:
        kid_hex = base64.b64decode(kid).hex()
        key_hex = base64.b64decode(key).hex()
        cmd: list[str | Path] = [self.decryptor, "--key", f"{kid_hex}:{key_hex}", encrypted_path, output_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            msg = f"mp4decrypt failed: {result.stderr}"
            raise RuntimeError(msg)

    def download_and_decrypt(self, media_url: str, output_path: Path, kid: str, key: str) -> None:
        encrypted_path = self.download_encrypted(media_url, output_path)
        self.decrypt(encrypted_path, output_path, kid, key)
        encrypted_path.unlink(missing_ok=True)

    def download_direct(self, media_url: str, output_path: Path) -> None:
        media = self.client.fetch_content(media_url)
        with output_path.open("wb") as file:
            _ = file.write(media)

    def download(self, media_url: str, output_path: Path, kid: str | None, key: str | None) -> None:
        if kid is None:
            self.download_direct(media_url, output_path)
            return
        if key is None:
            raise ValueError("DRM key required when KID is provided")
        self.download_and_decrypt(media_url, output_path, kid, key)
