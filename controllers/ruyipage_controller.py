import json
import random
import time

from ruyipage import FirefoxOptions, FirefoxPage

from config import get_config
from .base_controller import BaseBrowserController


class RuyiPageController(BaseBrowserController):
    def __init__(self):
        super().__init__()
        data = get_config()

        controller_config = data.get("ruyipage", {})
        self.browser_path = controller_config.get("browser_path", "").strip()
        self.headless = bool(controller_config.get("headless", False))
        self.xpath_picker = bool(controller_config.get("xpath_picker", False))
        self.action_visual = bool(controller_config.get("action_visual", False))

    def launch_browser(self, proxy_config=None):
        profile_dir = self.build_profile_dir()

        try:
            opts = FirefoxOptions()
            opts.close_on_exit(True)
            opts.set_load_mode("eager")
            opts.set_timeouts(base=5, page_load=40, script=10)
            opts.set_pref("intl.accept_languages", "zh-CN,zh,en-US,en")
            opts.set_human_algorithm("windmouse")
            opts.headless(self.headless)
            opts.set_user_dir(profile_dir)

            # 性能优化：减少内存和 CPU 占用
            opts.set_pref("browser.cache.disk.enable", False)  # 禁用磁盘缓存
            opts.set_pref("browser.cache.memory.enable", True)  # 只用内存缓存
            opts.set_pref("browser.cache.memory.capacity", 8192)  # 限制内存缓存 8MB
            opts.set_pref("browser.sessionhistory.max_total_viewers", 0)  # 禁用后退缓存
            opts.set_pref("media.autoplay.default", 5)  # 禁止自动播放媒体
            opts.set_pref("permissions.default.image", 2)  # 禁止加载图片（可选，会影响验证码显示）
            opts.set_pref("javascript.options.mem.high_water_mark", 32)  # 限制 JS 内存 32MB

            if self.browser_path:
                opts.set_browser_path(self.browser_path)
            if proxy_config:
                opts.set_proxy(proxy_config["requests_url"])
            if self.xpath_picker:
                opts.enable_xpath_picker(True)
            if self.action_visual:
                opts.enable_action_visual(True)

            page = FirefoxPage(opts)

            # 小窗口运行：800×600 足够注册流程，减少渲染开销
            try:
                page.set_viewport(800, 600)
            except Exception:
                pass

            # 不要全屏/最大化，保持小窗口
            try:
                page.window.set_window_size(820, 650)
            except Exception:
                pass

            return page, {"page": page, "profile_dir": profile_dir}
        except Exception as e:
            self._remove_profile_dir(profile_dir)
            print(f"启动 ruyipage 浏览器失败: {e}")
            return False, False

    def _find_captcha_frame(self, page):
        locators = [
            "css:iframe#enforcementFrame",
            "css:iframe[title='验证质询']",
            "css:iframe[title*='验证']",
            "css:iframe[src*='arkoselabs']",
            "css:iframe[src*='funcaptcha']",
        ]
        for locator in locators:
            frame = page.get_frame(locator)
            if frame:
                return frame
        return None

    def _find_challenge_frame(self, outer_frame):
        locators = [
            "css:iframe[style*='display: block']",
            "css:iframe[src*='arkoselabs']",
            "css:iframe[src*='funcaptcha']",
        ]
        for locator in locators:
            frame = outer_frame.get_frame(locator)
            if frame:
                return frame

        for index in range(3):
            frame = outer_frame.get_frame(index=index)
            if frame:
                return frame
        return None

    def _resolve_frame_path(self, page, frame_path):
        scope = page
        for index in frame_path:
            try:
                scope = scope.get_frame(index=index)
            except Exception:
                return None
            if not scope:
                return None
        return scope

    def _iter_scopes(self, root):
        yield root
        try:
            children = root.get_frames()
        except Exception:
            children = []
        for child in children:
            yield from self._iter_scopes(child)

    def _challenge_button_locators(self):
        return [
            "css:[xml-roles='button']",
            "xpath://*[@xml-roles='button']",
            "xpath://*[@xml-roles='button'][.//text()[contains(., 'Press and hold') or contains(., '按住') or contains(., '长按')]]",
            "xpath://button[contains(normalize-space(.), '按住')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '按住')]",
            "xpath://*[contains(@class, 'button') and contains(normalize-space(.), '按住')]",
            "css:[aria-label='可访问性挑战']",
            "xpath://*[@aria-label='可访问性挑战']",
            "css:[aria-label='再次按下']",
            "xpath://*[@aria-label='再次按下']",
            "xpath://button[contains(normalize-space(.), '长按')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '长按')]",
            "xpath://*[contains(@class, 'button') and contains(normalize-space(.), '长按')]",
            "xpath://button[contains(normalize-space(.), '按下')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '按下')]",
            "xpath://button[@aria-label='按住']",
            "xpath://*[@aria-label='按住']",
        ]

    def _challenge_click_locators(self):
        return [
            "css:button[aria-label*='verify i am human' i]",
            "css:button[aria-label*='click to verify' i]",
            "css:button[aria-label*='i am human' i]",
            "css:[role='button'][aria-label*='verify i am human' i]",
            "css:[role='button'][aria-label*='click to verify' i]",
            "css:[role='button'][aria-label*='i am human' i]",
            "css:button[aria-label*='验证']",
            "css:[role='button'][aria-label*='验证']",
            "css:button[title*='验证']",
            "css:[role='button'][title*='验证']",
            "xpath://button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify')]",
            "xpath://button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'human')]",
            "xpath://*[@role='button'][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify')]",
            "xpath://*[@role='button'][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'human')]",
            "xpath://button[contains(normalize-space(.), '点击')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '点击')]",
            "xpath://button[contains(normalize-space(.), '单击')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '单击')]",
            "xpath://button[contains(normalize-space(.), '验证')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '验证')]",
        ]

    def _challenge_target_locators(self):
        return self._challenge_button_locators() + self._challenge_click_locators()

    def _scope_has_text(self, owner, keywords):
        try:
            text = owner.run_js(
                "return document.body ? document.body.innerText : '';",
                as_expr=False,
            )
        except Exception:
            return False

        if not text:
            return False
        return any(keyword in str(text) for keyword in keywords)

    def _scope_prefers_press(self, owner):
        return self._scope_has_text(
            owner,
            [
                "长按",
                "按住",
                "按下并按住",
                "Press and hold",
                "press and hold",
                "Press & Hold",
                "hold to verify",
            ],
        )

    def _fast_press_button_locators(self):
        return [
            "xpath://button[normalize-space(.)='按住']",
            "xpath://*[@role='button'][normalize-space(.)='按住']",
            "xpath://*[contains(@class, 'button') and normalize-space(.)='按住']",
            "xpath://button[contains(normalize-space(.), '按住')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '按住')]",
            "xpath://*[contains(@class, 'button') and contains(normalize-space(.), '按住')]",
        ]

    def _page_level_press_surface(self, page):
        return self._scope_has_text(
            page,
            [
                "证明你不是机器人",
                "长按该按钮",
                "按住",
            ],
        )

    def _find_direct_press_target_by_js(self, owner):
        try:
            return owner.run_js(
                """() => {
                    const nodes = Array.from(document.querySelectorAll('button, [role="button"], div, span'));
                    const viewportWidth = window.innerWidth || 0;
                    const candidates = [];
                    for (const el of nodes) {
                        const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                        if (!text || text.length > 8) continue;
                        if (!(text === '按住' || text === '长按' || text.includes('按住'))) continue;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                        if (rect.width < 120 || rect.width > 340) continue;
                        if (rect.height < 32 || rect.height > 90) continue;
                        if (rect.x < 0 || rect.y < 0) continue;
                        const centerX = rect.x + rect.width / 2;
                        const centerY = rect.y + rect.height / 2;
                        const distanceToViewportCenter = Math.abs(centerX - viewportWidth / 2);
                        const className = typeof el.className === 'string' ? el.className : '';
                        let score = 0;
                        if (text === '按住') score += 400;
                        else if (text === '长按') score += 320;
                        else score += 220;
                        if (className.toLowerCase().includes('button')) score += 80;
                        score += Math.min(rect.width * rect.height, 25000) / 100;
                        score += Math.max(0, centerY);
                        score -= distanceToViewportCenter / 5;
                        candidates.push({
                            kind: 'press',
                            summary: `${text} [direct-js]`,
                            text,
                            x: Math.round(centerX),
                            y: Math.round(centerY),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            score,
                        });
                    }
                    candidates.sort((a, b) => b.score - a.score);
                    return candidates[0] || null;
                }""",
                as_expr=False,
            )
        except Exception:
            return None

    def _find_bottom_press_target_by_js(self, owner):
        try:
            return owner.run_js(
                """() => {
                    const nodes = Array.from(document.querySelectorAll('button, [role="button"], div, span'));
                    const viewportWidth = window.innerWidth || 0;
                    const viewportHeight = window.innerHeight || 0;
                    const candidates = [];
                    for (const el of nodes) {
                        const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                        if (rect.width < 120 || rect.width > 340) continue;
                        if (rect.height < 32 || rect.height > 90) continue;
                        if (rect.x < 0 || rect.y < 0) continue;
                        const centerX = rect.x + rect.width / 2;
                        const centerY = rect.y + rect.height / 2;
                        if (centerY < viewportHeight * 0.65) continue;
                        const className = typeof el.className === 'string' ? el.className : '';
                        let score = 0;
                        if (text === '按住') score += 500;
                        else if (text.includes('按住')) score += 300;
                        if (className.toLowerCase().includes('button')) score += 120;
                        score += rect.width;
                        score -= Math.abs(centerX - viewportWidth / 2) / 4;
                        candidates.push({
                            kind: 'press',
                            summary: `${text || '[bottom-press-target]'} [bottom-js]`,
                            text,
                            x: Math.round(centerX),
                            y: Math.round(centerY),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            score,
                        });
                    }
                    candidates.sort((a, b) => b.score - a.score);
                    return candidates[0] || null;
                }""",
                as_expr=False,
            )
        except Exception:
            return None

    def _find_bottom_button_shape_target_by_js(self, owner):
        try:
            return owner.run_js(
                """() => {
                    const viewportWidth = window.innerWidth || 0;
                    const viewportHeight = window.innerHeight || 0;
                    const nodes = Array.from(document.querySelectorAll('button, [role="button"], div, span, a'));
                    const candidates = [];
                    for (const el of nodes) {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                        if (rect.width < 150 || rect.width > 340) continue;
                        if (rect.height < 36 || rect.height > 90) continue;
                        if (rect.x < 0 || rect.y < 0) continue;
                        const centerX = rect.x + rect.width / 2;
                        const centerY = rect.y + rect.height / 2;
                        if (centerY < viewportHeight * 0.68 || centerY > viewportHeight * 0.92) continue;
                        const distanceToViewportCenter = Math.abs(centerX - viewportWidth / 2);
                        if (distanceToViewportCenter > viewportWidth * 0.22) continue;

                        const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                        const className = typeof el.className === 'string' ? el.className.toLowerCase() : '';
                        const radius = parseFloat(style.borderRadius || '0') || 0;
                        const bg = style.backgroundColor || '';
                        const borderTop = style.borderTopColor || '';
                        const borderWidth = parseFloat(style.borderTopWidth || '0') || 0;

                        let score = 0;
                        if (text === '按住') score += 600;
                        else if (text.includes('按住')) score += 350;
                        else if (text === '长按') score += 300;
                        if (className.includes('button')) score += 120;
                        if (radius >= 12) score += 80;
                        if (bg.includes('255') || bg.includes('rgb(255')) score += 90;
                        if (borderWidth >= 1) score += 50;
                        if (borderTop.includes('0, 120, 212') || borderTop.includes('0,120,212')) score += 40;
                        score += Math.min(rect.width * rect.height, 25000) / 100;
                        score += centerY / 2;
                        score -= distanceToViewportCenter / 3;

                        candidates.push({
                            kind: 'press',
                            summary: `${text || '[button-shape-target]'} [shape-js]`,
                            text,
                            x: Math.round(centerX),
                            y: Math.round(centerY),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            score,
                        });
                    }

                    candidates.sort((a, b) => b.score - a.score);
                    return candidates[0] || null;
                }""",
                as_expr=False,
            )
        except Exception:
            return None

    def _page_level_press_point_target(self, page):
        viewport_width, viewport_height = self._ensure_viewport(page)
        if viewport_width <= 0 or viewport_height <= 0:
            return None

        return {
            "kind": "press",
            "summary": "page-bottom-fallback [point]",
            "x": int(viewport_width * 0.5),
            "y": int(viewport_height * 0.80),
        }

    def _find_press_point_from_prompt_by_js(self, owner):
        try:
            return owner.run_js(
                """() => {
                    const viewportWidth = window.innerWidth || 0;
                    const viewportHeight = window.innerHeight || 0;
                    const texts = ['长按该按钮。', '长按该按钮', '证明你不是机器人'];
                    const nodes = Array.from(document.querySelectorAll('div, p, span, h1, h2, h3'));
                    for (const text of texts) {
                        for (const el of nodes) {
                            const raw = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                            if (!raw || !raw.includes(text)) continue;
                            const rect = el.getBoundingClientRect();
                            if (rect.width <= 0 || rect.height <= 0) continue;
                            const x = Math.round(rect.x + rect.width / 2);
                            let y = Math.round(rect.y + rect.height + viewportHeight * 0.085);
                            if (text.includes('证明你不是机器人')) {
                                y = Math.round(rect.y + rect.height + viewportHeight * 0.33);
                            }
                            y = Math.max(1, Math.min(y, Math.round(viewportHeight * 0.88)));
                            return {
                                kind: 'press',
                                summary: `${text} [prompt-point]`,
                                x,
                                y,
                            };
                        }
                    }
                    return null;
                }""",
                as_expr=False,
            )
        except Exception:
            return None

    def _press_target_variants(self, page, target):
        if not isinstance(target, dict) or target.get("element"):
            return [target]

        base_point = self._target_point(page, target)
        if not base_point:
            return [target]

        viewport_width, viewport_height = self._ensure_viewport(page)
        offsets = [
            (0, -24),
            (0, -12),
            (0, 0),
            (-28, -12),
            (28, -12),
            (0, 12),
        ]
        variants = []
        seen = set()
        for dx, dy in offsets:
            x = max(1, min(base_point["x"] + dx, viewport_width - 1))
            y = max(1, min(base_point["y"] + dy, viewport_height - 1))
            key = (x, y)
            if key in seen:
                continue
            seen.add(key)
            variants.append(
                {
                    "kind": target.get("kind", "press"),
                    "summary": f'{target.get("summary", "point-target")} @({x},{y})',
                    "x": x,
                    "y": y,
                }
            )
        return variants or [target]

    def _wait_for_page_press_target(self, owner, timeout=6):
        end_time = time.time() + timeout
        while time.time() < end_time:
            direct_js_target = self._find_direct_press_target_by_js(owner)
            if direct_js_target:
                return direct_js_target

            bottom_js_target = self._find_bottom_press_target_by_js(owner)
            if bottom_js_target:
                return bottom_js_target

            button_shape_target = self._find_bottom_button_shape_target_by_js(owner)
            if button_shape_target:
                return button_shape_target

            direct_page_target = self._best_visible_candidate(
                owner,
                self._fast_press_button_locators(),
                timeout=0.1,
            )
            wrapped_target = self._wrap_target(direct_page_target, "press")
            if wrapped_target:
                return wrapped_target

            if self.mailbox_url_ready(owner):
                return None
            owner.wait(0.15)

        return None

    def _is_stale_context_error(self, error):
        text = str(error or "").lower()
        return (
            "no such frame" in text
            or "browsing context" in text
            or "not found" in text and "context" in text
        )

    def _visible_candidate(self, owner, locators, timeout=5):
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
                        if width < 20 or height < 20:
                            continue
                        x, y = element.rect.viewport_midpoint
                        if x <= 0 or y <= 0:
                            continue
                        return element
                    except Exception:
                        continue
            owner.wait(0.2)
        return False

    def _best_visible_candidate(self, owner, locators, timeout=0.5):
        end_time = time.time() + timeout
        while time.time() < end_time:
            candidates = []
            for locator in locators:
                try:
                    elements = owner.eles(locator, timeout=0.15)
                except Exception:
                    elements = []

                for element in elements:
                    try:
                        if not element or not element.is_displayed:
                            continue
                        size = element.size or {}
                        width = int(size.get("width", 0) or 0)
                        height = int(size.get("height", 0) or 0)
                        if width < 40 or height < 24:
                            continue
                        x, y = element.rect.viewport_midpoint
                        if x <= 0 or y <= 0:
                            continue
                        text = self._element_summary_text(element)
                        normalized_text = " ".join(str(text).split())
                        if len(normalized_text) > 48:
                            continue
                        if any(
                            keyword in normalized_text
                            for keyword in ("证明你不是机器人", "长按该按钮", "@hotmail.com", "@outlook.com")
                        ):
                            continue
                        if width > 420 or height > 120:
                            continue
                        score = 0
                        if normalized_text == "按住":
                            score += 300
                        elif normalized_text == "长按":
                            score += 260
                        elif "按住" in normalized_text:
                            score += 180
                        elif "长按" in normalized_text:
                            score += 150
                        score += min(width * height, 12000) / 100.0
                        score += y / 10.0
                        candidates.append((score, element))
                    except Exception:
                        continue

            if candidates:
                candidates.sort(key=lambda item: item[0], reverse=True)
                return candidates[0][1]
            owner.wait(0.1)
        return False

    def _wrap_target(self, element, kind):
        if not element:
            return None
        return {
            "kind": kind,
            "element": element,
            "summary": self._element_summary_text(element),
        }

    def _log_captcha_branch(self, branch, target):
        if not self.action_visual or not target:
            return

        summary = str(target.get("summary") or "").replace("\n", " ").strip()
        if len(summary) > 160:
            summary = summary[:160] + "..."
        print(f"[Debug: Captcha] - branch={branch}; summary={summary}")

    def _post_press_click_locators(self):
        return [
            "css:[aria-label='再次按下']",
            "xpath://*[@aria-label='再次按下']",
            "xpath://button[contains(normalize-space(.), '再次按下')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '再次按下')]",
            "xpath://button[contains(normalize-space(.), '再点一次')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '再点一次')]",
            "xpath://button[contains(normalize-space(.), '再按一次')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '再按一次')]",
            "xpath://button[contains(normalize-space(.), '点击一次')]",
            "xpath://*[@role='button'][contains(normalize-space(.), '点击一次')]",
            "xpath://button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click again')]",
            "xpath://*[@role='button'][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'click again')]",
            "xpath://button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'try again')]",
            "xpath://*[@role='button'][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'try again')]",
        ]

    def _post_press_release_hints(self):
        return [
            "再次按下",
            "再点一次",
            "再按一次",
            "点击一次",
            "click again",
            "Click again",
            "try again",
            "Try again",
            "retry",
            "Retry",
        ]

    def _element_summary_text(self, element):
        parts = []
        for attr_name in ("text", "value"):
            try:
                parts.append(str(getattr(element, attr_name) or ""))
            except Exception:
                pass
        for attr_name in ("aria-label", "title", "xml-roles", "id", "class"):
            try:
                parts.append(str(element.attr(attr_name) or ""))
            except Exception:
                pass
        for attr_name in ("html", "inner_html"):
            try:
                parts.append(str(getattr(element, attr_name) or ""))
            except Exception:
                pass
        return " ".join(parts)

    def _first_match(self, owner, locators, timeout=5):
        end_time = time.time() + timeout
        while time.time() < end_time:
            for locator in locators:
                try:
                    element = owner.ele(locator, timeout=0.2)
                except Exception:
                    element = False
                if element:
                    return element
            owner.wait(0.2)
        return False

    def _click_first(self, owner, locators, timeout=3, optional=False):
        element = self._first_match(owner, locators, timeout=timeout)
        if not element:
            if optional:
                return False
            raise TimeoutError(f"captcha step element not found: {locators}")

        try:
            element.click()
            return True
        except Exception as e:
            if optional:
                return False
            raise TimeoutError(f"captcha step click failed: {e}")

    def _classify_challenge_summary(self, summary):
        if not summary:
            return None

        blocked_keywords = [
            "帮助",
            "反馈",
            "使用条款",
            "隐私",
            "Cookie",
            "专用浏览",
        ]
        if any(keyword in summary for keyword in blocked_keywords):
            return None

        target_keywords = [
            "按住",
            "长按",
            "按下",
            "挑战",
            "机器人",
            "Press and hold",
            "Press & Hold",
            "Human Challenge",
            "requires verification",
            "px-captcha",
        ]
        if any(keyword in summary for keyword in target_keywords):
            return "press"

        click_keywords = [
            "点击",
            "单击",
            "验证",
            "verify",
            "Verify",
            "click to verify",
            "Click to verify",
            "click the button",
            "Click the button",
            "I am human",
            "i am human",
        ]
        if any(keyword in summary for keyword in click_keywords):
            return "click"

        return None

    def _actionable_element(self, owner, locators, timeout=5, expected_kind=None):
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
                        if width < 20 or height < 20:
                            continue
                        summary = self._element_summary_text(element)
                        kind = self._classify_challenge_summary(summary)
                        if not kind:
                            continue
                        if expected_kind and kind != expected_kind:
                            continue
                        x, y = element.rect.viewport_midpoint
                        if x <= 0 or y <= 0:
                            continue
                        return {
                            "kind": kind,
                            "element": element,
                            "summary": summary,
                        }
                    except Exception:
                        continue
            owner.wait(0.2)
        return False

    def _press_fallback_target(self, owner, timeout=1.0):
        locators = [
            "css:#px-captcha",
            "css:div#px-captcha",
            "xpath://*[@id='px-captcha']",
            "css:[data-testid*='captcha' i]",
            "css:[id*='captcha' i]",
        ]
        element = self._visible_candidate(owner, locators, timeout=timeout)
        return self._wrap_target(element, "press")

    def _post_press_click_target(self, owner, timeout=0.5):
        element = self._visible_candidate(
            owner, self._post_press_click_locators(), timeout=timeout
        )
        return self._wrap_target(element, "click")

    def _summary_has_post_press_hint(self, summary):
        if not summary:
            return False
        return any(keyword in summary for keyword in self._post_press_release_hints())

    def _challenge_active(self, page):
        return bool(
            self.visible_locator_exists(
                page,
                [
                    "css:iframe#enforcementFrame",
                    "css:iframe[src*='arkoselabs']",
                    "css:iframe[src*='funcaptcha']",
                ],
                timeout=0.3,
                min_size=20,
            )
            or self.text_exists(page, "证明你不是机器人")
            or self.text_exists(page, "长按该按钮")
            or self.text_exists(page, "点击以验证")
            or self.text_exists(page, "单击以验证")
            or self.text_exists(page, "可访问性挑战")
            or self.text_exists(page, "再次按下")
            or self.text_exists(page, "Click to verify")
            or self.text_exists(page, "Verify you are human")
        )

    def _ensure_viewport(self, page):
        try:
            width, height = page.rect.viewport_size
        except Exception:
            width, height = 0, 0

        if width > 0 and height > 0:
            return width, height

        try:
            page.set_viewport(1366, 900)
            page.wait(0.2)
            return page.rect.viewport_size
        except Exception:
            return 0, 0

    def _target_point(self, page, target):
        viewport_width, viewport_height = self._ensure_viewport(page)
        if viewport_width <= 0 or viewport_height <= 0:
            return None

        x = y = None
        element = None if not isinstance(target, dict) else target.get("element")

        if element:
            try:
                x, y = element.rect.viewport_midpoint
            except Exception:
                x = y = None

        if x is None or y is None:
            try:
                x = int(target["x"])
                y = int(target["y"])
            except Exception:
                return None

        if x <= 0 or y <= 0 or x >= viewport_width or y >= viewport_height:
            return None

        return {
            "x": max(1, min(int(x + random.randint(-3, 3)), viewport_width - 1)),
            "y": max(1, min(int(y + random.randint(-3, 3)), viewport_height - 1)),
        }

    def _find_challenge_target_by_js(self, owner, expected_kind=None):
        try:
            return owner.run_js(
                """() => {
                    const pressKeywords = ['按住', '长按', 'Press and hold', 'press and hold', 'Press & Hold', 'px-captcha'];
                    const clickKeywords = ['点击', '单击', '验证', 'Click to verify', 'click to verify', 'Verify you are human', 'verify you are human', 'I am human', 'i am human'];
                    const blockedKeywords = ['帮助', '反馈', '使用条款', '隐私', 'Cookie', '专用浏览'];
                    const nodes = Array.from(document.querySelectorAll('button, [role="button"], [xml-roles="button"], div, a, span'));
                    const candidates = [];
                    for (const el of nodes) {
                        const text = ((el.innerText || '') + ' ' + (el.getAttribute('aria-label') || '') + ' ' + (el.getAttribute('title') || '')).trim();
                        if (!text) continue;
                        if (blockedKeywords.some(k => text.includes(k))) continue;
                        let kind = null;
                        if (pressKeywords.some(k => text.includes(k))) kind = 'press';
                        else if (clickKeywords.some(k => text.includes(k))) kind = 'click';
                        if (!kind) continue;
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                        if (rect.width < 20 || rect.height < 20) continue;
                        if (rect.x < 0 || rect.y < 0) continue;
                        candidates.push({
                            kind,
                            text,
                            x: Math.round(rect.x + rect.width / 2),
                            y: Math.round(rect.y + rect.height / 2),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                        });
                    }
                    const expectedKind = window.__ruyiExpectedChallengeKind || null;
                    const filtered = expectedKind ? candidates.filter(item => item.kind === expectedKind) : candidates;
                    const pool = filtered.length ? filtered : candidates;
                    pool.sort((a, b) => (b.width * b.height) - (a.width * a.height));
                    return pool[0] || null;
                }""",
                as_expr=False,
            )
        except Exception:
            return None

    def _find_challenge_target(self, owner, timeout=5, expected_kind=None):
        if owner is not None and expected_kind == "press" and self._page_level_press_surface(owner):
            page_press_target = self._wait_for_page_press_target(
                owner, timeout=max(1.2, min(timeout, 6))
            )
            if page_press_target:
                return page_press_target
            prompt_point_target = self._find_press_point_from_prompt_by_js(owner)
            if prompt_point_target:
                return prompt_point_target
            return self._page_level_press_point_target(owner)

        target = self._actionable_element(
            owner,
            self._challenge_target_locators(),
            timeout=timeout,
            expected_kind=expected_kind,
        )
        if target:
            return target

        prefer_press = expected_kind == "press" and self._scope_prefers_press(owner)
        if expected_kind == "press":
            direct_button_target = self._best_visible_candidate(
                owner,
                self._fast_press_button_locators(),
                timeout=min(timeout, 0.2),
            )
            wrapped_button_target = self._wrap_target(direct_button_target, "press")
            if wrapped_button_target:
                return wrapped_button_target

            fallback_target = self._press_fallback_target(owner, timeout=min(timeout, 0.4))
            if fallback_target:
                return fallback_target
        if prefer_press:
            generic_press_target = self._visible_candidate(
                owner, self._challenge_click_locators(), timeout=min(timeout, 2)
            )
            wrapped_target = self._wrap_target(generic_press_target, "press")
            if wrapped_target:
                return wrapped_target

        try:
            owner.run_js(
                f"window.__ruyiExpectedChallengeKind = {json.dumps(expected_kind)};",
                as_expr=True,
            )
        except Exception:
            pass

        target = self._find_challenge_target_by_js(owner, expected_kind=expected_kind)
        if not target:
            return None
        if prefer_press and target.get("kind") == "click":
            target["kind"] = "press"
        if expected_kind and target.get("kind") != expected_kind:
            return None
        return target

    def _perform_press(self, owner, page, challenge_target):
        press_point = self._target_point(page, challenge_target)
        if not press_point:
            raise TimeoutError("captcha button has no valid viewport point")

        owner.actions.move_to(
            press_point,
            duration=random.randint(120, 240),
        ).hold().perform()
        return press_point

    def _release_press(self, owner):
        try:
            owner.actions.release().perform()
        except Exception:
            try:
                owner.actions.release_all()
            except Exception:
                pass

    def _perform_click(self, owner, page, challenge_target):
        click_point = self._target_point(page, challenge_target)
        if not click_point:
            raise TimeoutError("captcha click target has no valid viewport point")

        owner.actions.move_to(
            click_point,
            duration=random.randint(120, 240),
        ).click().perform()

    def _perform_press_at_point(self, owner, point, hold_seconds):
        owner.actions.move_to(
            {"x": int(point["x"]), "y": int(point["y"])},
            duration=random.randint(120, 240),
        ).hold().wait(hold_seconds).release().perform()

    def _wait_for_post_press_transition(self, owner, page, timeout=20):
        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.mailbox_url_ready(page):
                return {"status": "completed"}
            if not self._challenge_active(page):
                return {"status": "completed"}

            try:
                click_target = self._post_press_click_target(owner, timeout=0.15)
            except Exception as e:
                if self.mailbox_url_ready(page) or self._is_stale_context_error(e):
                    return {"status": "completed"}
                raise
            if click_target:
                return {"status": "followup_click", "target": click_target}

            try:
                challenge_target = self._find_challenge_target(
                    owner, timeout=0.15, expected_kind="press"
                )
            except Exception as e:
                if self.mailbox_url_ready(page) or self._is_stale_context_error(e):
                    return {"status": "completed"}
                raise
            if challenge_target and self._summary_has_post_press_hint(
                challenge_target.get("summary")
            ):
                return {"status": "followup_click", "target": challenge_target}

            try:
                if self._scope_has_text(owner, self._post_press_release_hints()):
                    return {"status": "release_only"}
            except Exception as e:
                if self.mailbox_url_ready(page) or self._is_stale_context_error(e):
                    return {"status": "completed"}
                raise

            page.wait(0.2)

        return {"status": "timeout"}

    def _resolve_transition_result(self, owner, page, transition):
        page.wait(0.25)

        if transition["status"] == "completed":
            return True

        if transition["status"] == "followup_click":
            self.human_pause(page, 0.12, 0.25)
            self._perform_click(owner, page, transition["target"])
            page.wait(1.2)
            return not self._challenge_active(page)

        if transition["status"] == "release_only":
            page.wait(0.8)
            return not self._challenge_active(page)

        return False

    def _perform_press_until_transition(self, owner, page, challenge_target):
        candidate_targets = self._press_target_variants(page, challenge_target)
        is_point_target = not (
            isinstance(challenge_target, dict) and challenge_target.get("element")
        )

        for index, candidate_target in enumerate(candidate_targets):
            self._perform_press(owner, page, candidate_target)
            try:
                wait_timeout = 7 if is_point_target else 20
                transition = self._wait_for_post_press_transition(
                    owner, page, timeout=wait_timeout
                )
            finally:
                self._release_press(owner)

            result = self._resolve_transition_result(owner, page, transition)
            if result:
                return True

            if transition["status"] != "timeout":
                return False

            if index < len(candidate_targets) - 1:
                page.wait(0.2)

        return False

    def _handle_click_challenge(self, owner, page):
        challenge_target = self._find_challenge_target(
            owner, timeout=1.2, expected_kind="click"
        )
        if not challenge_target:
            return None

        self._log_captcha_branch("click", challenge_target)
        for _ in range(self.max_captcha_retries + 1):
            self.human_pause(page, 0.2, 0.5)
            try:
                self._perform_click(owner, page, challenge_target)
            except Exception:
                challenge_target = self._find_challenge_target(
                    owner, timeout=1.0, expected_kind="click"
                )
                if not challenge_target:
                    return None
                continue
            page.wait(1.8)
            if not self._challenge_active(page):
                return True
            challenge_target = self._find_challenge_target(
                owner, timeout=1.0, expected_kind="click"
            )
            if not challenge_target:
                return not self._challenge_active(page)
        return False

    def _handle_press_challenge(self, owner, page):
        challenge_target = self._find_challenge_target(
            owner, timeout=1.5, expected_kind="press"
        )
        if not challenge_target:
            return None

        self._log_captcha_branch("press", challenge_target)
        for _ in range(self.max_captcha_retries + 1):
            self.human_pause(page, 0.2, 0.5)
            try:
                result = self._perform_press_until_transition(
                    owner, page, challenge_target
                )
            except Exception as e:
                if self.mailbox_url_ready(page) or self._is_stale_context_error(e):
                    return True
                self._release_press(owner)
                challenge_target = self._find_challenge_target(
                    owner, timeout=1.0, expected_kind="press"
                )
                if not challenge_target:
                    return None
                continue
            if result:
                return True
            challenge_target = self._find_challenge_target(
                owner, timeout=1.0, expected_kind="press"
            )
            if not challenge_target:
                return not self._challenge_active(page)
        return False

    def _challenge_scopes(self, page):
        scopes = []
        seen = set()

        def add_scope(scope):
            if not scope:
                return
            scope_id = id(scope)
            if scope_id in seen:
                return
            seen.add(scope_id)
            scopes.append(scope)

        outer_frame = self._find_captcha_frame(page)
        add_scope(outer_frame)

        if outer_frame:
            add_scope(self._find_challenge_frame(outer_frame))
            for scope in self._iter_scopes(outer_frame):
                add_scope(scope)

        for scope in self._iter_scopes(page):
            add_scope(scope)

        return scopes

    def _priority_challenge_scopes(self, page):
        scopes = []
        seen = set()

        def add_scope(scope):
            if not scope:
                return
            scope_id = id(scope)
            if scope_id in seen:
                return
            seen.add(scope_id)
            scopes.append(scope)

        outer_frame = self._find_captcha_frame(page)
        inner_frame = self._find_challenge_frame(outer_frame) if outer_frame else None

        add_scope(page)
        add_scope(inner_frame)
        add_scope(outer_frame)
        return scopes

    def _recorded_captcha_flow(self, page):
        challenge_link_locators = [
            "css:a[aria-label='Accessible challenge']",
            "xpath://a[contains(@aria-label, 'Accessible challenge')]",
            "xpath://a[contains(normalize-space(.), 'Human Challenge requires verification')]",
        ]
        completed_locators = [
            "css:div[aria-label='Human Challenge completed, please wait']",
            "xpath://*[@aria-label='Human Challenge completed, please wait']",
            "xpath://*[contains(normalize-space(.), 'Human Challenge completed')]",
        ]
        scope_22 = self._resolve_frame_path(page, [2, 2])
        if scope_22:
            clicked = self._click_first(
                scope_22, challenge_link_locators, timeout=0.35, optional=True
            )
            if clicked:
                page.wait(0.25)
                if not self._challenge_active(page):
                    return True
                self._click_first(scope_22, completed_locators, timeout=0.25, optional=True)
                page.wait(0.2)

        scope_23 = self._resolve_frame_path(page, [2, 3])
        if scope_23:
            clicked = self._click_first(
                scope_23, challenge_link_locators, timeout=0.35, optional=True
            )
            if clicked:
                page.wait(0.3)
                if not self._challenge_active(page):
                    return True
                try:
                    page.wait.url_contains("/ppsecure/post.srf", timeout=1.5)
                    return True
                except Exception:
                    pass

        # Secondary pass: recursively scan every frame for the same recorded selectors.
        for scope in self._iter_scopes(page):
            clicked = self._click_first(
                scope,
                challenge_link_locators + completed_locators,
                timeout=0.1,
                optional=True,
            )
            if clicked:
                page.wait(0.2)
                if not self._challenge_active(page):
                    return True

        return None

    def _wait_for_frame(self, owner, locator, timeout=15, poll=0.25):
        """
        ruyipage 的 page.get_frame() 是即时查询，不会像 patchright 的 frame_locator
        那样自动等待。这里做一个轮询，直到 iframe 出现或超时。
        """
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                frame = owner.get_frame(locator)
            except Exception:
                frame = None
            if frame:
                return frame
            try:
                owner.wait(poll)
            except Exception:
                time.sleep(poll)
        return None

    def _find_captcha_button_in_scopes(self, page, label, timeout=8):
        """
        递归遍历 page 与所有 frame，找到匹配 aria-label 的按钮。
        不依赖固定 iframe 路径，只要按钮被渲染出来就能找到，
        从而绕开 iframe[style*="display: block"] 这种脆弱选择器。
        返回 (scope, button) 或 (None, None)。
        """
        locator = f'css:[aria-label="{label}"]'
        end_time = time.time() + timeout
        while time.time() < end_time:
            try:
                scopes = list(self._iter_scopes(page))
            except Exception:
                scopes = [page]

            for scope in scopes:
                try:
                    btn = scope.ele(locator, timeout=0.15)
                except Exception:
                    btn = None
                if not btn:
                    continue
                try:
                    if not btn.states.is_displayed:
                        continue
                except Exception:
                    pass
                try:
                    x, y = btn.rect.viewport_midpoint
                    if not x or not y or x <= 0 or y <= 0:
                        continue
                except Exception:
                    continue
                return scope, btn

            try:
                page.wait(0.25)
            except Exception:
                time.sleep(0.25)
        return None, None

    def _click_captcha_button(self, scope, element, jitter_x=10, jitter_y=10):
        """
        点击挑战按钮：
        - 优先用 scope.actions.move_to(element)：让 ruyipage 自动处理 frame 偏移
          （对比之前用 page.actions.move_to({"x":..,"y":..}) 的坐标在 iframe 里是错的）
        - 失败再回退到 element.click() 这条 BiDi-trusted 路径
        """
        try:
            scope.actions.move_to(
                element,
                offset_x=random.randint(-jitter_x, jitter_x),
                offset_y=random.randint(-jitter_y, jitter_y),
                duration=random.randint(80, 180),
            ).click().perform()
            return True
        except Exception as e1:
            print(f"[Debug: Captcha] - actions.move_to(element) 点击失败，回退 element.click(): {e1}")
            try:
                element.click()
                return True
            except Exception as e2:
                print(f"[Debug: Captcha] - element.click() 也失败: {e2}")
                return False

    def handle_captcha(self, page):
        """
        处理验证码挑战 - 镜像 patchright 工作版本：
        1. 在所有 frame 中递归找 "可访问性挑战" 按钮（不再依赖具体 iframe 路径）
        2. 点击它，然后点击 "再次按下"
        3. 等待 .draw detach（验证通过的关键信号）
        4. 检查加载/风控/重试状态
        若按钮连续 3 次都未找到，则直接判定失败，由上层关闭浏览器、进入下一线程
        """
        print("[Info: Captcha] - 开始处理验证码...")

        # 连续未找到 "可访问性挑战" 的次数；达到阈值即直接失败
        not_found_streak = 0
        not_found_limit = 3

        try:
            for attempt in range(self.max_captcha_retries + 1):
                page.wait(0.3)

                # 1. 在所有 scope 中找 "可访问性挑战" 按钮
                scope, btn = self._find_captcha_button_in_scopes(
                    page, "可访问性挑战", timeout=12
                )
                if not btn:
                    if not self._challenge_active(page):
                        print("[Info: Captcha] - 未发现挑战按钮且无挑战状态，判定通过")
                        return True

                    not_found_streak += 1
                    print(
                        f"[Info: Captcha] - 第 {not_found_streak}/{not_found_limit} 次"
                        f"未找到 可访问性挑战 按钮"
                    )
                    if not_found_streak >= not_found_limit:
                        print(
                            "[Error: Captcha] - 连续 "
                            f"{not_found_limit} 次未找到挑战按钮，判定失败，"
                            "关闭浏览器并继续下一个线程"
                        )
                        return False
                    # 短暂等待后再尝试
                    page.wait(1.0)
                    continue

                # 找到按钮则重置未找到计数
                not_found_streak = 0

                # 2. 点击 "可访问性挑战"
                print("[Debug: Captcha] - 点击 [aria-label='可访问性挑战']")
                self._click_captcha_button(scope, btn, jitter_x=10, jitter_y=10)
                time.sleep(random.uniform(0.2, 0.45))

                # 3. 点击 "再次按下"（先在同 scope 找，找不到再全局递归）
                btn2 = None
                btn2_scope = scope
                try:
                    btn2 = scope.ele('css:[aria-label="再次按下"]', timeout=3)
                except Exception:
                    btn2 = None
                if not btn2:
                    btn2_scope, btn2 = self._find_captcha_button_in_scopes(
                        page, "再次按下", timeout=5
                    )
                if btn2:
                    print("[Debug: Captcha] - 点击 [aria-label='再次按下']")
                    self._click_captcha_button(
                        btn2_scope, btn2, jitter_x=20, jitter_y=13
                    )

                # 4. 等待 .draw 消失（patchright 的关键判定信号）
                try:
                    page.wait.ele_deleted('css:.draw', timeout=15)
                except Exception:
                    if self.text_exists(page, '取消'):
                        return True
                    print(f"[Info: Captcha] - 第 {attempt + 1} 次：.draw 未消失，继续重试")
                    continue

                # 5. 等加载/检查风控/检查是否仍有挑战
                try:
                    loading = page.ele(
                        'css:[role="status"][aria-label="正在加载..."]', timeout=5
                    )
                    if loading:
                        page.wait(8)

                    if self.error_text_detected(page):
                        print("[Error: Rate limit] - 正常通过验证码，但当前 IP 注册频率过快。")
                        return False

                    _, still = self._find_captcha_button_in_scopes(
                        page, "可访问性挑战", timeout=1
                    )
                    if still:
                        print(f"[Info: Captcha] - 第 {attempt + 1} 次未通过，继续重试")
                        continue
                    return True
                except Exception:
                    if self.text_exists(page, '取消'):
                        return True
                    continue

            print("[Error: Captcha] - 重试次数已达到上限，验证码处理失败。")
            return False

        except Exception as e:
            print(f"[Debug: Captcha] - 简易验证码处理逻辑出现异常: {e}")
            return False

    def _original_handle_captcha_logic(self, page):

        # 1. 如果检测到挑战，优先进行递归 iframe 扫描
        # 原有逻辑 handle_captcha 的核心就是从 outer_frame 开始进行多层级的遍历处理

        # 尝试查找验证码 iframe 并执行原有的复杂处理流程
        outer_frame = self._find_captcha_frame(page)

        # 即使没有找到明显的 outer_frame，也可以尝试直接在 page 上应用挑战逻辑
        # 很多情况下验证码是动态插入的，直接对页面元素应用逻辑可能更有效

        # 尝试运行原有的循环尝试处理逻辑
        for attempt in range(self.max_captcha_retries + 1):
            if self.mailbox_url_ready(page):
                return True

            # 优先处理范围 (Priority Scopes)
            priority_scopes = self._priority_challenge_scopes(page)
            for scope in priority_scopes:
                if self._handle_press_challenge(scope, page):
                    return True
                if self._handle_click_challenge(scope, page):
                    return True

            # 录制的固定流程
            if self._recorded_captcha_flow(page):
                return True

            # 遍历所有发现的挑战 scope
            for scope in self._challenge_scopes(page):
                if scope in priority_scopes:
                    continue
                if self._handle_press_challenge(scope, page):
                    return True
                if self._handle_click_challenge(scope, page):
                    return True

            if not self.challenge_active(page):
                return True

            print(f"[Info: Captcha] - 尝试第 {attempt+1} 次处理未果，继续尝试...")
            page.wait(1.0)

        print("[Error: Captcha] - 验证码处理流程均未成功。")
        return False
