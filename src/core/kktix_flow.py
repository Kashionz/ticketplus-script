"""KKTIX 電腦配位主迴圈。不匯入 PyQt。"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse, urlunparse

from ..pages.kktix.checkout_page import KktixCheckoutPage
from ..pages.kktix.login_page import KktixLoginPage
from ..pages.kktix.registration_page import KktixRegistrationPage
from ..utils.helpers import (
    extract_kktix_slug,
    is_kktix_held_url,
    is_kktix_login_url,
    is_kktix_payment_url,
    is_kktix_registration_url,
    is_mock_url,
)
from .bot_engine import BotStep
from .kktix_select import pick_kktix_ticket

if TYPE_CHECKING:
    from .bot_engine import BotEngine

KKTIX_HOME = "https://kktix.com/"


def kktix_registration_url(activity_url: str) -> str:
    parsed = urlparse(activity_url or "")
    if is_kktix_registration_url(activity_url):
        return activity_url
    slug = extract_kktix_slug(activity_url)
    if not slug:
        return activity_url
    query = parsed.query
    if is_mock_url(activity_url):
        path = f"/events/{slug}/registrations/new"
        return urlunparse((parsed.scheme, parsed.netloc, path, "", query, ""))
    live = f"https://kktix.com/events/{slug}/registrations/new"
    return f"{live}?{query}" if query else live


class KktixFlow:
    def __init__(self, engine: "BotEngine"):
        self.engine = engine
        self._did_sale_refresh = False
        self._last_login_at = 0.0
        self._last_advance_url = ""
        self._last_advance_at = 0.0
        self._reg: Optional[KktixRegistrationPage] = None
        self._login: Optional[KktixLoginPage] = None
        self._checkout: Optional[KktixCheckoutPage] = None

    def run(self) -> bool:
        e = self.engine
        if not e._browser_still_open():
            return False
        assert e._browser and e._browser.driver
        driver = e._browser.driver
        self._reg = KktixRegistrationPage(driver)
        self._login = KktixLoginPage(driver)
        self._checkout = KktixCheckoutPage(driver)

        e._update_state(step=BotStep.NAVIGATE, message="開啟 KKTIX 購票頁")
        self._ensure_on_booking_page()
        if self._reg.detect_sale_state() == "on_sale":
            self._did_sale_refresh = True

        retries = 0
        while not e._should_stop() and retries < e.max_retries:
            if not e._browser_still_open():
                return False
            e._state.retry_count = retries
            url = self._reg.current_url

            if self._at_payment(url):
                e._log(f"已到達付款頁: {url}")
                return True

            if is_kktix_login_url(url) or self._login.has_login_form():
                self._handle_login()
                retries += 1
                continue

            if self._handle_human_gate():
                continue

            if self._reg.is_queue():
                e._update_state(step=BotStep.WAIT_QUEUE, message="查詢空位中，請勿重整")
                e._log_once("kktix-queue", "偵測到查詢空位中，停留等待官方放行，不會重新整理")
                e._sleep(1.0)
                continue

            if is_kktix_held_url(url):
                self._advance_held(url)
                e._sleep(0.8)
                retries += 1
                continue

            if is_kktix_registration_url(url):
                if self._process_registration():
                    e._sleep(0.8)
                retries += 1
                continue

            e._log(f"未預期的頁面: {url}，回到購票頁")
            self._reg.open(self._registration_url())
            e._sleep()
            retries += 1

        url = self._reg.current_url
        return self._at_payment(url)

    def _registration_url(self) -> str:
        return kktix_registration_url(self.engine.config.activity_url)

    def _ensure_on_booking_page(self) -> None:
        assert self._reg
        url = self._reg.current_url or ""
        if self._at_payment(url):
            return
        if is_kktix_held_url(url) or is_kktix_login_url(url) or is_kktix_registration_url(url):
            return
        self._reg.open(self._registration_url())

    def _at_payment(self, url: str) -> bool:
        assert self._checkout
        if is_kktix_payment_url(url):
            return True
        if is_kktix_registration_url(url) or is_kktix_login_url(url):
            return False
        return bool(self._checkout.has_card_field())

    def _handle_login(self) -> None:
        assert self._login and self._reg
        e = self.engine
        e._update_state(step=BotStep.WAIT_LOGIN, message="尚未登入，先完成登入")
        email = (e.config.account or "").strip()
        password = e.config.password or ""
        if not email or not password:
            e._log_once(
                "kktix-need-login",
                "尚未登入。請在瀏覽器登入 KKTIX，登入完成後會繼續，不會重刷頁面",
            )
            e._sleep(1.0)
            return

        now = time.time()
        if now - self._last_login_at >= 5:
            self._last_login_at = now
            e._log("偵測到未登入，正在自動登入")
            if self._login.has_recaptcha() and e.wait_for_human:
                e._log("登入出現驗證碼，請在瀏覽器完成")
                while not e._should_stop() and self._login.has_recaptcha():
                    e._sleep(0.5)
            if not self._login.fill_and_submit(email, password):
                e._log("自動填寫登入失敗，稍後再試或改手動登入", "WARNING")
            else:
                deadline = time.time() + 12
                while time.time() < deadline and not e._should_stop():
                    if self._login.is_logged_in() and not self._login.has_login_form():
                        e._log("自動登入成功")
                        if e.config.activity_url:
                            self._reg.open(self._registration_url())
                        return
                    e._sleep(0.4)

        e._log_once("kktix-wait-login", "停在登入頁等待登入完成，先不刷新購票頁")
        e._sleep(1.0)

    def _handle_human_gate(self) -> bool:
        assert self._reg
        e = self.engine
        recaptcha = self._reg.has_recaptcha()
        question = self._reg.has_question_captcha()
        if not recaptcha and not question:
            return False
        if not e.wait_for_human:
            e._log("出現驗證碼或活動問答，但 wait_for_human=false，稍後重試", "WARNING")
            e._sleep(1.0)
            return True
        e._update_state(step=BotStep.WAIT_HUMAN, message="請在瀏覽器完成驗證碼或問答")
        e._log("出現 reCAPTCHA 或活動問答，請在瀏覽器手動完成，完成後程式會繼續")
        while not e._should_stop() and (self._reg.has_recaptcha() or self._reg.has_question_captcha()):
            e._sleep(0.5)
        return True

    def _advance_held(self, url: str) -> None:
        assert self._checkout and self._reg
        e = self.engine
        e._update_state(step=BotStep.SUBMIT, message="已鎖票，往下一步")
        e._log_once("kktix-hold", "已鎖票，不再重選票種、不重整")
        now = time.time()
        if url == self._last_advance_url and now - self._last_advance_at < 2.5:
            return
        self._checkout.dismiss_seat_notice()
        if e.auto_agree:
            self._reg.agree_terms()
        if self._checkout.click_advance():
            self._last_advance_url = url
            self._last_advance_at = now

    def _process_registration(self) -> bool:
        assert self._reg
        e = self.engine
        cfg = e.config
        rows = self._reg.list_rows()
        pick = pick_kktix_ticket(
            rows,
            cfg.area_priorities,
            cfg.quantity,
            cfg.fallback_first_available,
            cfg.require_exact_quantity,
        )

        if pick.action == "wait_sale":
            self._wait_sale()
            return False

        if pick.action == "refresh":
            e._update_state(step=BotStep.SELECT_AREA, message="優先票種暫無票券，重整等待")
            e._log_once("kktix-refresh", "優先票種暫無票券，稍後整頁重整再選")
            e._sleep()
            self._safe_refresh()
            return False

        if pick.index is None or pick.quantity is None:
            e._sleep()
            return False

        if pick.action == "fallback":
            e._log_once("kktix-fallback", "優先票種沒票，改買第一個可購的非愛心票種")

        e._update_state(step=BotStep.SELECT_AREA, message="選擇票種 / 張數")
        if not self._reg.set_quantity(pick.index, pick.quantity):
            e._log("設定張數失敗，稍後再試")
            return False

        if self._reg.has_invitation_field():
            code = (cfg.exclusive_code or "").strip()
            if not code:
                e._log_once("kktix-need-code", "購票頁出現邀請碼欄，但設定未填序號")
                return False
            if not self._reg.fill_invitation(code):
                e._log_once("kktix-fill-code-fail", "找到邀請碼欄但填入失敗")
                return False

        if e.auto_agree:
            self._reg.agree_terms()

        e._update_state(step=BotStep.SUBMIT, message="送出電腦配位")
        if not self._reg.click_computer_assign():
            e._log("電腦配位 / 下一步尚未可按，稍後再試")
            return False
        return True

    def _wait_sale(self) -> None:
        assert self._reg
        e = self.engine
        e._update_state(step=BotStep.WAIT_SALE, message="尚未開賣，等待開賣時刻")
        sale_at = self._reg.sale_at_epoch()
        now = time.time()
        if not self._did_sale_refresh:
            due = sale_at is not None and now >= sale_at
            if due:
                e._log("開賣時刻已到，重整一次")
                self._safe_refresh()
                self._did_sale_refresh = True
                return
            if sale_at is not None:
                e._sleep(min(e.refresh_interval, max(0.05, sale_at - now)))
            else:
                e._sleep()
            return
        e._sleep()
        self._safe_refresh()

    def _safe_refresh(self) -> None:
        assert self._reg
        url = self._reg.current_url
        if self._reg.is_queue() or is_kktix_held_url(url) or is_kktix_payment_url(url):
            return
        if not is_kktix_registration_url(url):
            return
        self._reg.refresh()
