"""TicketPlus 登入。已登入則不動作。"""

from __future__ import annotations

import logging
import time
from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver

from .base_page import BasePage

logger = logging.getLogger("ticketplus")


class LoginPage(BasePage):
    def __init__(self, driver: WebDriver, timeout: int = 8):
        super().__init__(driver, timeout)

    def has_login_form(self) -> bool:
        return bool(
            self.execute_js(
                """
                const pwd = document.querySelector('input[type="password"]');
                const mobile = document.querySelector(
                    'input[placeholder*="手機"], input[placeholder*="帳號"], input[type="tel"]'
                );
                return Boolean(pwd && mobile && pwd.offsetParent !== null);
                """
            )
        )

    def is_logged_in(self) -> bool:
        if super().is_logged_in():
            return True
        return bool(
            self.execute_js(
                """
                const body = document.body ? (document.body.innerText || '') : '';
                const hasLogout = body.includes('登出');
                const pwd = document.querySelector('input[type="password"]');
                return hasLogout && !(pwd && pwd.offsetParent !== null);
                """
            )
        )

    def open_login_form(self) -> bool:
        if self.has_login_form():
            return True
        opened = self.execute_js(
            """
            const nodes = Array.from(document.querySelectorAll('button, a, span, div'));
            const login = nodes.find((el) => {
                const text = (el.innerText || '').trim();
                if (text !== '登入' && text !== '會員登入') return false;
                return el.offsetParent !== null;
            });
            if (login) {
                login.click();
                return true;
            }
            const icon = document.querySelector('i.mdi-account');
            if (icon) {
                const btn = icon.closest('button') || icon;
                btn.click();
                return true;
            }
            return false;
            """
        )
        if opened:
            time.sleep(0.6)
        return bool(self.has_login_form())

    def fill_and_submit(self, mobile: str, password: str, country_code: str = "+886") -> bool:
        mobile = (mobile or "").strip()
        password = password or ""
        if not mobile or not password:
            return False
        result = self.execute_js(
            """
            function setValue(el, value) {
                if (!el) return;
                el.focus();
                const proto = window.HTMLInputElement.prototype;
                const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                if (desc && desc.set) desc.set.call(el, value);
                else el.value = value;
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }
            const country = arguments[0];
            const mobile = arguments[1];
            const password = arguments[2];
            const countryEl = document.querySelector('input[placeholder*="區碼"]');
            if (countryEl && country) setValue(countryEl, country);
            const mobileEl = document.querySelector(
                'input[placeholder*="手機"], input[placeholder*="帳號"], input[type="tel"]'
            );
            const pwdEl = document.querySelector('input[type="password"]');
            if (!mobileEl || !pwdEl) return false;
            setValue(mobileEl, mobile);
            setValue(pwdEl, password);
            const form = pwdEl.closest('form, .v-card, .v-dialog, .v-navigation-drawer') || document.body;
            const buttons = Array.from((form || document).querySelectorAll('button, .v-btn'));
            const submit = buttons.find((b) => {
                if (b.disabled || b.classList.contains('v-btn--disabled') || b.classList.contains('disabledBtn')) {
                    return false;
                }
                const text = (b.innerText || '').replace(/\\s+/g, '');
                return text === '登入' || text === '會員登入';
            });
            if (!submit) return false;
            submit.click();
            return true;
            """,
            country_code,
            mobile,
            password,
        )
        return bool(result)

    def wait_until_logged_in(self, timeout: float = 15.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.is_logged_in():
                return True
            time.sleep(0.4)
        return self.is_logged_in()
