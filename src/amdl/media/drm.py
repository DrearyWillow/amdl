import base64
from pathlib import Path

from pywidevine import PSSH, Cdm, Device
from pywidevine.license_protocol_pb2 import WidevinePsshData

from amdl.apple_music.client import AppleMusicClient


class WidevineDRM:
    def __init__(self, client: AppleMusicClient) -> None:
        device_path: Path = Path(__file__).parent / "device.wvd"
        assert device_path.exists(), f"Widevine device file not found at {device_path}"
        self.device: Device = Device.load(device_path)
        self.cdm: Cdm = Cdm.from_device(self.device)

        self.client: AppleMusicClient = client
        self.service_certificate: bytes = self.client.get_service_certificate()

    def generate_pssh(self, kid_b64: str) -> PSSH:
        """Generate PSSH (Protection Scheme Specific Header) from Key ID"""
        kid = base64.standard_b64decode(kid_b64)
        wv_data = WidevinePsshData(key_ids=[kid], algorithm="AESCTR", protection_scheme=0x63656E63)
        pssh = PSSH.new(system_id=PSSH.SystemId.Widevine, init_data=wv_data, version=0)
        return pssh

    def get_license_challenge(self, session_id: bytes, kid_b64: str) -> str:
        """Generate license challenge for key request"""
        pssh = self.generate_pssh(kid_b64)
        challenge_bytes = self.cdm.get_license_challenge(session_id, pssh)
        challenge = base64.b64encode(challenge_bytes).decode()
        return challenge

    def parse_license_and_get_key(self, session_id: bytes, license_data: bytes) -> str:
        """Parse license and extract content key"""
        self.cdm.parse_license(session_id, license_data)
        keys = self.cdm.get_keys(session_id)
        content_key = next(k.key for k in keys if k.type == "CONTENT")
        return base64.b64encode(bytes(content_key)).decode("utf-8")

    def get_content_key(self, kid_b64: str, track_id: str) -> str:
        session_id = self.cdm.open()
        try:
            _ = self.cdm.set_service_certificate(session_id, self.service_certificate,)
            challenge = self.get_license_challenge(session_id, kid_b64)
            license_data = self.client.get_license(challenge, kid_b64, track_id)
            return self.parse_license_and_get_key(session_id, license_data)
        finally:
            self.cdm.close(session_id)
