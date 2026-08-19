import base64
from pathlib import Path

from pywidevine import PSSH, Cdm, Device
from pywidevine.license_protocol_pb2 import WidevinePsshData


class WidevineDRM:
    def __init__(self) -> None:
        device_path: Path = Path(__file__).parent / "device.wvd"
        assert device_path.exists(), f"Widevine device file not found at {device_path}"
        self.device: Device = Device.load(device_path)
        self.cdm: Cdm = Cdm.from_device(self.device)
        self.session_id: bytes = self.cdm.open()

    def set_service_certificate(self, cert: bytes) -> None:
        _ = self.cdm.set_service_certificate(self.session_id, cert)

    def generate_pssh(self, kid_b64: str) -> PSSH:
        """Generate PSSH (Protection Scheme Specific Header) from Key ID"""
        kid = base64.standard_b64decode(kid_b64)
        wv_data = WidevinePsshData(key_ids=[kid], algorithm="AESCTR", protection_scheme=0x63656E63)
        pssh = PSSH.new(system_id=PSSH.SystemId.Widevine, init_data=wv_data, version=0)
        return pssh

    def get_license_challenge(self, kid_b64: str) -> str:
        """Generate license challenge for key request"""
        pssh = self.generate_pssh(kid_b64)
        challenge_bytes = self.cdm.get_license_challenge(self.session_id, pssh)
        challenge = base64.b64encode(challenge_bytes).decode()
        return challenge

    def parse_license_and_get_key(self, license_data: bytes) -> str:
        """Parse license and extract content key"""
        self.cdm.parse_license(self.session_id, license_data)
        keys = self.cdm.get_keys(self.session_id)
        content_key = next(k.key for k in keys if k.type == "CONTENT")
        return base64.b64encode(bytes(content_key)).decode("utf-8")
