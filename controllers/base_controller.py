import os
import random
import shutil
import tempfile
import threading
import time
from abc import ABC, abstractmethod

from faker import Faker

from config import get_config
from utils import format_proxy_label, get_working_proxy, release_proxy


class BaseBrowserController(ABC):
    def __init__(self):
        data = get_config()

        self.wait_time = data["bot_protection_wait"]
        self.max_captcha_retries = data["max_captcha_retries"]
        self.enable_oauth2 = data["oauth2"]["enable_oauth2"]
        self.email_suffix = data["email_suffix"]
        self.action_pause_min = 0.5
        self.action_pause_max = 1.0

        controller_config = data.get("ruyipage", {})
        self.profile_root = os.path.abspath(
            controller_config.get(
                "profile_root",
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Profiles"),
            )
        )
        os.makedirs(self.profile_root, exist_ok=True)

        self.cleanup_lock = threading.Lock()
        self.active_resources = {}

        self.results_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "Results"
        )
        os.makedirs(self.results_dir, exist_ok=True)

    @abstractmethod
    def launch_browser(self, proxy_config=None):
        pass

    @abstractmethod
    def handle_captcha(self, page):
        pass

    def get_thread_page(self, proxy_config=None):
        proxy_config = get_working_proxy(preferred_proxy=proxy_config, reserve=True)
        if not proxy_config:
            print("[Error: Proxy Pool] - 没有可用的 HTTPS 代理。")
            return False

        print(f"[Info: Proxy] - current task using {format_proxy_label(proxy_config)}")

        page, resource = self.launch_browser(proxy_config)
        if not page:
            release_proxy(proxy_config)
            return False

        resource["proxy_config"] = proxy_config
        with self.cleanup_lock:
            self.active_resources[id(page)] = resource
        return page

    def clean_up(self, page=None, type="all_browser"):
        if type == "done_browser" and page:
            self._close_resource(id(page))
            return

        if type == "all_browser":
            with self.cleanup_lock:
                page_ids = list(self.active_resources.keys())
            for page_id in page_ids:
                self._close_resource(page_id)

    def _close_resource(self, page_id):
        with self.cleanup_lock:
            resource = self.active_resources.pop(page_id, None)

        if not resource:
            return

        page = resource.get("page")
        if page:
            try:
                page.quit(timeout=5, force=True)
            except Exception:
                pass

        profile_dir = resource.get("profile_dir")
        if profile_dir:
            self._remove_profile_dir(profile_dir)

        release_proxy(resource.get("proxy_config"))

    def _remove_profile_dir(self, profile_dir, retries=8, delay=0.5):
        for _ in range(retries):
            if not os.path.exists(profile_dir):
                return
            try:
                shutil.rmtree(profile_dir)
                return
            except Exception:
                time.sleep(delay)

        if os.path.exists(profile_dir):
            print(f"[Warn: Cleanup] - profile dir not removed: {profile_dir}")

    def build_profile_dir(self):
        return tempfile.mkdtemp(prefix="ruyipage-", dir=self.profile_root)

    def human_pause(self, page, min_seconds=None, max_seconds=None):
        pause_min = self.action_pause_min if min_seconds is None else min_seconds
        pause_max = self.action_pause_max if max_seconds is None else max_seconds
        page.wait(random.uniform(pause_min, pause_max))

    def wait_for_any(self, owner, locators, timeout=5):
        end_time = time.time() + timeout
        while time.time() < end_time:
            for locator in locators:
                element = owner.ele(locator, timeout=0.2)
                if element:
                    return element
            owner.wait(0.2)
        return False

    def visible_locator_exists(self, owner, locators, timeout=1.5, min_size=8):
        end_time = time.time() + timeout
        while time.time() < end_time:
            for locator in locators:
                try:
                    elements = owner.eles(locator, timeout=0.2)
                except Exception:
                    elements = []

                for element in elements:
                    try:
                        if not element or not element.is_displayed:
                            continue
                        size = element.size or {}
                        width = int(size.get("width", 0) or 0)
                        height = int(size.get("height", 0) or 0)
                        if width < min_size or height < min_size:
                            continue
                        return element
                    except Exception:
                        continue
            owner.wait(0.2)
        return False

    def click_element(self, owner, element):
        owner.actions.move_to(
            element,
            offset_x=random.randint(-3, 3),
            offset_y=random.randint(-2, 2),
            duration=random.randint(80, 180),
        ).click().perform()

    def click_locator(self, owner, locators, timeout=5):
        element = self.wait_for_any(owner, locators, timeout=timeout)
        if not element:
            return False
        self.click_element(owner, element)
        return element

    def text_exists(self, page, text):
        try:
            return bool(
                page.run_js(
                    "return !!document.body && document.body.innerText.includes(arguments[0]);",
                    text,
                    as_expr=False,
                )
            )
        except Exception:
            return False

    def page_preview(self, page, limit=300):
        try:
            preview = page.run_js(
                "return document.body ? document.body.innerText.slice(0, arguments[0]) : '';",
                limit,
                as_expr=False,
            )
            return str(preview).replace("\r", " ").replace("\n", " ").strip()
        except Exception:
            return ""

    def page_state_summary(self, page, preview_limit=500):
        try:
            current_url = page.url or "unknown"
        except Exception:
            current_url = "unknown"

        try:
            page_title = page.title or "unknown"
        except Exception:
            page_title = "unknown"

        return current_url, page_title, self.page_preview(page, limit=preview_limit)

    def primary_button(self, page, timeout=5):
        return self.wait_for_any(
            page,
            [
                "css:[data-testid='primaryButton']",
                "css:button[type='submit']",
                "xpath://button[@data-testid='primaryButton']",
            ],
            timeout=timeout,
        )

    def click_primary_button(self, page, timeout=5):
        button = self.primary_button(page, timeout=timeout)
        if not button:
            return False
        self.click_element(page, button)
        return True

    def error_text_detected(self, page):
        return self.text_exists(page, "一些异常活动") or self.text_exists(
            page, "此站点正在维护，暂时无法使用，请稍后重试。"
        )

    def challenge_active(self, page):
        if self.mailbox_url_ready(page):
            return False

        iframe_locators = [
            "css:iframe#enforcementFrame",
            "css:iframe[title*='验证']",
            "css:iframe[src*='arkoselabs']",
            "css:iframe[src*='funcaptcha']",
        ]
        if self.visible_locator_exists(page, iframe_locators, timeout=0.5, min_size=20):
            return True

        challenge_texts = [
            "验证你不是机器人",
            "可访问性挑战",
            "再次按下",
            "请再试一次",
            "长按该按钮",
            "Click to verify",
            "Press and hold",
        ]
        return any(self.text_exists(page, text) for text in challenge_texts)

    def mailbox_shell_ready(self, page):
        mailbox_locators = [
            "css:[aria-label='新邮件']",
            "xpath://*[contains(normalize-space(.), '新邮件')]",
            "xpath://*[contains(normalize-space(.), '收件箱')]",
            "xpath://*[contains(normalize-space(.), '创建新的电子邮件')]",
            "xpath://*[contains(normalize-space(.), '重点')]",
            "xpath://*[contains(normalize-space(.), '其他')]",
        ]
        if self.visible_locator_exists(page, mailbox_locators, timeout=0.3):
            return True

        try:
            current_url = page.url or ""
        except Exception:
            current_url = ""

        try:
            page_title = page.title or ""
        except Exception:
            page_title = ""

        mailbox_url = (
            "outlook.live.com/mail" in current_url
            and "prompt=create_account" not in current_url
        )
        mailbox_title = "Outlook" in page_title or "邮件 -" in page_title
        mailbox_text = any(
            self.text_exists(page, text)
            for text in ("收件箱", "新邮件", "创建新的电子邮件", "重点", "其他")
        )
        return mailbox_url and (mailbox_title or mailbox_text)

    def mailbox_url_ready(self, page):
        try:
            current_url = page.url or ""
        except Exception:
            current_url = ""

        return "https://outlook.live.com/mail/0/" in current_url

    def get_select_state(self, element):
        try:
            value = element.run_js("return this.value;", as_expr=False)
        except Exception:
            value = ""

        try:
            text = element.run_js(
                "return this.options && this.selectedIndex >= 0 ? this.options[this.selectedIndex].text : '';",
                as_expr=False,
            )
        except Exception:
            text = ""

        return str(value or ""), str(text or "")

    def select_with_fallback(self, page, select_element, value, text_candidates, field_name):
        try:
            if select_element.select.by_value(value):
                return True
        except Exception:
            pass

        for text in text_candidates:
            try:
                if select_element.select.by_text(text):
                    return True
            except Exception:
                pass

        self.human_pause(page, 0.2, 0.5)
        self.click_element(page, select_element)

        option_locators = []
        for text in text_candidates:
            option_locators.extend(
                [
                    f"xpath://*[@role='option'][contains(normalize-space(.), '{text}')]",
                    f"xpath://option[contains(normalize-space(.), '{text}')]",
                    f"xpath://*[contains(normalize-space(.), '{text}')]",
                ]
            )

        option = self.wait_for_any(page, option_locators, timeout=3)
        if option:
            self.click_element(page, option)
            return True

        current_value, current_text = self.get_select_state(select_element)
        raise TimeoutError(
            f"{field_name} select failed; expected={value}; actual_value={current_value}; actual_text={current_text}"
        )

    def _suffix_control_locators(self):
        return [
            "xpath://*[@role='combobox' and (contains(normalize-space(.), '@outlook.com') or contains(normalize-space(.), '@hotmail.com'))]",
            "xpath://button[contains(normalize-space(.), '@outlook.com') or contains(normalize-space(.), '@hotmail.com')]",
            "xpath://*[@aria-haspopup='listbox' and (contains(@aria-label, '@outlook.com') or contains(@aria-label, '@hotmail.com'))]",
            "css:[role='combobox']",
        ]

    def _extract_suffix_from_element(self, element):
        if not element:
            return None

        candidates = []
        for attr_name in ("text", "value"):
            try:
                candidates.append(str(getattr(element, attr_name) or ""))
            except Exception:
                pass
        for attr_name in ("aria-label", "title", "value"):
            try:
                candidates.append(str(element.attr(attr_name) or ""))
            except Exception:
                pass

        merged = " ".join(candidates)
        if "@hotmail.com" in merged:
            return "@hotmail.com"
        if "@outlook.com" in merged:
            return "@outlook.com"
        return None

    def read_current_email_suffix(self, page):
        control = self.wait_for_any(page, self._suffix_control_locators(), timeout=1)
        return self._extract_suffix_from_element(control)

    def ensure_email_suffix_selected(self, page):
        desired_suffix = self.email_suffix
        current_suffix = self.read_current_email_suffix(page)

        if desired_suffix == "@outlook.com" and current_suffix in (None, "@outlook.com"):
            return True
        if current_suffix == desired_suffix:
            return True

        control = self.wait_for_any(page, self._suffix_control_locators(), timeout=5)
        if not control:
            raise TimeoutError("email suffix control not found")

        self.human_pause(page, 0.2, 0.5)
        self.click_element(page, control)
        self.human_pause(page, 0.2, 0.5)

        option = self.click_locator(
            page,
            [
                f"xpath://*[@role='option'][contains(normalize-space(.), '{desired_suffix}')]",
                f"xpath://*[contains(normalize-space(.), '{desired_suffix}')]",
            ],
            timeout=5,
        )
        if not option:
            raise TimeoutError(f"email suffix option not found: {desired_suffix}")

        self.human_pause(page, 0.3, 0.6)
        current_suffix = self.read_current_email_suffix(page)
        if current_suffix != desired_suffix:
            raise TimeoutError(
                f"email suffix selection did not stick; expected={desired_suffix}; actual={current_suffix}"
            )
        return True

    def mailbox_ready(self, page):
        if self.mailbox_url_ready(page):
            return True
        if self.mailbox_shell_ready(page):
            return True

        try:
            current_url = page.url or ""
        except Exception:
            current_url = ""

        if (
            "outlook.live.com/mail" in current_url
            and "prompt=create_account" not in current_url
            and not self.challenge_active(page)
        ):
            return True

        return False

    def wait_for_mailbox_ready(self, page, timeout=40):
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.error_text_detected(page):
                return False, "risk"
            if self.mailbox_url_ready(page):
                return True, "mailbox_url_ready"
            if self.mailbox_ready(page):
                return True, "mailbox_ready"
            if self.mailbox_shell_ready(page):
                return True, "mailbox_shell_ready"
            if self.challenge_active(page):
                if not self.handle_captcha(page):
                    return False, "captcha_still_active"
                continue
            page.wait(0.25)
        current_url, page_title, preview = self.page_state_summary(page, preview_limit=220)
        shell_ready = self.mailbox_shell_ready(page)
        challenge_still_active = self.challenge_active(page)
        print(
            "[Debug: MailboxWait] - "
            f"shell_ready={shell_ready}; challenge_active={challenge_still_active}; "
            f"url={current_url}; title={page_title}; preview={preview}"
        )
        return False, "timeout"

    def outlook_register(self, page, email, password):
        fake = Faker()
        lastname = fake.last_name()
        firstname = fake.first_name()
        year = str(random.randint(1960, 2005))
        month = str(random.randint(1, 12))
        day = str(random.randint(1, 28))

        email_input_locators = [
            "css:[aria-label='新建电子邮件']",
            "css:input[aria-label='新建电子邮件']",
            "css:input[name='MemberName']",
        ]
        consent_locators = [
            "xpath://button[contains(normalize-space(.), '同意并继续')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '同意并继续')]",
            "xpath://span[contains(normalize-space(.), '同意并继续')]",
        ]

        try:
            page.get(
                "https://outlook.live.com/mail/0/?prompt=create_account",
                wait="interactive",
                timeout=20,
            )
        except Exception as e:
            print(f"[Error: Entry Navigation] - 无法打开注册页: {e}")
            return False

        start_time = time.time()
        try:
            entry_element = self.wait_for_any(
                page, consent_locators + email_input_locators, timeout=30
            )
            if not entry_element:
                raise TimeoutError("entry elements not found")

            if self.text_exists(page, "同意并继续"):
                self.human_pause(page)
                if not self.click_locator(page, consent_locators, timeout=5):
                    raise TimeoutError("consent button not found")
                self.wait_for_any(page, email_input_locators, timeout=20)
        except Exception as e:
            current_url, page_title, preview = self.page_state_summary(page)
            diagnostics = []

            if self.error_text_detected(page):
                diagnostics.append("命中风控提示")
            if not self.text_exists(page, "同意并继续"):
                diagnostics.append("未找到同意并继续")
            if not self.wait_for_any(page, email_input_locators, timeout=1):
                diagnostics.append("未找到邮箱输入框")

            diagnostics_text = "；".join(diagnostics) if diagnostics else "无明确诊断"
            print(
                "[Error: Entry Page] - 无法进入注册界面: "
                f"{e}; url={current_url}; title={page_title}; "
                f"diagnostics={diagnostics_text}; preview={preview}"
            )
            return False

        try:
            self.ensure_email_suffix_selected(page)

            email_input = self.wait_for_any(page, email_input_locators, timeout=10)
            if not email_input:
                raise TimeoutError("email input not found")
            self.human_pause(page)
            self.click_element(page, email_input)
            self.human_pause(page, 0.2, 0.5)
            email_input.input(email, clear=True)

            self.human_pause(page)
            if not self.click_primary_button(page):
                raise TimeoutError("email next button not found")

            password_input = self.wait_for_any(
                page, ["css:input[type='password']"], timeout=10
            )
            if not password_input:
                raise TimeoutError("password input not found")
            self.human_pause(page)
            self.click_element(page, password_input)
            self.human_pause(page, 0.2, 0.5)
            password_input.input(password, clear=True)

            self.human_pause(page)
            if not self.click_primary_button(page):
                raise TimeoutError("password next button not found")

            birth_year_input = self.wait_for_any(
                page,
                ["css:[name='BirthYear']", "css:input[name='BirthYear']"],
                timeout=10,
            )
            if not birth_year_input:
                raise TimeoutError("birth year input not found")
            self.human_pause(page)
            birth_year_input.input(year, clear=True)

            birth_month = self.wait_for_any(page, ["css:[name='BirthMonth']"], timeout=5)
            birth_day = self.wait_for_any(page, ["css:[name='BirthDay']"], timeout=5)
            if not birth_month or not birth_day:
                raise TimeoutError("birthday selects not found")

            self.human_pause(page, 0.2, 0.5)
            self.select_with_fallback(
                page,
                birth_month,
                month,
                [month, f"{month}月", f"{month} 月"],
                "BirthMonth",
            )
            self.human_pause(page, 0.2, 0.5)
            self.select_with_fallback(
                page,
                birth_day,
                day,
                [day, f"{day}日", f"{day} 号"],
                "BirthDay",
            )

            self.human_pause(page)
            if not self.click_primary_button(page):
                raise TimeoutError("birthday next button not found")

            last_name_input = self.wait_for_any(page, ["css:#lastNameInput"], timeout=10)
            first_name_input = self.wait_for_any(page, ["css:#firstNameInput"], timeout=10)
            if not last_name_input or not first_name_input:
                month_value, month_text = self.get_select_state(birth_month)
                day_value, day_text = self.get_select_state(birth_day)
                raise TimeoutError(
                    "name inputs not found after birthday submit; "
                    f"month_value={month_value}; month_text={month_text}; "
                    f"day_value={day_value}; day_text={day_text}"
                )

            self.human_pause(page)
            self.click_element(page, last_name_input)
            self.human_pause(page, 0.2, 0.5)
            last_name_input.input(lastname, clear=True)

            self.human_pause(page, 0.2, 0.5)
            first_name_input.input(firstname, clear=True)

            remaining_wait = self.wait_time - (time.time() - start_time)
            if remaining_wait > 0:
                page.wait(remaining_wait)

            self.human_pause(page)
            if not self.click_primary_button(page):
                raise TimeoutError("profile submit button not found")

            page.wait(0.8)

            mailbox_ready = None
            reason = None

            if self.error_text_detected(page):
                print("[Error: IP or browser] - 当前 IP 注册频率过快，或浏览器环境已被风控。")
                return False

            if self.challenge_active(page):
                try:
                    if not self.handle_captcha(page):
                        raise TimeoutError("captcha failed")
                except Exception as e:
                    if self.mailbox_url_ready(page):
                        mailbox_ready, reason = True, "mailbox_url_ready_after_captcha"
                    else:
                        raise e

            if mailbox_ready is True:
                pass
            elif self.mailbox_url_ready(page):
                mailbox_ready, reason = True, "mailbox_url_ready"
            elif self.mailbox_shell_ready(page):
                mailbox_ready, reason = True, "mailbox_shell_ready"
            else:
                mailbox_ready, reason = self.wait_for_mailbox_ready(page, timeout=15)
            if not mailbox_ready:
                raise TimeoutError(f"mailbox not ready; state={reason}")
        except Exception as e:
            current_url, page_title, preview = self.page_state_summary(page)
            print(
                "[Error: Register Flow] - "
                f"{e}; url={current_url}; title={page_title}; preview={preview}"
            )
            return False

        full_email = f"{email}{self.email_suffix}"
        filename = os.path.join(
            self.results_dir,
            "logged_email.txt" if self.enable_oauth2 else "unlogged_email.txt",
        )
        with open(filename, "a", encoding="utf-8") as f:
            f.write(f"{full_email}: {password}\n")
        print(f"[Success: Email Registration] - {full_email}: {password}")

        return True
