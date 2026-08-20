"""KKTIX 登入：Email／密碼。已登入則不動作。"""

from __future__ import annotations

import logging
from typing import Any, Dict

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver

from ...utils.helpers import is_kktix_login_url, is_mock_url
from ..base_page import BasePage

logger = logging.getLogger("ticket-helper")

_JS_VISIBLE = """
function visible(el) {
    if (!el) return false;
    if (el.hidden) return false;
    if (el.closest && el.closest('[hidden]')) return false;
    const style = window.getComputedStyle(el);
    const box = el.getBoundingClientRect();
    if (style.visibility === 'hidden' || style.display === 'none') return false;
    if (Number(style.opacity) === 0) return false;
    return box.width >= 2 && box.height >= 2;
}
"""


class KktixLoginPage(BasePage):
    def __init__(self, driver: WebDriver, timeout: int = 8):
        super().__init__(driver, timeout)

    def has_login_form(self) -> bool:
        return bool(
            self.execute_js(
                _JS_VISIBLE
                + """
                if (document.querySelector('#login-form') && visible(document.querySelector('#login-form'))) {
                    return true;
                }
                const inputs = Array.from(document.querySelectorAll('input')).filter(visible);
                const pwd = inputs.find((el) => String(el.type || '').toLowerCase() === 'password');
                const email = inputs.find((el) => {
                    if (el === pwd) return false;
                    const t = String(el.type || '').toLowerCase();
                    const hint = (
                        (el.placeholder || '') +
                        (el.getAttribute('aria-label') || '') +
                        (el.name || '') +
                        (el.id || '')
                    ).toLowerCase();
                    if (t === 'email') return true;
                    return /email|login|帳號|user/.test(hint);
                });
                return Boolean(pwd && email);
                """
            )
        )

    def is_logged_in(self) -> bool:
        if self._has_mock_user_cookie():
            return True
        if is_kktix_login_url(self.current_url) or self.has_login_form():
            return False
        if is_mock_url(self.current_url):
            return True
        return bool(
            self.execute_js(
                """
                const nav = document.querySelector('nav, header, .navbar, #nav, .account-menu') || document.body;
                const navText = nav ? (nav.innerText || '') : '';
                const body = document.body ? (document.body.innerText || '') : '';
                if (/我的票券/.test(navText) || /我的票券/.test(body)) return true;
                if (document.querySelector('.account-menu, a[href*="/account"], a[href*="/users/edit"]')) return true;
                if (/登出|logout/i.test(navText)) return true;
                return false;
                """
            )
        )

    def fill_and_submit(self, email: str, password: str) -> bool:
        email = (email or "").strip()
        password = password or ""
        if not email or not password:
            return False
        if not self.has_login_form():
            return False
        fields = self._mark_fields()
        if not fields.get("email") or not fields.get("password"):
            logger.debug("KKTIX 登入欄位還沒出現: %s", fields)
            return False
        typed_email = self._type_into('input[data-kktix-email="1"]', email)
        typed_pwd = self._type_into('input[data-kktix-password="1"]', password)
        if not (typed_email and typed_pwd):
            return False
        self.wait_seconds(0.2)
        clicked = self.execute_js(
            """
            const btn = document.querySelector('[data-kktix-login-submit="1"]')
                || document.querySelector('#login-form button[type="submit"], #login-form button, form button[type="submit"]');
            if (btn) {
                btn.disabled = false;
                btn.click();
                return true;
            }
            const form = document.querySelector('#login-form, form');
            if (form && form.requestSubmit) {
                form.requestSubmit();
                return true;
            }
            if (form) {
                form.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}));
                return true;
            }
            return false;
            """
        )
        if clicked:
            logger.info("已送出 KKTIX 登入")
        return bool(clicked)

    def _has_mock_user_cookie(self) -> bool:
        try:
            cookies = self.driver.get_cookies()
        except Exception:
            return False
        return any(cookie.get("name") == "mock_kktix_user" for cookie in cookies)

    def _mark_fields(self) -> Dict[str, Any]:
        result = self.execute_js(
            _JS_VISIBLE
            + """
            const root = document.querySelector('#login-form, form') || document.body;
            const inputs = Array.from(root.querySelectorAll('input')).filter(visible);
            const pwd = inputs.find((el) => String(el.type || '').toLowerCase() === 'password');
            let email = inputs.find((el) => {
                if (el === pwd) return false;
                const t = String(el.type || '').toLowerCase();
                const hint = (
                    (el.placeholder || '') +
                    (el.getAttribute('aria-label') || '') +
                    (el.name || '') +
                    (el.id || '')
                ).toLowerCase();
                if (t === 'email') return true;
                return /email|login|帳號|user/.test(hint);
            });
            if (!email) {
                email = inputs.find((el) => el !== pwd && ['text', 'email', ''].includes(String(el.type || '').toLowerCase()));
            }
            const buttons = Array.from(root.querySelectorAll('button, input[type="submit"], .btn'));
            const submit = buttons.find((b) => {
                const text = ((b.innerText || b.value || '')).replace(/\\s+/g, '');
                return text === '登入' || text === '會員登入' || String(b.type || '').toLowerCase() === 'submit';
            }) || buttons[0];
            if (email) email.setAttribute('data-kktix-email', '1');
            if (pwd) pwd.setAttribute('data-kktix-password', '1');
            if (submit) submit.setAttribute('data-kktix-login-submit', '1');
            return {
                email: Boolean(email),
                password: Boolean(pwd),
                submit: Boolean(submit),
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
