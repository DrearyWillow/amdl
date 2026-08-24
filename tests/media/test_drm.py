import base64
from unittest.mock import MagicMock, patch

import pytest

from amdl.media.drm import PSSH, WidevineDRM


class TestWidevineDRM:
    @staticmethod
    def make_client() -> MagicMock:
        client = MagicMock()
        client.get_service_certificate.return_value = b"certificate"
        return client

    @staticmethod
    def make_drm() -> tuple[WidevineDRM, MagicMock, MagicMock]:
        client = TestWidevineDRM.make_client()
        device = MagicMock()
        cdm = MagicMock()

        with (
            patch("amdl.media.drm.Path.exists", return_value=True),
            patch("amdl.media.drm.Device.load", return_value=device),
            patch("amdl.media.drm.Cdm.from_device", return_value=cdm),
        ):
            drm = WidevineDRM(client)

        return drm, cdm, client

    @staticmethod
    def test_init() -> None:
        client = TestWidevineDRM.make_client()
        device = MagicMock()
        cdm = MagicMock()

        with (
            patch("amdl.media.drm.Path.exists", return_value=True) as exists,
            patch("amdl.media.drm.Device.load", return_value=device) as load,
            patch("amdl.media.drm.Cdm.from_device", return_value=cdm) as from_device,
        ):
            drm = WidevineDRM(client)

        exists.assert_called_once_with()
        load.assert_called_once()
        from_device.assert_called_once_with(device)
        client.get_service_certificate.assert_called_once_with()

        assert drm.device is device
        assert drm.cdm is cdm
        assert drm.client is client
        assert drm.service_certificate == b"certificate"

    @staticmethod
    def test_init_missing_device() -> None:
        client = TestWidevineDRM.make_client()

        with (
            patch("amdl.media.drm.Path.exists", return_value=False),
            pytest.raises(FileNotFoundError, match=r"Widevine device file not found"),
        ):
            WidevineDRM(client)

    @staticmethod
    def test_generate_pssh() -> None:
        kid = base64.b64encode(b"kid").decode()

        pssh = WidevineDRM.generate_pssh(kid)

        assert isinstance(pssh, PSSH)

    @staticmethod
    def test_get_license_challenge() -> None:
        drm, cdm, _ = TestWidevineDRM.make_drm()

        session_id = b"session"
        kid = base64.b64encode(b"kid").decode()
        challenge = b"challenge"

        cdm.get_license_challenge.return_value = challenge

        with patch.object(
            drm,
            "generate_pssh",
            return_value=MagicMock(),
        ) as generate_pssh:
            result = drm.get_license_challenge(session_id, kid)

        generate_pssh.assert_called_once_with(kid)
        cdm.get_license_challenge.assert_called_once_with(session_id, generate_pssh.return_value)
        assert result == base64.b64encode(challenge).decode()

    @staticmethod
    def test_parse_license_and_get_key() -> None:
        drm, cdm, _ = TestWidevineDRM.make_drm()

        session_id = b"session"
        license_data = b"license"
        content_key = b"content-key"

        content_key_item = MagicMock()
        content_key_item.type = "CONTENT"
        content_key_item.key = content_key

        other_key = MagicMock()
        other_key.type = "SIGNING"
        other_key.key = b"other-key"

        cdm.get_keys.return_value = [other_key, content_key_item]

        result = drm.parse_license_and_get_key(session_id, license_data)

        cdm.parse_license.assert_called_once_with(session_id, license_data)
        cdm.get_keys.assert_called_once_with(session_id)
        assert result == base64.b64encode(content_key).decode("utf-8")

    @staticmethod
    def test_parse_license_and_get_key_no_content_key() -> None:
        drm, cdm, _ = TestWidevineDRM.make_drm()

        session_id = b"session"
        cdm.get_keys.return_value = []

        with pytest.raises(StopIteration):
            drm.parse_license_and_get_key(session_id, b"license")

    @staticmethod
    def test_get_content_key() -> None:
        drm, cdm, client = TestWidevineDRM.make_drm()

        session_id = b"session"
        kid = base64.b64encode(b"kid").decode()
        track_id = "track"
        challenge = "challenge"
        license_data = b"license"
        content_key = "content-key"

        cdm.open.return_value = session_id
        client.get_license.return_value = license_data

        with (
            patch.object(
                drm,
                "get_license_challenge",
                return_value=challenge,
            ) as get_challenge,
            patch.object(
                drm,
                "parse_license_and_get_key",
                return_value=content_key,
            ) as parse_license,
        ):
            result = drm.get_content_key(kid, track_id)

        cdm.open.assert_called_once_with()
        cdm.set_service_certificate.assert_called_once_with(
            session_id,
            drm.service_certificate,
        )
        get_challenge.assert_called_once_with(session_id, kid)
        client.get_license.assert_called_once_with(
            challenge,
            kid,
            track_id,
        )
        parse_license.assert_called_once_with(
            session_id,
            license_data,
        )
        cdm.close.assert_called_once_with(session_id)
        assert result == content_key

    @staticmethod
    def test_get_content_key_closes_session_on_error() -> None:
        drm, cdm, _ = TestWidevineDRM.make_drm()

        session_id = b"session"
        kid = base64.b64encode(b"kid").decode()

        cdm.open.return_value = session_id

        with (
            patch.object(drm, "get_license_challenge", side_effect=RuntimeError("challenge failed")),
            pytest.raises(RuntimeError, match="challenge failed"),
        ):
            drm.get_content_key(kid, "track")

        cdm.close.assert_called_once_with(session_id)
