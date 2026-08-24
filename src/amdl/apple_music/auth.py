import contextlib
import logging
import re
from dataclasses import dataclass

lazy import keyring
lazy from keyring.errors import PasswordDeleteError
lazy from playwright.sync_api import BrowserContext, sync_playwright
lazy from playwright.sync_api import Error as PlaywrightError

from amdl.config import APPLE_MUSIC_URL, KEYRING_NAME

logger = logging.getLogger(__name__)


@dataclass
class AppleMusicCredentials:
    user_token: str
    media_token: str


class LoginCancelledError(Exception):
    pass


class AppleMusicAuthenticator:
    def __init__(self) -> None:
        self.credentials: AppleMusicCredentials | None = None

    def login(self) -> None:
        try:
            if not self._login():
                logger.warning("Authentication failed. Clearing credentials and prompting login.")
                if not self._login():
                    raise SystemExit("Authentication failed.")
        except LoginCancelledError as e:
            raise SystemExit("Login cancelled: browser was closed") from e

    def _login(self) -> bool:
        credentials = self._load_credentials()
        if credentials is not None:
            self.credentials = credentials
            return True
        self._clear_credentials()

        credentials = self._browser_login()
        if credentials is None:
            return False

        self.credentials = credentials
        self._save_credentials(credentials)
        logger.info("Authentication successful")
        return True

    def logout(self) -> None:
        self._clear_credentials()
        logger.info("Logged out")

    def _clear_credentials(self) -> None:
        logger.debug("Deleting credentials from keyring")
        self.credentials = None
        for key in ("user_token", "media_token"):
            with contextlib.suppress(PasswordDeleteError):
                keyring.delete_password(KEYRING_NAME, key)

    @staticmethod
    def _load_credentials() -> AppleMusicCredentials | None:
        user_token = keyring.get_password(KEYRING_NAME, "user_token")
        media_token = keyring.get_password(KEYRING_NAME, "media_token")
        return AppleMusicCredentials(user_token, media_token) if user_token and media_token else None

    @staticmethod
    def _save_credentials(credentials: AppleMusicCredentials) -> None:
        keyring.set_password(KEYRING_NAME, "user_token", credentials.user_token)
        keyring.set_password(KEYRING_NAME, "media_token", credentials.media_token)

    def _browser_login(self) -> AppleMusicCredentials | None:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            try:
                context = browser.new_context()
                page = context.new_page()
                _ = page.goto(APPLE_MUSIC_URL)

                while True:
                    user_token = self._find_user_token(context)
                    if user_token is not None:
                        media_token = self._acquire_media_token(context)
                        return AppleMusicCredentials(user_token, media_token)

                    if page.is_closed():
                        raise LoginCancelledError("Browser was closed")

                    try:
                        page.wait_for_timeout(500)
                    except PlaywrightError as e:
                        raise LoginCancelledError("Browser was closed") from e

            finally:
                browser.close()

    @staticmethod
    def _find_user_token(context: BrowserContext) -> str | None:
        for cookie in context.cookies():
            if cookie.get("name") == "media-user-token":
                return cookie.get("value")
        return None

    @staticmethod
    def _acquire_media_token(context: BrowserContext) -> str:
        # fetch main page
        response = context.request.get(APPLE_MUSIC_URL)
        html = response.text()

        # find index JS file
        match = re.search(r'/assets/index[^"]*\.js', html)
        if not match:
            raise RuntimeError("Could not find index JS URI")
        index_js_uri = match.group(0)

        # fetch index JS file
        response = context.request.get(f"{APPLE_MUSIC_URL}{index_js_uri}")
        js = response.text()

        # extract the JWT token (starts with eyJ)
        match = re.search(r'"(eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)"', js)
        if not match:
            raise RuntimeError("Could not find media token in JS")

        return match.group(1)
