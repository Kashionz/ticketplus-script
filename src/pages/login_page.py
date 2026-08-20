"""TicketPlus 登入。已登入則不動作。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict
from urllib.parse import urlparse

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from .base_page import BasePage
from ..utils.helpers import is_login_url, normalize_mobile

logger = logging.getLogger("ticket-helper")

LOGIN_ERROR_TEXTS = (
    "帳號或密碼錯誤",
    "密碼錯誤",
    "帳號不存在",
    "登入失敗",
    "驗證碼",
    "請輸入正確",
    "請填寫",
)


class LoginPage(BasePage):
    def __init__(self, driver: WebDriver, timeout: int = 8):
        super().__init__(driver, timeout)

    def has_login_form(self) -> bool:
        return bool(
            self.execute_js(
                """
                function visible(el) {
                    if (!el || el.disabled) return false;
                    if (el.closest('.v-select, .lang-select, header, #appBar, .mock-control')) return false;
                    const style = window.getComputedStyle(el);
                    const box = el.getBoundingClientRect();
                    if (style.visibility === 'hidden' || style.display === 'none') return false;
                    return box.width >= 2 && box.height >= 2;
                }
                const inputs = Array.from(document.querySelectorAll('input')).filter(visible);
                const pwd = inputs.find((el) => String(el.type || '').toLowerCase() === 'password');
                const mobile = inputs.find((el) => {
                    if (el === pwd) return false;
                    const t = String(el.type || '').toLowerCase();
                    const hint = ((el.placeholder || '') + (el.getAttribute('aria-label') || '') + (el.name || '')).toLowerCase();
                    if (t === 'tel') return true;
                    return /手機|帳號|mobile|phone|account/.test(hint);
                });
                return Boolean(pwd && (mobile || inputs.some((el) => el !== pwd && (el.type === 'text' || el.type === 'tel' || !el.type))));
                """
            )
        )

    def is_logged_in(self) -> bool:
        if self.has_login_form():
            return False
        if super().is_logged_in():
            return True
        return bool(
            self.execute_js(
                """
                const body = document.body ? (document.body.innerText || '') : '';
                const hasLogout = /登出|logout/i.test(body);
                const pwd = document.querySelector('input[type="password"]');
                return hasLogout && !(pwd && pwd.offsetParent !== null);
                """
            )
        )

    def login_error_text(self) -> str:
        text = self.page_text()
        for token in LOGIN_ERROR_TEXTS:
            if token in text:
                return token
        return ""

    def open_login_form(self) -> bool:
        if self.has_login_form():
            return True
        if is_login_url(self.current_url):
            self.wait_seconds(0.4)
            return self.has_login_form()

        opened = self.execute_js(
            """
            const nodes = Array.from(document.querySelectorAll('button, a, span'));
            const login = nodes.find((el) => {
                const text = (el.innerText || '').replace(/\\s+/g, '');
                if (text !== '會員登入') return false;
                return el.offsetParent !== null;
            });
            if (login) {
                login.click();
                return true;
            }
            const icon = document.querySelector('i.mdi-account, i.mdi-account-outline');
            if (icon) {
                const btn = icon.closest('button, a') || icon;
                btn.click();
                return true;
            }
            return false;
            """
        )
        if opened:
            self.wait_seconds(0.7)
            if self.has_login_form():
                return True
        return self._goto_login_page()

    def _goto_login_page(self) -> bool:
        parsed = urlparse(self.current_url)
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else self.BASE_URL
        query = f"?{parsed.query}" if parsed.query else ""
        target = f"{origin}/login{query}"
        if not is_login_url(self.current_url):
            logger.info("改走登入頁: %s", target)
            self.navigate_to(target)
        self.wait_seconds(0.6)
        return self.has_login_form()

    def _find_fields(self) -> Dict[str, Any]:
        result = self.execute_js(
            """
            function visible(el) {
                if (!el) return false;
                if (el.closest('.v-select, .lang-select, header, #appBar, .mock-control')) return false;
                const style = window.getComputedStyle(el);
                const box = el.getBoundingClientRect();
                if (style.visibility === 'hidden' || style.display === 'none') return false;
                return box.width >= 2 && box.height >= 2;
            }
            const inputs = Array.from(document.querySelectorAll('input')).filter(visible);
            const pwd = inputs.find((el) => String(el.type || '').toLowerCase() === 'password');
            let mobile = inputs.find((el) => {
                if (el === pwd) return false;
                const t = String(el.type || '').toLowerCase();
                const hint = ((el.placeholder || '') + (el.getAttribute('aria-label') || '') + (el.name || '')).toLowerCase();
                if (t === 'tel') return true;
                return /手機|帳號|mobile|phone|account/.test(hint);
            });
            if (!mobile) {
                mobile = inputs.find((el) => el !== pwd && ['text', 'tel', 'number', ''].includes(String(el.type || '').toLowerCase()));
            }
            const root = (pwd && (pwd.closest('form, .v-card, .v-dialog, .login-card') || document.body)) || document.body;
            const buttons = Array.from(root.querySelectorAll('button, .v-btn'));
            const submit = buttons.find((b) => {
                const text = (b.innerText || '').replace(/\\s+/g, '');
                return text === '登入' || text === '會員登入';
            });
            if (mobile) mobile.setAttribute('data-tp-mobile', '1');
            if (pwd) pwd.setAttribute('data-tp-password', '1');
            if (submit) submit.setAttribute('data-tp-login-submit', '1');
            return {
                mobile: Boolean(mobile),
                password: Boolean(pwd),
                submit: Boolean(submit),
                submitDisabled: Boolean(submit && (submit.disabled || submit.classList.contains('v-btn--disabled') || submit.classList.contains('disabledBtn'))),
            };
            """
        )
        return result if isinstance(result, dict) else {}

    def _type_into(self, selector: str, value: str) -> bool:
        try:
            el = self.driver.find_element("css selector", selector)
        except Exception:
            return False
        try:
            el.click()
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            el.send_keys(value)
            return True
        except Exception:
            return bool(
                self.execute_js(
                    """
                    const el = document.querySelector(arguments[0]);
                    const value = arguments[1];
                    if (!el) return false;
                    el.focus();
                    const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                    if (desc && desc.set) desc.set.call(el, value);
                    else el.value = value;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                    """,
                    selector,
                    value,
                )
            )

    def fill_and_submit(self, mobile: str, password: str, country_code: str = "+886") -> bool:
        mobile = normalize_mobile(mobile, country_code)
        password = password or ""
        if not mobile or not password:
            return False
        if not self.has_login_form() and not self.open_login_form():
            return False
        fields = self._find_fields()
        if not fields.get("mobile") or not fields.get("password"):
            logger.debug("登入欄位還沒出現: %s", fields)
            return False
        typed_mobile = self._type_into('input[data-tp-mobile="1"]', mobile)
        typed_pwd = self._type_into('input[data-tp-password="1"]', password)
        if not (typed_mobile and typed_pwd):
            return False
        self.wait_seconds(0.35)
        clicked = self.execute_js(
            """
            const btn = document.querySelector('[data-tp-login-submit="1"]')
                || Array.from(document.querySelectorAll('button, .v-btn')).find((b) => {
                    const text = (b.innerText || '').replace(/\\s+/g, '');
                    return text === '登入' || text === '會員登入';
                });
            if (!btn) return false;
            btn.disabled = false;
            btn.classList.remove('v-btn--disabled', 'disabledBtn');
            btn.click();
            return true;
            """
        )
        return bool(clicked)

    def wait_until_logged_in(self, timeout: float = 15.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_logged_in():
                return True
            if self.login_error_text():
                return False
            time.sleep(0.4)
        return self.is_logged_in()
