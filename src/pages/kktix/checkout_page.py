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
