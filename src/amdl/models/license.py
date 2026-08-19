from pydantic import BaseModel


class AppleMusicLicenseResponse(BaseModel):
    status: int
    license: str
