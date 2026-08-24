from unittest.mock import MagicMock, patch

import pytest
from keyring.errors import PasswordDeleteError

from amdl.apple_music.auth import (
    AppleMusicAuthenticator,
    AppleMusicCredentials,
    LoginCancelledError,
)
from amdl.config import APPLE_MUSIC_URL, KEYRING_NAME

EXPECTED_CREDENTIAL_COUNT = 2


class TestAppleMusicCredentials:
    @staticmethod
    def test_credentials() -> None:
        user_value = "user-token"
        media_value = "media-token"

        credentials = AppleMusicCredentials(
            user_token=user_value,
            media_token=media_value,
        )

        assert credentials.user_token == user_value
        assert credentials.media_token == media_value


class TestAppleMusicAuthenticator:
    @staticmethod
    def test_init() -> None:
        authenticator = AppleMusicAuthenticator()

        assert authenticator.credentials is None

    @staticmethod
    def test_load_credentials() -> None:
        user_value = "user-token"
        media_value = "media-token"

        with patch(
            "amdl.apple_music.auth.keyring.get_password",
            side_effect=[user_value, media_value],
        ) as get_password:
            credentials = AppleMusicAuthenticator._load_credentials()  # pyright: ignore[reportPrivateUsage]

        assert credentials == AppleMusicCredentials(
            user_token=user_value,
            media_token=media_value,
        )
        assert get_password.call_count == EXPECTED_CREDENTIAL_COUNT
        get_password.assert_any_call(KEYRING_NAME, "user_token")
        get_password.assert_any_call(KEYRING_NAME, "media_token")

    @staticmethod
    @pytest.mark.parametrize(
        ("user_value", "media_value"),
        [
            (None, "media-token"),
            ("user-token", None),
            (None, None),
            ("", "media-token"),
            ("user-token", ""),
        ],
    )
    def test_load_credentials_missing(
        user_value: str | None,
        media_value: str | None,
    ) -> None:
        with patch(
            "amdl.apple_music.auth.keyring.get_password",
            side_effect=[user_value, media_value],
        ):
            credentials = AppleMusicAuthenticator._load_credentials()  # pyright: ignore[reportPrivateUsage]

        assert credentials is None

    @staticmethod
    def test_save_credentials() -> None:
        user_value, media_value = "user-token", "media-token"
        credentials = AppleMusicCredentials(user_token=user_value, media_token=media_value)

        with patch(
            "amdl.apple_music.auth.keyring.set_password",
        ) as set_password:
            AppleMusicAuthenticator._save_credentials(credentials)  # pyright: ignore[reportPrivateUsage]

        assert set_password.call_count == EXPECTED_CREDENTIAL_COUNT
        set_password.assert_any_call(
            KEYRING_NAME,
            "user_token",
            credentials.user_token,
        )
        set_password.assert_any_call(
            KEYRING_NAME,
            "media_token",
            credentials.media_token,
        )

    @staticmethod
    def test_clear_credentials() -> None:
        authenticator = AppleMusicAuthenticator()
        user_value, media_value = "user-token", "media-token"
        authenticator.credentials = AppleMusicCredentials(user_token=user_value, media_token=media_value)

        with patch(
            "amdl.apple_music.auth.keyring.delete_password",
        ) as delete_password:
            authenticator._clear_credentials()  # pyright: ignore[reportPrivateUsage]

        assert authenticator.credentials is None
        assert delete_password.call_count == EXPECTED_CREDENTIAL_COUNT
        delete_password.assert_any_call(KEYRING_NAME, "user_token")
        delete_password.assert_any_call(KEYRING_NAME, "media_token")

    @staticmethod
    def test_clear_credentials_ignores_missing_credentials() -> None:
        authenticator = AppleMusicAuthenticator()

        with patch(
            "amdl.apple_music.auth.keyring.delete_password",
            side_effect=PasswordDeleteError(),
        ) as delete_password:
            authenticator._clear_credentials()  # pyright: ignore[reportPrivateUsage]

        assert authenticator.credentials is None
        assert delete_password.call_count == EXPECTED_CREDENTIAL_COUNT

    @staticmethod
    def test_login_uses_saved_credentials() -> None:
        authenticator = AppleMusicAuthenticator()
        user_value, media_value = "user-token", "media-token"
        credentials = AppleMusicCredentials(user_token=user_value, media_token=media_value)

        with (
            patch.object(
                authenticator,
                "_load_credentials",
                return_value=credentials,
            ) as load_credentials,
            patch.object(authenticator, "_clear_credentials") as clear_credentials,
            patch.object(authenticator, "_browser_login") as browser_login,
            patch.object(authenticator, "_save_credentials") as save_credentials,
        ):
            authenticator.login()

        assert authenticator.credentials == credentials
        load_credentials.assert_called_once_with()
        clear_credentials.assert_not_called()
        browser_login.assert_not_called()
        save_credentials.assert_not_called()

    @staticmethod
    def test_login_browser_login() -> None:
        authenticator = AppleMusicAuthenticator()
        user_value, media_value = "user-token", "media-token"
        credentials = AppleMusicCredentials(user_token=user_value, media_token=media_value)

        with (
            patch.object(
                authenticator,
                "_load_credentials",
                return_value=None,
            ) as load_credentials,
            patch.object(
                authenticator,
                "_clear_credentials",
            ) as clear_credentials,
            patch.object(
                authenticator,
                "_browser_login",
                return_value=credentials,
            ) as browser_login,
            patch.object(
                authenticator,
                "_save_credentials",
            ) as save_credentials,
        ):
            authenticator.login()

        assert authenticator.credentials == credentials
        load_credentials.assert_called_once_with()
        clear_credentials.assert_called_once_with()
        browser_login.assert_called_once_with()
        save_credentials.assert_called_once_with(credentials)

    @staticmethod
    def test_login_browser_login_fails() -> None:
        authenticator = AppleMusicAuthenticator()

        with (
            patch.object(
                authenticator,
                "_load_credentials",
                return_value=None,
            ),
            patch.object(
                authenticator,
                "_clear_credentials",
            ) as clear_credentials,
            patch.object(
                authenticator,
                "_browser_login",
                return_value=None,
            ) as browser_login,
            pytest.raises(
                SystemExit,
                match=r"Authentication failed\.",
            ),
        ):
            authenticator.login()

        assert authenticator.credentials is None
        assert clear_credentials.call_count == EXPECTED_CREDENTIAL_COUNT
        assert browser_login.call_count == EXPECTED_CREDENTIAL_COUNT

    @staticmethod
    def test_login_retries_successfully() -> None:
        authenticator = AppleMusicAuthenticator()

        with patch.object(authenticator, "_login", side_effect=[False, True]) as login:
            authenticator.login()

        assert login.call_count == EXPECTED_CREDENTIAL_COUNT

    @staticmethod
    def test_login_handles_login_cancelled() -> None:
        authenticator = AppleMusicAuthenticator()

        with (
            patch.object(
                authenticator,
                "_load_credentials",
                return_value=None,
            ),
            patch.object(
                authenticator,
                "_clear_credentials",
            ) as clear_credentials,
            patch.object(
                authenticator,
                "_browser_login",
                side_effect=LoginCancelledError("Browser was closed"),
            ),
            pytest.raises(
                SystemExit,
                match=r"Login cancelled: browser was closed",
            ),
        ):
            authenticator.login()

        clear_credentials.assert_called_once_with()

    @staticmethod
    def test_logout() -> None:
        authenticator = AppleMusicAuthenticator()

        with patch.object(
            authenticator,
            "_clear_credentials",
        ) as clear_credentials:
            authenticator.logout()

        clear_credentials.assert_called_once_with()

    @staticmethod
    def test_find_user_token() -> None:
        context = MagicMock()
        context.cookies.return_value = [
            {"name": "other-cookie", "value": "other-value"},
            {"name": "media-user-token", "value": "user-token"},
        ]

        assert AppleMusicAuthenticator._find_user_token(context) == "user-token"  # pyright: ignore[reportPrivateUsage]

    @staticmethod
    def test_find_user_token_missing() -> None:
        context = MagicMock()
        context.cookies.return_value = [
            {"name": "other-cookie", "value": "other-value"},
        ]

        assert AppleMusicAuthenticator._find_user_token(context) is None  # pyright: ignore[reportPrivateUsage]

    @staticmethod
    def test_find_user_token_missing_value() -> None:
        context = MagicMock()
        context.cookies.return_value = [
            {"name": "media-user-token"},
        ]

        assert AppleMusicAuthenticator._find_user_token(context) is None  # pyright: ignore[reportPrivateUsage]

    @staticmethod
    def test_acquire_media_token() -> None:
        context = MagicMock()

        html = '<script src="/assets/index123.js"></script>'
        token = "eyJ" + "header.eyJ" + "payload.signature"
        javascript = f'"{token}"'

        main_response = MagicMock()
        main_response.text.return_value = html

        js_response = MagicMock()
        js_response.text.return_value = javascript

        context.request.get.side_effect = [main_response, js_response]

        assert AppleMusicAuthenticator._acquire_media_token(context) == token  # pyright: ignore[reportPrivateUsage]

        assert context.request.get.call_count == EXPECTED_CREDENTIAL_COUNT
        context.request.get.assert_any_call(APPLE_MUSIC_URL)
        context.request.get.assert_any_call(
            "https://music.apple.com/assets/index123.js",
        )

    @staticmethod
    def test_acquire_media_token_index_script_missing() -> None:
        context = MagicMock()

        response = MagicMock()
        response.text.return_value = "<html></html>"
        context.request.get.return_value = response

        with pytest.raises(RuntimeError, match="Could not find index JS URI"):
            AppleMusicAuthenticator._acquire_media_token(context)  # pyright: ignore[reportPrivateUsage]

        context.request.get.assert_called_once_with(APPLE_MUSIC_URL)

    @staticmethod
    def test_acquire_media_token_missing_token() -> None:
        context = MagicMock()

        main_response = MagicMock()
        main_response.text.return_value = '<script src="/assets/index123.js"></script>'

        js_response = MagicMock()
        js_response.text.return_value = "const token = null;"

        context.request.get.side_effect = [main_response, js_response]

        with pytest.raises(
            RuntimeError,
            match="Could not find media token in JS",
        ):
            AppleMusicAuthenticator._acquire_media_token(context)  # pyright: ignore[reportPrivateUsage]

    @staticmethod
    def test_browser_login() -> None:
        authenticator = AppleMusicAuthenticator()

        context = MagicMock()
        page = MagicMock()
        browser = MagicMock()
        chromium = MagicMock()
        playwright = MagicMock()

        playwright.chromium = chromium
        chromium.launch.return_value = browser
        browser.new_context.return_value = context
        context.new_page.return_value = page

        user_value, media_value = "user-token", "media-token"
        credentials = AppleMusicCredentials(user_token=user_value, media_token=media_value)

        with (
            patch(
                "amdl.apple_music.auth.sync_playwright",
            ) as sync_playwright,
            patch.object(
                authenticator,
                "_find_user_token",
                return_value=credentials.user_token,
            ),
            patch.object(
                authenticator,
                "_acquire_media_token",
                return_value=credentials.media_token,
            ),
        ):
            sync_playwright.return_value.__enter__.return_value = playwright

            result = authenticator._browser_login()  # pyright: ignore[reportPrivateUsage]

        assert result == credentials
        chromium.launch.assert_called_once_with(headless=False)
        browser.new_context.assert_called_once_with()
        context.new_page.assert_called_once_with()
        page.goto.assert_called_once_with(APPLE_MUSIC_URL)
        browser.close.assert_called_once_with()

    @staticmethod
    def test_browser_login_browser_closed() -> None:
        authenticator = AppleMusicAuthenticator()

        context = MagicMock()
        page = MagicMock()
        browser = MagicMock()
        playwright = MagicMock()

        playwright.chromium.launch.return_value = browser
        browser.new_context.return_value = context
        context.new_page.return_value = page
        page.is_closed.return_value = True

        with patch(
            "amdl.apple_music.auth.sync_playwright",
        ) as sync_playwright:
            sync_playwright.return_value.__enter__.return_value = playwright

            with (
                patch.object(
                    authenticator,
                    "_find_user_token",
                    return_value=None,
                ),
                pytest.raises(
                    LoginCancelledError,
                    match=r"Browser was closed",
                ),
            ):
                authenticator._browser_login()  # pyright: ignore[reportPrivateUsage]

        browser.close.assert_called_once_with()

    @staticmethod
    def test_browser_login_wait_error() -> None:
        authenticator = AppleMusicAuthenticator()

        context = MagicMock()
        page = MagicMock()
        browser = MagicMock()
        playwright = MagicMock()

        playwright.chromium.launch.return_value = browser
        browser.new_context.return_value = context
        context.new_page.return_value = page
        page.is_closed.return_value = False
        page.wait_for_timeout.side_effect = Exception("Browser closed")

        with patch(
            "amdl.apple_music.auth.sync_playwright",
        ) as sync_playwright:
            sync_playwright.return_value.__enter__.return_value = playwright

            with (
                patch.object(
                    authenticator,
                    "_find_user_token",
                    return_value=None,
                ),
                patch(
                    "amdl.apple_music.auth.PlaywrightError",
                    Exception,
                ),
                pytest.raises(
                    LoginCancelledError,
                    match=r"Browser was closed",
                ),
            ):
                authenticator._browser_login()  # pyright: ignore[reportPrivateUsage]

        browser.close.assert_called_once_with()
