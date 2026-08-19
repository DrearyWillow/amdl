from amdl.json_type import JSON
from amdl.models.license import AppleMusicLicenseResponse


class AppleMusicLicenseParser:
    @classmethod
    def parse(cls, data: JSON) -> str:
        response = AppleMusicLicenseResponse.model_validate(data)
        cls.check_status(response.status)
        cls.check_license(response.license)
        return response.license

    @staticmethod
    def check_status(status: int) -> None:
        if status != 0:
            error_messages = {
                -1001: "Invalid PSSH.",
                -1002: "You do not own this title.",
                -1004: "Maximum number of simultaneous streams exceeded.",
                -1017: "This content is geo-restricted.",
                -1021: "Device has insufficient security level.",
            }
            error_msg = error_messages.get(status, status) or "Unknown"
            raise ValueError(f"License error: {error_msg}")

    @staticmethod
    def check_license(licence: str) -> None:
        if not licence:
            raise ValueError("No license data received from Apple")
