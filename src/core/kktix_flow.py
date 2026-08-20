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
        self._seats_locked = False

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
            dismiss = getattr(self._reg, "dismiss_js_alert", None)
            if callable(dismiss) and dismiss() == "rechoose":
                self._seats_locked = True
                e._log_once("kktix-keep-seats", "已拒絕重新選票，保留目前座位，不再重選")
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

            alert = self._handle_page_alert(url)
            if alert == "wait":
                continue
            if alert == "refreshed":
                retries += 1
                continue

            if self._confirm_seats_if_needed():
                retries += 1
                continue

            if self._seats_locked:
                self._advance_held(url)
                e._sleep(0.8)
                retries += 1
                continue

            if is_kktix_held_url(url):
                self._advance_held(url)
                e._sleep(0.8)
                retries += 1
                continue

            if is_kktix_registration_url(url):
                result = self._process_registration()
                if result == "wait_sale":
                    continue
                if result:
                    e._sleep(0.8)
                retries += 1
                continue

            if self._reg.is_cloudflare_challenge() is True:
                self._handle_human_gate()
                continue
            if self._seats_locked:
                self._advance_held(url)
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
        cloudflare = self._reg.is_cloudflare_challenge() is True
        recaptcha = self._reg.has_recaptcha()
        question = self._reg.has_question_captcha()
        if not cloudflare and not recaptcha and not question:
            return False
        if cloudflare:
            e._update_state(step=BotStep.WAIT_HUMAN, message="請在瀏覽器完成 Cloudflare 人機驗證")
            e._log_once(
                "kktix-cf",
                "出現 Cloudflare「正在驗證您是否是人類」。請在這個 Chrome 視窗完成驗證，"
                "完成前程式不會重整（重整會重跑驗證）。通過後會自動繼續。",
            )
            while not e._should_stop() and self._reg.is_cloudflare_challenge():
                e._sleep(0.5)
            return True
        if not e.wait_for_human:
            e._log("出現驗證碼或活動問答，但 wait_for_human=false，稍後重試", "WARNING")
            e._sleep(1.0)
            return True
        e._update_state(step=BotStep.WAIT_HUMAN, message="請在瀏覽器完成驗證碼或問答")
        e._log("出現 reCAPTCHA 或活動問答，請在瀏覽器手動完成，完成後程式會繼續")
        while not e._should_stop() and (self._reg.has_recaptcha() or self._reg.has_question_captcha()):
            e._sleep(0.5)
        return True

    def _confirm_seats_if_needed(self) -> bool:
        """劃位頁已有座位時，點確認座位 → 完成選位以提早鎖票。"""
        assert self._checkout
        e = self.engine
        if self._checkout.has_seat_confirm_ui() is not True:
            return False
        e._update_state(step=BotStep.SUBMIT, message="確認座位並完成選位")
        result = self._checkout.confirm_assigned_seats()
        if result == "done":
            self._seats_locked = True
            e._log("已點「完成選位」，等待進入填表")
            e._sleep(0.6)
            return True
        e._log_once("kktix-wait-seats", "劃位畫面已出現，等待座位配好後再點完成選位（不重整）")
        e._sleep(0.4)
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
        else:
            e._log_once(
                "kktix-prefill",
                "下一步無法點擊。請到 https://kktix.com/account/prefills 填寫報名預填資料，或在本頁手動補齊；填完後程式會繼續按下一步",
            )

    def _handle_page_alert(self, url: str) -> str:
        """verification/busy/failure/csrf。回傳 wait（不計重試）、refreshed、或空字串繼續。"""
        assert self._reg
        e = self.engine
        kind = self._reg.classify_alert()
        held = is_kktix_held_url(url)
        if kind == "verification":
            e._update_state(step=BotStep.WAIT_LOGIN, message="請完成手機或 Email 驗證")
            e._log_once(
                "kktix-verify",
                "購票需要已驗證的手機與電子郵件。請在瀏覽器完成驗證，完成前不會重整頁面",
            )
            e._sleep(1.0)
            return "wait"
        if kind == "busy":
            e._update_state(step=BotStep.WAIT_QUEUE, message="流量管制／系統忙碌，稍後再試")
            e._log_once("kktix-busy", "偵測到流量管制或系統忙碌，等待後再試，已鎖票則不重整")
            e._sleep()
            return "wait"
        if kind == "failure":
            closed = self._reg.dismiss_failure_dialog()
            if closed:
                e._log("購票失敗視窗已關閉")
            if held:
                e._log_once("kktix-fail-held", "已鎖票後出現失敗訊息，只往前不重選")
                return ""
            e._sleep()
            return "wait"
        if kind == "csrf":
            if held or self._reg.is_queue() or self._at_payment(url):
                e._log_once("kktix-csrf-hold", "已鎖票或排隊中，忽略官方 CSRF 重整")
                e._sleep()
                return "wait"
            e._log("官方要求更新頁面（CSRF），尚未鎖票，跟隨重整")
            self._safe_refresh()
            e._sleep()
            return "refreshed"
        return ""

    def _process_registration(self) -> bool | str:
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
            return "wait_sale"

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
            e._sleep()
            return False

        if self._reg.has_invitation_field():
            code = (cfg.exclusive_code or "").strip()
            if not code:
                e._log_once("kktix-need-code", "購票頁出現邀請碼欄，但設定未填序號")
                e._sleep()
                return False
            if not self._reg.fill_invitation(code):
                e._log_once("kktix-fill-code-fail", "找到邀請碼欄但填入失敗")
                e._sleep()
                return False

        if e.auto_agree:
            self._reg.agree_terms()

        e._update_state(step=BotStep.SUBMIT, message="送出電腦配位")
        if not self._reg.click_computer_assign():
            e._log("電腦配位 / 下一步尚未可按，稍後再試")
            e._sleep()
            return False
        return True

    def _wait_sale(self) -> None:
        assert self._reg
        e = self.engine
        e._update_state(step=BotStep.WAIT_SALE, message="尚未開賣，等待開賣時刻")
        sale_at = self._reg.sale_at_epoch()
        remaining = self._reg.sale_countdown_remaining()
        now = time.time()
        if not self._did_sale_refresh:
            due = False
            if sale_at is not None:
                due = now >= sale_at
            elif remaining is not None:
                due = remaining <= 0
            if due:
                e._log("開賣時刻已到，重整一次")
                self._safe_refresh()
                self._did_sale_refresh = True
                return
            if sale_at is not None:
                e._sleep(min(e.refresh_interval, max(0.05, sale_at - now)))
            elif remaining is not None and remaining > 0:
                e._sleep(min(e.refresh_interval, max(0.05, remaining)))
            else:
                e._sleep()
            return
        e._sleep()
        self._safe_refresh()

    def _safe_refresh(self) -> None:
        assert self._reg
        url = self._reg.current_url
        if self._reg.is_cloudflare_challenge() is True:
            return
        if self._seats_locked:
            return
        if self._checkout and self._checkout.has_seat_confirm_ui() is True:
            return
        if self._reg.is_queue() or is_kktix_held_url(url) or is_kktix_payment_url(url):
            return
        if not is_kktix_registration_url(url):
            return
        self._reg.refresh()
