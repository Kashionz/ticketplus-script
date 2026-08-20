"""KKTIX 購票頁：票種列、張數、條款、電腦配位。"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from selenium.webdriver.remote.webdriver import WebDriver

from ...core.kktix_select import KktixTicketRow
from ...utils.helpers import (
    classify_kktix_page_alert,
    parse_kktix_countdown_remaining,
    parse_kktix_sale_at,
)
from ..base_page import BasePage

logger = logging.getLogger("ticketplus")

_JS_VISIBLE = """
function visible(el) {
    if (!el) return false;
    if (el.hidden) return false;
    if (el.closest && el.closest('[hidden]')) return false;
    if (el.classList && el.classList.contains('ng-hide')) return false;
    if (el.closest && el.closest('.ng-hide')) return false;
    const style = window.getComputedStyle(el);
    const box = el.getBoundingClientRect();
    if (style.visibility === 'hidden' || style.display === 'none') return false;
    if (Number(style.opacity) === 0) return false;
    return box.width >= 2 && box.height >= 2;
}
"""

_JS_SALE_HINT = """
function saleAtAttr() {
    const el = document.querySelector('#sale-countdown[data-sale-at], [data-sale-at]');
    if (!el) return null;
    const n = Number(el.getAttribute('data-sale-at'));
    return Number.isFinite(n) && n > 0 ? n : null;
}
function saleHintText() {
    const chunks = [];
    const countdown = document.querySelector('#sale-countdown');
    if (countdown) chunks.push(countdown.innerText || '');
    const nodes = document.querySelectorAll(
        '[data-ticket-row], #registrationsNewApp .display-table-row, .period-time, .timezoneSuffix'
    );
    for (const n of nodes) chunks.push(n.innerText || '');
    const body = document.body ? (document.body.innerText || '') : '';
    chunks.push(body);
    return chunks.join('\\n').slice(0, 8000);
}
"""

_JS_COLLECT_ROWS = _JS_VISIBLE + """
function collectTicketRows() {
    const seen = new Set();
    const nodes = [];
    const selector = '[data-ticket-row], #registrationsNewApp .display-table-row';
    for (const el of document.querySelectorAll(selector)) {
        if (seen.has(el)) continue;
        seen.add(el);
        nodes.push(el);
    }
    return nodes;
}

function parseRemain(text) {
    const s = String(text || '');
    const m = s.match(/剩(?:餘)?\\s*[:：]?\\s*(\\d+)/);
    if (m) return parseInt(m[1], 10);
    return null;
}

function hasVisibleQty(el) {
    if (!el) return false;
    const nodes = el.querySelectorAll(
        '[data-act="plus"], input.ticket-quantity, .ticket-quantity, [ng-click*="quantityPlus"], [ng-click*="plus"]'
    );
    for (const n of nodes) {
        if (visible(n)) return true;
    }
    return false;
}

function classifyStatus(el) {
    const text = ((el && el.innerText) || '').replace(/\\s+/g, ' ');
    const attr = String((el && el.getAttribute('data-status')) || '').trim();
    const hasPlus = hasVisibleQty(el);
    if (/尚未開賣|秒後開賣/.test(text)) return 'not_on_sale';
    if (text.includes('暫無票券')) return 'unavailable';
    if (text.includes('已售完') || /售罄/.test(text)) return 'sold_out';
    if (hasPlus || /熱賣|剩/.test(text)) return 'on_sale';
    if (/\\d{4}[\\/-]\\d{1,2}[\\/-]\\d{1,2}/.test(text) && /\\d{1,2}:\\d{2}/.test(text)) return 'not_on_sale';
    if (['not_on_sale', 'unavailable', 'sold_out', 'on_sale'].indexOf(attr) >= 0) return attr;
    return 'unknown';
}

function rowName(el) {
    const attr = (el.getAttribute('data-name') || '').trim();
    if (attr) return attr;
    const cells = Array.from(el.children || []).map((c) => (c.innerText || '').trim()).filter(Boolean);
    return cells[0] || ((el.innerText || '').trim().split(/\\s+/)[0] || '');
}

function rowPrice(el) {
    const attr = (el.getAttribute('data-price') || '').trim();
    if (attr) return attr;
    const blob = (el.innerText || '').replace(/\\s+/g, ' ');
    const m = blob.match(/TWD\\s*\\$?\\s*([0-9,]+)|NT\\s*\\$?\\s*([0-9,]+)|\\$\\s*([0-9,]+)/i);
    if (m) return (m[1] || m[2] || m[3] || '').replace(/,/g, '');
    return '';
}
"""


class KktixRegistrationPage(BasePage):
    def __init__(self, driver: WebDriver, timeout: int = 8):
        super().__init__(driver, timeout)

    def open(self, url: str) -> None:
        logger.info("開啟 KKTIX 購票頁: %s", url)
        self.navigate_to(url)

    def list_rows(self) -> List[KktixTicketRow]:
        raw = self.execute_js(
            _JS_COLLECT_ROWS
            + """
            const nodes = collectTicketRows();
            const rows = [];
            for (let i = 0; i < nodes.length; i++) {
                const el = nodes[i];
                const name = rowName(el);
                const price_text = rowPrice(el);
                if (!name && !price_text) continue;
                const status = classifyStatus(el);
                const remaining = parseRemain(el.innerText || '');
                rows.push({
                    index: i,
                    name: name,
                    price_text: price_text,
                    status: status,
                    remaining: remaining,
                    purchasable: status === 'on_sale',
                });
            }
            return rows;
            """
        )
        rows: List[KktixTicketRow] = []
        for item in raw or []:
            if not isinstance(item, dict):
                continue
            remaining = item.get("remaining")
            if remaining is not None:
                try:
                    remaining = int(remaining)
                except (TypeError, ValueError):
                    remaining = None
            status = str(item.get("status") or "unknown")
            rows.append(
                KktixTicketRow(
                    index=int(item.get("index", len(rows))),
                    name=str(item.get("name") or ""),
                    price_text=str(item.get("price_text") or ""),
                    status=status,
                    remaining=remaining,
                    purchasable=status == "on_sale",
                )
            )
        return rows

    def detect_sale_state(self) -> str:
        result = self.execute_js(
            _JS_COLLECT_ROWS
            + """
            const nodes = collectTicketRows();
            let onSale = 0;
            let notOnSale = 0;
            let soldOrWait = 0;
            for (const el of nodes) {
                const status = classifyStatus(el);
                if (status === 'on_sale') onSale += 1;
                else if (status === 'not_on_sale') notOnSale += 1;
                else if (status === 'sold_out' || status === 'unavailable') soldOrWait += 1;
            }
            const countdown = document.querySelector('#sale-countdown');
            if (onSale > 0) return 'on_sale';
            if (soldOrWait > 0) return 'on_sale';
            if (notOnSale > 0) return 'not_on_sale';
            if (countdown) return 'not_on_sale';
            return 'unknown';
            """
        )
        if result in {"not_on_sale", "on_sale", "unknown"}:
            return str(result)
        return "unknown"

    def _sale_hint(self) -> Dict[str, Any]:
        result = self.execute_js(
            _JS_SALE_HINT
            + """
            return {attr: saleAtAttr(), text: saleHintText()};
            """
        )
        return result if isinstance(result, dict) else {}

    def sale_at_epoch(self) -> Optional[float]:
        info = self._sale_hint()
        attr = info.get("attr") if isinstance(info, dict) else None
        if attr is not None:
            try:
                value = float(attr)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
        text = str((info or {}).get("text") or "")
        return parse_kktix_sale_at(text, now=time.time())

    def sale_countdown_remaining(self) -> Optional[float]:
        info = self._sale_hint()
        text = str((info or {}).get("text") or "")
        remaining = parse_kktix_countdown_remaining(text)
        if remaining is not None:
            return remaining
        sale_at = self.sale_at_epoch()
        if sale_at is None:
            return None
        return sale_at - time.time()

    def is_queue(self) -> bool:
        return bool(
            self.execute_js(
                _JS_VISIBLE
                + """
                const body = document.body ? (document.body.innerText || '') : '';
                if (body.includes('查詢空位中')) return true;
                const spinner = document.querySelector('.kk-busy-spinner--enqueue, #queue-spinner');
                return visible(spinner);
                """
            )
        )

    def has_question_captcha(self) -> bool:
        return bool(self.execute_js("return Boolean(document.querySelector('.custom-captcha-inner'));"))

    def page_text(self) -> str:
        text = self.execute_js("return (document.body && document.body.innerText) || '';")
        return text if isinstance(text, str) else ""

    def classify_alert(self) -> str:
        return classify_kktix_page_alert(self.page_text())

    def dismiss_failure_dialog(self) -> bool:
        return bool(
            self.execute_js(
                _JS_VISIBLE
                + """
                const fail = /購票失敗|目前沒有可以購買的票券|目前沒有任何可以購買的票券|別人搶先|無法購買|訂單已過期/;
                const dialogs = document.querySelectorAll(
                    '[role="dialog"], .modal, .alert, .sweet-alert, .kk-modal, .modal-dialog'
                );
                for (const dialog of dialogs) {
                    if (!visible(dialog)) continue;
                    const blob = dialog.innerText || '';
                    if (!fail.test(blob)) continue;
                    const btn = Array.from(dialog.querySelectorAll('button, a.btn, .btn, .close')).find((b) => {
                        if (!visible(b)) return false;
                        const t = ((b.innerText || b.getAttribute('aria-label') || '')).replace(/\\s+/g, '');
                        return !t || /確定|關閉|知道了|OK|關閉視窗|×/.test(t);
                    });
                    if (btn) { btn.click(); return true; }
                    dialog.remove();
                    return true;
                }
                return false;
                """
            )
        )

    def agree_terms(self) -> bool:
        result = self.execute_js(
            """
            const box = document.querySelector(
                '#person_agree_terms, input[ng-model*="agreeTerm"], input[ng-model*="agree"]'
            );
            if (!box) return false;
            if (!box.checked) {
                box.click();
                if (!box.checked) {
                    box.checked = true;
                    box.dispatchEvent(new Event('change', {bubbles: true}));
                    box.dispatchEvent(new Event('input', {bubbles: true}));
                }
            }
            return Boolean(box.checked);
            """
        )
        return bool(result)

    def set_quantity(self, index: int, quantity: int) -> bool:
        result = self.execute_js(
            _JS_COLLECT_ROWS
            + """
            const index = arguments[0];
            const want = Math.max(0, Number(arguments[1]) || 0);
            const rows = collectTicketRows();
            const row = rows[index];
            if (!row) return {ok: false, reason: 'no-row'};

            function readCount() {
                const input = row.querySelector('input.ticket-quantity, input[type="number"], input[ng-model*="quantity"]');
                if (input && String(input.value || '') !== '') {
                    const n = parseInt(String(input.value).replace(/[^0-9]/g, ''), 10);
                    if (Number.isFinite(n)) return n;
                }
                return 0;
            }

            function plusBtn() {
                return row.querySelector('[data-act="plus"]')
                    || Array.from(row.querySelectorAll('button, a')).find((b) =>
                        (b.innerText || '').replace(/\\s+/g, '') === '+'
                    );
            }

            function minusBtn() {
                return row.querySelector('[data-act="minus"]')
                    || Array.from(row.querySelectorAll('button, a')).find((b) =>
                        (b.innerText || '').replace(/\\s+/g, '') === '-'
                    );
            }

            function setInput(value) {
                const input = row.querySelector('input.ticket-quantity, input[type="number"], input[ng-model*="quantity"]');
                if (!input) return;
                input.focus();
                const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (desc && desc.set) desc.set.call(input, String(value));
                else input.value = String(value);
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }

            let current = readCount();
            for (let i = 0; i < 12 && current < want; i++) {
                const plus = plusBtn();
                if (!plus || plus.disabled) break;
                plus.click();
                current = readCount();
            }
            for (let i = 0; i < 12 && current > want; i++) {
                const minus = minusBtn();
                if (!minus || minus.disabled) break;
                minus.click();
                current = readCount();
            }
            if (readCount() !== want) setInput(want);
            const qty = readCount();
            return {ok: want === 0 ? qty === 0 : qty === want, qty: qty};
            """,
            int(index),
            int(quantity),
        )
        if isinstance(result, dict):
            ok = bool(result.get("ok"))
            if ok:
                logger.info("已設定票種 #%s x%s", index, quantity)
            return ok
        return bool(result)

    def click_computer_assign(self) -> bool:
        clicked = self.execute_js(
            _JS_VISIBLE
            + """
            function enabled(el) {
                if (!el || el.disabled) return false;
                if (el.classList && (el.classList.contains('disabled') || el.classList.contains('disabledBtn'))) return false;
                return visible(el);
            }
            function textOf(el) {
                return ((el && el.innerText) || '').replace(/\\s+/g, '');
            }
            function isSelfSeat(el) {
                if (!el) return false;
                if ((el.getAttribute('data-act') || '') === 'self-seat') return true;
                return textOf(el).includes('自行選位');
            }
            const buttons = Array.from(document.querySelectorAll('button, a.btn, .btn, [data-act]'));
            function isComputerAssign(el) {
                if (!el || isSelfSeat(el)) return false;
                if ((el.getAttribute('data-act') || '') === 'auto-seat') return true;
                return textOf(el).includes('電腦配位');
            }
            const assignBtns = buttons.filter((b) => isComputerAssign(b) && visible(b));
            if (assignBtns.length) {
                const auto = assignBtns.find(enabled);
                if (auto) {
                    auto.click();
                    return 'auto';
                }
                return '';
            }
            const area = document.querySelector('.register-new-next-button-area') || document;
            const nextCandidates = Array.from(area.querySelectorAll('button, a.btn, .btn, [data-act="next"]'));
            const next = nextCandidates.find((b) => {
                if (!enabled(b) || isSelfSeat(b)) return false;
                const text = textOf(b);
                if (text.includes('電腦配位')) return true;
                if (text !== '下一步') return false;
                if (b.classList && b.classList.contains('btn-primary')) return true;
                if ((b.getAttribute('data-act') || '') === 'next') return true;
                return Boolean(b.classList && b.classList.contains('btn-primary'));
            });
            if (next) {
                next.click();
                return 'next';
            }
            return '';
            """
        )
        if clicked:
            logger.info("已點擊%s", "電腦配位" if clicked == "auto" else "下一步")
            return True
        return False

    def has_invitation_field(self) -> bool:
        return bool(self._invitation_field().get("found"))

    def fill_invitation(self, code: str) -> bool:
        if not code or not str(code).strip():
            return False
        last: Dict[str, Any] = {}
        for _ in range(6):
            last = self._fill_invitation_once(str(code).strip())
            if last.get("filled"):
                logger.info("已填入邀請碼")
                return True
            if last.get("reason") == "no-field":
                break
            self.wait_seconds(0.15)
        return False

    def _invitation_field(self) -> Dict[str, Any]:
        result = self.execute_js(
            _JS_VISIBLE
            + """
            function looksLike(text) {
                return /邀請|invitation|promo|coupon|優惠碼|兌換碼|access.?code/i.test(String(text || ''));
            }
            const inputs = Array.from(document.querySelectorAll('input')).filter((el) => {
                if (!visible(el) || el.disabled) return false;
                const t = String(el.type || 'text').toLowerCase();
                return t === 'text' || t === 'search' || t === '' || t === 'tel';
            });
            for (const input of inputs) {
                const box = input.closest('label, .form-group, .control-group, li, div') || input.parentElement;
                const blob = [
                    (box && box.innerText) || '',
                    input.placeholder || '',
                    input.getAttribute('aria-label') || '',
                    input.name || '',
                    input.id || '',
                ].join(' ');
                if (looksLike(blob)) return {found: 1};
            }
            return {found: 0};
            """
        )
        return result if isinstance(result, dict) else {"found": 0}

    def _fill_invitation_once(self, code: str) -> Dict[str, Any]:
        result = self.execute_js(
            _JS_VISIBLE
            + """
            const code = arguments[0];
            function looksLike(text) {
                return /邀請|invitation|promo|coupon|優惠碼|兌換碼|access.?code/i.test(String(text || ''));
            }
            function setValue(input, value) {
                input.focus();
                const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (desc && desc.set) desc.set.call(input, value);
                else input.value = value;
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }
            const inputs = Array.from(document.querySelectorAll('input')).filter((el) => {
                if (!visible(el) || el.disabled || el.readOnly) return false;
                const t = String(el.type || 'text').toLowerCase();
                return t === 'text' || t === 'search' || t === '' || t === 'tel';
            });
            for (const input of inputs) {
                const box = input.closest('label, .form-group, .control-group, li, div') || input.parentElement;
                const blob = [
                    (box && box.innerText) || '',
                    input.placeholder || '',
                    input.getAttribute('aria-label') || '',
                    input.name || '',
                    input.id || '',
                ].join(' ');
                if (!looksLike(blob)) continue;
                setValue(input, code);
                return {filled: 1};
            }
            return {filled: 0, reason: 'no-field'};
            """,
            code,
        )
        return result if isinstance(result, dict) else {"filled": 0}
