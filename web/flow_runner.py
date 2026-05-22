"""单次注册流程的执行函数(从 main.py 的 process_single_flow 迁移)。"""

import os

from config import get_config
from get_token import get_access_token
from utils import generate_strong_password, random_email


def process_single_flow(controller, assigned_proxy=None):
    page = None
    try:
        page = controller.get_thread_page(assigned_proxy)
        if not page:
            return {"success": False, "oauth_success": False}

        email = random_email()
        password = generate_strong_password()

        result = controller.outlook_register(page, email, password)
        if result and not controller.enable_oauth2:
            return {"success": True, "oauth_success": False}
        if not result:
            return {"success": False, "oauth_success": False}

        config = get_config()
        client_id = config["oauth2"]["client_id"]
        token_result = get_access_token(page, email)
        if token_result[0]:
            refresh_token, _access_token, _expire_at = token_result
            results_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "Results", "outlook_token.txt"
            )
            with open(results_path, "a", encoding="utf-8") as f2:
                f2.write(
                    f"{email}{controller.email_suffix}----{password}----"
                    f"{client_id}----{refresh_token}\n"
                )
            print(f"[Success: TokenAuth] - {email}{controller.email_suffix}")
            return {"success": True, "oauth_success": True}
        return {"success": True, "oauth_success": False}
    except Exception as e:
        print(f"[Error: Flow] - {e}")
        return {"success": False, "oauth_success": False}
    finally:
        if page:
            controller.clean_up(page, "done_browser")
