import base64
import hashlib
import secrets
import string
from datetime import datetime
from urllib.parse import parse_qs, quote

import requests

from config import get_config
from utils import build_requests_proxy, get_working_proxy


def get_proxy():
    return build_requests_proxy(get_working_proxy())


def generate_code_verifier(length=128):
    alphabet = string.ascii_letters + string.digits + "-._~"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_code_challenge(code_verifier):
    sha256_hash = hashlib.sha256(code_verifier.encode()).digest()
    return base64.urlsafe_b64encode(sha256_hash).decode().rstrip("=")


def wait_for_any(page, locators, timeout=5):
    end_time = datetime.now().timestamp() + timeout
    while datetime.now().timestamp() < end_time:
        for locator in locators:
            element = page.ele(locator, timeout=0.2)
            if element:
                return element
        page.wait(0.2)
    return False


def handle_oauth2_form(page, email):
    try:
        login_input = wait_for_any(page, ["css:[name='loginfmt']"], timeout=20)
        if login_input:
            login_input.input(email, clear=True)

        next_button = wait_for_any(page, ["css:#idSIButton9"], timeout=7)
        if next_button:
            next_button.click()

        consent_button = wait_for_any(
            page, ["css:[data-testid='appConsentPrimaryButton']"], timeout=20
        )
        if consent_button:
            consent_button.click()
    except Exception:
        pass


def get_access_token(page, email, max_retries=3):
    for _ in range(max_retries):
        result = _try_get_access_token(page, email)
        if result[0] is not False:
            return result
    return False, False, False


def _try_get_access_token(page, email):
    data = get_config()

    scopes = data["oauth2"]["Scopes"]
    client_id = data["oauth2"]["client_id"]
    redirect_url = data["oauth2"]["redirect_url"]
    email_suffix = data["email_suffix"]

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_url,
        "scope": " ".join(scopes),
        "response_mode": "query",
        "prompt": "select_account",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    authorize_url = (
        "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?"
        + "&".join(f"{k}={quote(v)}" for k, v in params.items())
    )

    captured_url = None
    page.listen.start(redirect_url)

    try:
        try:
            page.wait(0.25)
            page.get(authorize_url, wait="interactive", timeout=30)
        except Exception:
            return False, False, False

        handle_oauth2_form(page, f"{email}{email_suffix}")

        max_refreshes = 1
        refresh_count = 0
        refresh_interval = 200

        for i in range(400):
            packet = page.listen.wait(timeout=0.1)
            if packet and redirect_url in packet.url and "code=" in packet.url:
                captured_url = packet.url
                break

            current_url = page.url or ""
            if "res=error" in current_url or "error" in current_url.split("?")[-1]:
                return False, False, False

            if i > 0 and i % refresh_interval == 0:
                if refresh_count >= max_refreshes:
                    return False, False, False
                refresh_count += 1
                try:
                    page.refresh()
                except Exception:
                    pass
        else:
            return False, False, False
    finally:
        page.listen.stop()

    if not captured_url or "code=" not in captured_url:
        return False, False, False

    auth_code = parse_qs(captured_url.split("?")[1])["code"][0]

    try:
        response = requests.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "code": auth_code,
                "redirect_uri": redirect_url,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
                "scope": " ".join(scopes),
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            proxies=get_proxy(),
        )

        if "refresh_token" in response.json():
            tokens = response.json()
            return (
                tokens["refresh_token"],
                tokens.get("access_token", ""),
                datetime.now().timestamp() + tokens["expires_in"],
            )
    except Exception:
        return False, False, False

    return False, False, False
