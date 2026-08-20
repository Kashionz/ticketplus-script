"""KKTIX 鎖票後：關通知、按下一步／確認；不改表單欄位。"""

from __future__ import annotations

import logging

from selenium.webdriver.remote.webdriver import WebDriver

from ..base_page import BasePage

logger = logging.getLogger("ticketplus")

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


class KktixCheckoutPage(BasePage):
    ADVANCE_TEXTS = ("下一步", "確認訂單並繳費", "確認訂單")

    def __init__(self, driver: WebDriver, timeout: int = 8):
        super().__init__(driver, timeout)

    def has_seat_confirm_ui(self) -> bool:
        return bool(
            self.execute_js(
                _JS_VISIBLE
                + "return visible(document.querySelector('.btn-group-for-seat'));"
            )
        )

    def confirm_assigned_seats(self) -> str:
        """電腦配位／自行選位後：確認座位 → 完成選位。不改座位、不刪除。

        回傳 done / wait / missing。
        """
        result = self.execute_js(
            _JS_VISIBLE
            + """
            function textOf(el) {
                return ((el && el.innerText) || '').replace(/\\s+/g, '');
            }
            const group = document.querySelector('.btn-group-for-seat');
            if (!visible(group)) return 'missing';
            const badge = group.querySelector('.badge');
            const badgeN = badge ? parseInt(String(badge.textContent || '').replace(/\\D/g, ''), 10) : 0;
            const seatCount = group.querySelectorAll('.ticket-seat, .ticket-list .ticket').length;
            if (!(seatCount > 0 || badgeN > 0)) return 'wait';

            function findDone() {
                return Array.from(group.querySelectorAll('a, button')).find((el) => {
                    if (!visible(el)) return false;
                    const text = textOf(el);
                    if (text.includes('刪除')) return false;
                    return text.includes('完成選位') || (el.getAttribute('ng-click') || '').includes('done()');
                });
            }
            let done = findDone();
            if (!done) {
                const toggle = Array.from(group.querySelectorAll('button, a')).find((el) => {
                    if (!visible(el)) return false;
                    return textOf(el).includes('確認座位');
                });
                if (toggle) toggle.click();
                done = findDone();
            }
            if (!done) return 'wait';
            done.click();
            return 'done';
            """
        )
        if result == "done":
            logger.info("已點「完成選位」")
        return result if result in {"done", "wait", "missing"} else "missing"

    def dismiss_seat_notice(self) -> None:
        self.execute_js(
            _JS_VISIBLE
            + """
            const texts = ['我知道了', '知道了', '確定', '關閉', 'OK'];
            const dialogs = document.querySelectorAll('[role="dialog"], .modal, .v-dialog, .kk-modal, .sweet-alert');
            for (const dialog of dialogs) {
                if (!visible(dialog)) continue;
                const buttons = Array.from(dialog.querySelectorAll('button, a.btn, .btn'));
                const btn = buttons.find((b) => {
                    const text = (b.innerText || '').replace(/\\s+/g, '');
                    return texts.some((t) => text.includes(t));
                });
                if (btn) {
                    btn.click();
                    return true;
                }
            }
            const loose = Array.from(document.querySelectorAll('button, a.btn, .btn')).find((b) => {
                if (!visible(b)) return false;
                const text = (b.innerText || '').replace(/\\s+/g, '');
                return text === '我知道了' || text === '知道了';
            });
            if (loose) loose.click();
            return false;
            """
        )

    def click_advance(self) -> bool:
        clicked = self.execute_js(
            _JS_VISIBLE
            + """
            const allow = arguments[0];
            function textOf(el) {
                return ((el && el.innerText) || '').replace(/\\s+/g, '');
            }
            function enabled(el) {
                if (!el || el.disabled) return false;
                if (el.classList && (el.classList.contains('disabled') || el.classList.contains('disabledBtn'))) return false;
                return visible(el);
            }
            const buttons = Array.from(document.querySelectorAll(
                'button, a.btn, .btn, [data-act="next"], .register-new-next-button-area button'
            ));
            const btn = buttons.find((b) => {
                if (!enabled(b)) return false;
                const text = textOf(b);
                if (!text || text.includes('自行選位')) return false;
                if (text.includes('知道了') || text.includes('我知道了')) return false;
                return allow.some((t) => text.includes(t));
            });
            if (!btn) return false;
            btn.click();
            return true;
            """,
            list(self.ADVANCE_TEXTS),
        )
        if clicked:
            logger.info("已點擊下一步")
        return bool(clicked)

    def has_card_field(self) -> bool:
        return bool(
            self.execute_js(
                _JS_VISIBLE
                + """
                const inputs = Array.from(document.querySelectorAll(
                    'input[name="cardNumber"], input[autocomplete="cc-number"]'
                ));
                if (inputs.some((el) => visible(el))) return true;
                const frames = Array.from(document.querySelectorAll('iframe[src]'));
                return frames.some((f) => {
                    const src = String(f.getAttribute('src') || '').toLowerCase();
                    return src.includes('adyen') || src.includes('checkoutshopper')
                        || src.includes('3dsecure') || src.includes('acs.');
                });
                """
            )
        )
