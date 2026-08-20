"""購票頁：選區 / 張數 / 序號 / 同意條款 / 下一步。"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from .base_page import BasePage
from ..utils.helpers import is_payment_url

logger = logging.getLogger("ticket-helper")


class OrderPage(BasePage):
    NEXT_BTN = (By.CSS_SELECTOR, "button.nextBtn")
    CHECKBOX = (By.CSS_SELECTOR, 'input[type="checkbox"]')

    FAILURE_TEXTS = (
        "購票失敗",
        "您選擇的票種已售完",
        "已售完",
        "別人搶先一步",
        "已無可配座位",
        "本活動有限制購票總張數",
        "已被購買",
        "系統忙碌",
        "無法購票",
    )

    def __init__(self, driver: WebDriver, timeout: int = 8):
        super().__init__(driver, timeout)

    def wait_vue_ready(self, timeout: float = 8.0) -> bool:
        elapsed = 0.0
        while elapsed < timeout:
            ready = self.execute_js(
                """
                const panels = document.querySelectorAll('.v-expansion-panel').length;
                const plus = document.querySelectorAll('.count-button .mdi-plus, .mdi-plus').length;
                const rows = document.querySelectorAll('.row.py-1.py-md-4').length;
                const nextBtn = document.querySelector('button.nextBtn');
                return panels > 0 || plus > 0 || rows > 0 || Boolean(nextBtn);
                """
            )
            if ready:
                return True
            self.wait_seconds(0.15)
            elapsed += 0.15
        return False

    def wait_for_area_widgets(self, timeout: float = 8.0) -> bool:
        elapsed = 0.0
        while elapsed < timeout:
            if self.list_area_names() or self.execute_js(
                "return Boolean(document.querySelector('.v-expansion-panel-header, .count-button .mdi-plus'));"
            ):
                return True
            self.wait_seconds(0.2)
            elapsed += 0.2
        return False

    def detect_sale_state(self) -> Dict[str, Any]:
        """看票區欄位判斷購票頁是否已開賣。

        未開賣：欄位顯示開賣時間 / 尚未開賣。
        已開賣：可選購票數量，或顯示已售完 / 剩餘 / 熱賣中。
        """
        result = self.execute_js(
            """
            function ownHeader(panel) {
                return Array.from(panel.children).find((el) =>
                    el.classList && el.classList.contains('v-expansion-panel-header')
                );
            }
            function isLeaf(panel) {
                return panel.querySelectorAll('.v-expansion-panel').length === 0;
            }
            const onSaleRe = /已售完|剩餘|熱賣中|熱賣|暫停銷售|銷售截止|無可販售票種|無可販售票區|暫無票券/;
            const notOnSaleRe = /開賣時間|尚未開賣|開放登記|尚未開放/;
            const dateRe = /\\d{4}[\\/-]\\d{1,2}[\\/-]\\d{1,2}/;
            const timeRe = /\\d{1,2}:\\d{2}/;
            const plus = document.querySelectorAll('.count-button').length;
            const samples = [];
            let onSale = 0;
            let notOnSale = 0;

            function classify(text, hasQty) {
                const blob = (text || '').replace(/\\s+/g, ' ').trim();
                if (!blob && !hasQty) return 'unknown';
                if (hasQty || onSaleRe.test(blob)) return 'on_sale';
                if (notOnSaleRe.test(blob) || (dateRe.test(blob) && timeRe.test(blob))) return 'not_on_sale';
                return 'unknown';
            }

            const leafs = Array.from(document.querySelectorAll('.v-expansion-panel')).filter(isLeaf);
            for (const panel of leafs) {
                const header = ownHeader(panel);
                if (!header) continue;
                const text = (header.innerText || '').trim().replace(/\\s+/g, ' ');
                const hasQty = Boolean(panel.querySelector('.count-button, .mdi-plus, .mdi-minus'));
                const state = classify(text, hasQty);
                if (text) samples.push(text);
                if (state === 'on_sale') onSale += 1;
                if (state === 'not_on_sale') notOnSale += 1;
            }

            const rows = Array.from(document.querySelectorAll('.row.py-1.py-md-4, .row.py-1'));
            for (const row of rows) {
                const text = (row.innerText || '').trim().replace(/\\s+/g, ' ');
                const hasQty = Boolean(row.querySelector('.count-button, .mdi-plus, .mdi-minus'));
                const state = classify(text, hasQty);
                if (text && !samples.includes(text)) samples.push(text);
                if (state === 'on_sale') onSale += 1;
                if (state === 'not_on_sale') notOnSale += 1;
            }

            let state = 'unknown';
            let reason = 'no-area';
            if (plus > 0 || onSale > 0) {
                state = 'on_sale';
                reason = plus > 0 ? 'quantity' : 'sold-or-remain';
            } else if (notOnSale > 0) {
                state = 'not_on_sale';
                reason = 'sale-time';
            } else if (leafs.length || rows.length) {
                reason = 'area-unclassified';
            }
            return {
                state,
                reason,
                plus,
                onSale,
                notOnSale,
                samples: samples.slice(0, 8),
            };
            """
        )
        if isinstance(result, dict) and result.get("state"):
            return result
        return {"state": "unknown", "reason": "no-result", "samples": []}

    def is_on_sale(self) -> bool:
        return self.detect_sale_state().get("state") == "on_sale"

    def is_not_on_sale(self) -> bool:
        return self.detect_sale_state().get("state") == "not_on_sale"

    def list_area_names(self) -> List[str]:
        names = self.execute_js(
            """
            function ownHeader(panel) {
                return Array.from(panel.children).find((el) =>
                    el.classList && el.classList.contains('v-expansion-panel-header')
                );
            }
            function isLeaf(panel) {
                return panel.querySelectorAll('.v-expansion-panel').length === 0;
            }
            const leafs = Array.from(document.querySelectorAll('.v-expansion-panel')).filter(isLeaf);
            const headers = leafs.map((p) => ownHeader(p)).filter(Boolean);
            const rows = Array.from(document.querySelectorAll('.row.py-1.py-md-4 .font-weight-medium'));
            const texts = [...headers, ...rows].map((el) => (el.innerText || '').trim().replace(/\\s+/g, ' '));
            return texts.filter(Boolean);
            """
        )
        return list(names or [])

    def select_area_and_quantity(
        self,
        area_priorities: List[str],
        quantity: int,
        allow_fallback: bool = False,
        require_exact_quantity: bool = False,
    ) -> bool:
        if not self.wait_for_area_widgets():
            logger.debug("購票區元件尚未出現")
            return False
        priorities = [p for p in area_priorities if p and p.strip()]
        last_result: Dict[str, Any] = {}
        for keyword in priorities:
            result = self._try_keyword(keyword, quantity, require_exact_quantity)
            last_result = result
            if result.get("ok"):
                return True
        if not priorities or allow_fallback:
            if self._select_first_available(quantity, require_exact_quantity):
                return True
        names = self.list_area_names()
        reason = last_result.get("message") or "unknown"
        if reason == "short-stock":
            reason = (
                f"剩餘 {last_result.get('remain')} 不足指定 {quantity} 張"
                f"（{last_result.get('selected') or '符合的票區'}）"
            )
        logger.info(
            "票區未選到（要找 %s；畫面上有：%s；原因：%s）",
            priorities or "（未指定，改第一個可購）",
            names or "（尚未渲染）",
            reason,
        )
        return False

    def _try_keyword(
        self,
        keyword: str,
        quantity: int,
        require_exact_quantity: bool = False,
    ) -> Dict[str, Any]:
        result = self._select_once(keyword, quantity, require_exact_quantity)
        if result.get("success") and result.get("clicked"):
            self._log_selected(result, keyword, quantity)
            return {"ok": True, **result}
        if result.get("needRetry") or (result.get("success") and not result.get("clicked")):
            if result.get("message") == "expanded-group":
                self.wait_seconds(0.35)
                result = self._select_once(keyword, quantity, require_exact_quantity)
                if result.get("success") and result.get("clicked"):
                    self._log_selected(result, keyword, quantity)
                    return {"ok": True, **result}
            retried = self._retry_plus(quantity, require_exact_quantity)
            if retried.get("success"):
                self._log_selected(retried, keyword, quantity)
                return {"ok": True, **retried}
        return {"ok": False, **(result or {})}

    def _log_selected(self, result: Dict[str, Any], keyword: str, wanted: int) -> None:
        name = result.get("selected") or keyword or "第一個可購票區"
        qty = result.get("quantity") or wanted
        remain = result.get("remain")
        if result.get("reduced"):
            extra = f"，剩餘 {remain}" if remain is not None else ""
            logger.info("已選擇: %s x%s（指定 %s 張%s，改買剩餘）", name, qty, wanted, extra)
            return
        logger.info("已選擇: %s x%s", name, qty)

    def _select_first_available(self, quantity: int, require_exact_quantity: bool = False) -> bool:
        """畫面上由上到下第一個還能買的內層票區。"""
        for _ in range(8):
            result = self._try_keyword("", quantity, require_exact_quantity)
            if result.get("ok"):
                return True
            if not self._expand_next_group():
                break
            self.wait_seconds(0.3)
        return False

    def _expand_next_group(self) -> bool:
        return bool(
            self.execute_js(
                """
                const groups = Array.from(document.querySelectorAll('.v-expansion-panel')).filter((p) =>
                    p.querySelectorAll('.v-expansion-panel').length > 0
                    && !p.classList.contains('v-expansion-panel--active')
                );
                if (!groups.length) return false;
                const header = Array.from(groups[0].children).find((el) =>
                    el.classList && el.classList.contains('v-expansion-panel-header')
                );
                if (!header) return false;
                header.click();
                return true;
                """
            )
        )

    def _select_once(
        self,
        keyword: str,
        quantity: int,
        require_exact_quantity: bool = False,
    ) -> Dict[str, Any]:
        result = self.execute_js(
            """
            const keyword = arguments[0] || '';
            const ticketNumber = arguments[1] || 1;
            const requireExact = Boolean(arguments[2]);
            const normalize = (s) => (s || '').replace(/[\\s\\u3000]/g, '').toLowerCase();
            const kw = normalize(keyword);

            function isSoldOut(el) {
                const text = el.textContent || '';
                const sold = [/剩餘\\s*0(?!\\d)/, /剩餘\\s*:\\s*0(?!\\d)/, /sold\\s*out/i, /售完/, /已售完/, /售罄/, /無庫存/];
                const avail = [/熱賣中/, /熱賣/, /熱售/, /可購買/, /available/i, /剩餘\\s*[1-9]\\d*/];
                if (sold.some(p => p.test(text))) {
                    if (avail.some(p => p.test(text))) return false;
                    return true;
                }
                return false;
            }

            function parseRemain(text) {
                const s = String(text || '');
                if ((/已售完|售罄|售完/.test(s)) && !/剩餘\\s*[1-9]/.test(s)) return 0;
                const m = s.match(/剩餘\\s*[:：]?\\s*(\\d+)/);
                return m ? parseInt(m[1], 10) : null;
            }

            function ownHeader(panel) {
                return Array.from(panel.children).find((el) =>
                    el.classList && el.classList.contains('v-expansion-panel-header')
                );
            }

            function isLeaf(panel) {
                return panel.querySelectorAll('.v-expansion-panel').length === 0;
            }

            function headerText(panel) {
                const header = ownHeader(panel);
                return ((header && header.innerText) || '').trim().replace(/\\s+/g, ' ');
            }

            function remainOf(panel) {
                const header = ownHeader(panel);
                const small = header && header.querySelector('small.ml-1, .remain-tag');
                if (small) {
                    const n = parseRemain(small.textContent);
                    if (n !== null) return n;
                }
                return parseRemain(headerText(panel));
            }

            function buyQtyFor(remain, want) {
                if (remain === 0) return null;
                if (remain === null || remain === undefined) return want;
                if (remain >= want) return want;
                return requireExact ? null : remain;
            }

            function nameMatches(name, keyword) {
                const hay = normalize(name);
                const needle = normalize(keyword);
                if (!needle) return true;
                if (hay.includes(needle)) return true;
                const stripped = needle.endsWith('區') ? needle.slice(0, -1) : needle;
                return Boolean(stripped) && hay.includes(stripped);
            }

            function expandAncestors(panel) {
                let node = panel.parentElement;
                let clicked = false;
                while (node) {
                    if (node.classList && node.classList.contains('v-expansion-panel')) {
                        if (!node.classList.contains('v-expansion-panel--active')) {
                            const header = ownHeader(node);
                            if (header) {
                                header.click();
                                clicked = true;
                            }
                        }
                    }
                    node = node.parentElement;
                }
                return clicked;
            }

            function findLeaf(name) {
                const leafs = Array.from(document.querySelectorAll('.v-expansion-panel')).filter(isLeaf);
                return leafs.find((p) => headerText(p) === name)
                    || leafs.find((p) => nameMatches(headerText(p), name))
                    || null;
            }

            function readCount(panel) {
                const box = panel && panel.querySelector('.count-button');
                if (!box) return 0;
                const mid = Array.from(box.children).find((el) => el.tagName === 'DIV');
                const n = parseInt(String((mid && mid.textContent) || box.textContent || '').replace(/[^0-9]/g, ''), 10);
                return Number.isFinite(n) ? n : 0;
            }

            function closestBtn(el) {
                return el ? (el.closest('button') || el) : null;
            }

            function plusBtn(panel) {
                const icon = panel && (panel.querySelector('.count-button .mdi-plus') || panel.querySelector('.mdi-plus'));
                return closestBtn(icon);
            }

            function minusBtn(panel) {
                const icon = panel && (panel.querySelector('.count-button .mdi-minus') || panel.querySelector('.mdi-minus'));
                return closestBtn(icon);
            }

            function isLimited(btn) {
                if (!btn) return true;
                if (btn.disabled) return true;
                const limit = String(btn.getAttribute('data-limit') || '').toLowerCase();
                if (limit === 'true' || limit === '1') return true;
                const count = parseInt(btn.getAttribute('data-count') || '', 10);
                return Number.isFinite(count) && count <= 0;
            }

            function adjustQty(startPanel, name, want) {
                let panel = startPanel;
                let qty = readCount(panel);
                for (let i = 0; i < 12 && qty < want; i++) {
                    const plus = plusBtn(panel);
                    if (!plus || isLimited(plus)) break;
                    plus.click();
                    panel = findLeaf(name) || panel;
                    const next = readCount(panel);
                    if (next <= qty) break;
                    qty = next;
                }
                for (let i = 0; i < 12 && qty > want; i++) {
                    const minus = minusBtn(panel);
                    if (!minus) break;
                    minus.click();
                    panel = findLeaf(name) || panel;
                    const next = readCount(panel);
                    if (next >= qty) break;
                    qty = next;
                }
                return {qty: qty, panel: panel};
            }

            function packResult(ok, extra) {
                return Object.assign({success: ok, clicked: ok}, extra || {});
            }

            const hasPanel = document.querySelector('.v-expansion-panel');
            const hasPlus = document.querySelector('.count-button .mdi-plus, .mdi-plus');

            if (hasPanel) {
                const allPanels = Array.from(document.querySelectorAll('.v-expansion-panel'));
                const leafs = allPanels.filter(isLeaf);
                const valid = [];
                const skipped = [];
                for (const panel of leafs) {
                    const header = ownHeader(panel);
                    if (!header) continue;
                    const name = headerText(panel);
                    if (isSoldOut(header)) continue;
                    const remain = remainOf(panel);
                    const buyQty = buyQtyFor(remain, ticketNumber);
                    if (buyQty == null) {
                        skipped.push({name: name, remain: remain, reason: 'short-stock'});
                        continue;
                    }
                    valid.push({panel: panel, name: name, header: header, remain: remain, buyQty: buyQty});
                }
                let target = kw ? valid.find((v) => nameMatches(v.name, keyword)) : valid[0];
                if (!target && kw) {
                    const skippedHit = skipped.find((v) => nameMatches(v.name, keyword));
                    if (skippedHit) {
                        return {
                            success: false,
                            message: 'short-stock',
                            selected: skippedHit.name,
                            remain: skippedHit.remain,
                            wanted: ticketNumber,
                        };
                    }
                    const groups = allPanels.filter((p) => !isLeaf(p));
                    const group = groups.find((p) => {
                        const g = normalize(headerText(p));
                        if (!g) return false;
                        const base = g.endsWith('區') ? g.slice(0, -1) : g;
                        return kw.startsWith(g) || (base && kw.startsWith(base));
                    });
                    if (group && !group.classList.contains('v-expansion-panel--active')) {
                        const gh = ownHeader(group);
                        if (gh) gh.click();
                        return {success: false, message: 'expanded-group', needRetry: true, found: valid.map((v) => v.name)};
                    }
                }
                if (!target) {
                    return {success: false, message: 'no-panel-match', attempted: keyword, found: valid.map((v) => v.name)};
                }
                expandAncestors(target.panel);
                if (!target.panel.classList.contains('v-expansion-panel--active')) {
                    target.header.click();
                    target.panel = findLeaf(target.name) || target.panel;
                    target.header = ownHeader(target.panel) || target.header;
                }
                const plus = plusBtn(target.panel);
                if (!plus && !target.panel.querySelector('.count-button')) {
                    return {success: true, clicked: false, needRetry: true, selected: target.name, remain: target.remain};
                }
                const adjusted = adjustQty(target.panel, target.name, target.buyQty);
                const qty = adjusted.qty;
                const reduced = qty < ticketNumber;
                if (qty < 1) {
                    return {success: false, message: 'no-qty', selected: target.name, remain: target.remain};
                }
                if (reduced && requireExact) {
                    return {
                        success: false,
                        message: 'short-stock',
                        selected: target.name,
                        remain: target.remain == null ? qty : target.remain,
                        quantity: qty,
                        wanted: ticketNumber,
                    };
                }
                return packResult(true, {
                    selected: target.name,
                    type: 'panel',
                    quantity: qty,
                    remain: target.remain,
                    wanted: ticketNumber,
                    reduced: reduced,
                });
            }

            if (hasPlus) {
                const rows = document.querySelectorAll('.row.py-1.py-md-4, .row.py-1');
                const valid = [];
                for (const row of rows) {
                    const plus = row.querySelector('.count-button .mdi-plus, .mdi-plus');
                    if (!plus) continue;
                    const nameEl = row.querySelector('.font-weight-medium, .text-title, .v-list-item__title');
                    const name = ((nameEl && nameEl.textContent) || row.textContent || '').trim().replace(/\\s+/g, ' ');
                    if (isSoldOut(row)) continue;
                    const remain = parseRemain(name);
                    const buyQty = buyQtyFor(remain, ticketNumber);
                    if (buyQty == null) continue;
                    valid.push({row: row, name: name, plus: plus, remain: remain, buyQty: buyQty});
                }
                let target = kw ? valid.find(v => normalize(v.name).includes(kw)) : valid[0];
                if (!target) return {success: false, message: 'no-row-match', attempted: keyword};
                const btn = closestBtn(target.plus);
                for (let i = 0; i < target.buyQty; i++) {
                    if (!btn || isLimited(btn)) break;
                    btn.click();
                }
                return packResult(true, {
                    selected: target.name,
                    type: 'row',
                    quantity: target.buyQty,
                    remain: target.remain,
                    wanted: ticketNumber,
                    reduced: target.buyQty < ticketNumber,
                });
            }
            return {success: false, message: 'no-selectable'};
            """,
            keyword,
            int(quantity),
            bool(require_exact_quantity),
        )
        return result if isinstance(result, dict) else {"success": False}

    def _retry_plus(self, quantity: int, require_exact_quantity: bool = False) -> Dict[str, Any]:
        last: Dict[str, Any] = {}
        for _ in range(6):
            self.wait_seconds(0.2)
            last = self.execute_js(
                """
                const want = arguments[0] || 1;
                const requireExact = Boolean(arguments[1]);
                function ownHeader(panel) {
                    return Array.from(panel.children).find((el) =>
                        el.classList && el.classList.contains('v-expansion-panel-header')
                    );
                }
                function isLeaf(panel) {
                    return panel.querySelectorAll('.v-expansion-panel').length === 0;
                }
                function headerText(panel) {
                    const header = ownHeader(panel);
                    return ((header && header.innerText) || '').trim().replace(/\\s+/g, ' ');
                }
                function parseRemain(text) {
                    const m = String(text || '').match(/剩餘\\s*[:：]?\\s*(\\d+)/);
                    return m ? parseInt(m[1], 10) : null;
                }
                function remainOf(panel) {
                    const header = ownHeader(panel);
                    const small = header && header.querySelector('small.ml-1, .remain-tag');
                    return small ? parseRemain(small.textContent) : parseRemain(headerText(panel));
                }
                function closestBtn(el) { return el ? (el.closest('button') || el) : null; }
                function plusBtn(panel) {
                    const icon = panel && (panel.querySelector('.count-button .mdi-plus') || panel.querySelector('.mdi-plus'));
                    return closestBtn(icon);
                }
                function minusBtn(panel) {
                    const icon = panel && (panel.querySelector('.count-button .mdi-minus') || panel.querySelector('.mdi-minus'));
                    return closestBtn(icon);
                }
                function isLimited(btn) {
                    if (!btn) return true;
                    if (btn.disabled) return true;
                    const limit = String(btn.getAttribute('data-limit') || '').toLowerCase();
                    if (limit === 'true' || limit === '1') return true;
                    const count = parseInt(btn.getAttribute('data-count') || '', 10);
                    return Number.isFinite(count) && count <= 0;
                }
                function readCount(panel) {
                    const box = panel && panel.querySelector('.count-button');
                    if (!box) return 0;
                    const mid = Array.from(box.children).find((el) => el.tagName === 'DIV');
                    const n = parseInt(String((mid && mid.textContent) || box.textContent || '').replace(/[^0-9]/g, ''), 10);
                    return Number.isFinite(n) ? n : 0;
                }
                function findLeaf(name) {
                    const leafs = Array.from(document.querySelectorAll('.v-expansion-panel')).filter(isLeaf);
                    return leafs.find((p) => headerText(p) === name) || null;
                }
                const actives = Array.from(document.querySelectorAll('.v-expansion-panel--active'));
                let leaf = actives.filter((p) => isLeaf(p)).pop() || actives[actives.length - 1];
                if (!leaf) return {success: false};
                const name = headerText(leaf);
                const remain = remainOf(leaf);
                let target = want;
                if (remain === 0) return {success: false, message: 'short-stock', remain: 0, selected: name};
                if (remain !== null && remain < want) {
                    if (requireExact) return {success: false, message: 'short-stock', remain: remain, selected: name, wanted: want};
                    target = remain;
                }
                let qty = readCount(leaf);
                for (let i = 0; i < 12 && qty < target; i++) {
                    const plus = plusBtn(leaf);
                    if (!plus || isLimited(plus)) break;
                    plus.click();
                    leaf = findLeaf(name) || leaf;
                    const next = readCount(leaf);
                    if (next <= qty) break;
                    qty = next;
                }
                if (qty < 1) return {success: false, selected: name, remain: remain};
                if (qty < want && requireExact) {
                    return {success: false, message: 'short-stock', selected: name, remain: remain == null ? qty : remain, quantity: qty};
                }
                return {
                    success: true,
                    clicked: true,
                    selected: name,
                    quantity: qty,
                    remain: remain,
                    wanted: want,
                    reduced: qty < want,
                };
                """,
                int(quantity),
                bool(require_exact_quantity),
            )
            if isinstance(last, dict) and last.get("success"):
                return last
        return last if isinstance(last, dict) else {"success": False}

    def exclusive_code_field(self) -> Dict[str, Any]:
        """官方優先購：`.exclusive-code` 區塊，或 placeholder / 標籤含遠傳優先購序號。"""
        result = self.execute_js(
            """
            function visible(el) {
                if (!el || el.disabled) return false;
                const style = window.getComputedStyle(el);
                const box = el.getBoundingClientRect();
                if (style.visibility === 'hidden' || style.display === 'none') return false;
                if (Number(style.opacity) === 0) return false;
                return box.width >= 2 && box.height >= 2;
            }

            function typeOk(el) {
                const t = String(el.type || 'text').toLowerCase();
                return t === 'text' || t === 'search' || t === '';
            }

            function looksLikeCode(text) {
                const s = String(text || '');
                return s.includes('遠傳優先購') || s.includes('優先購序號');
            }

            function pack(input, where) {
                const box = input.closest('.exclusive-code') || input.closest('.v-input') || input.parentElement;
                return {
                    found: 1,
                    where: where,
                    placeholder: input.placeholder || '',
                    label: box ? String(box.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 40) : '',
                };
            }

            const official = document.querySelector('.exclusive-code');
            if (official) {
                const input = official.querySelector('input');
                if (input && typeOk(input) && visible(input)) return pack(input, 'exclusive-code');
            }

            const inputs = Array.from(document.querySelectorAll('input')).filter((el) => typeOk(el) && visible(el));
            for (const input of inputs) {
                const box = input.closest('.exclusive-code, .v-input, .v-text-field, .v-form, label') || input.parentElement;
                const text = [
                    (box && box.innerText) || '',
                    input.placeholder || '',
                    input.getAttribute('aria-label') || '',
                ].join(' ');
                if (looksLikeCode(text)) return pack(input, 'placeholder');
            }
            return {found: 0};
            """
        )
        return result if isinstance(result, dict) else {"found": 0}

    def has_exclusive_code_field(self) -> bool:
        return bool(self.exclusive_code_field().get("found"))

    def fill_exclusive_code(self, code: str) -> bool:
        """只填官方優先購序號欄。沒有 `.exclusive-code` 就略過。"""
        if not code or not code.strip():
            return False
        payload = code.strip()
        last: Dict[str, Any] = {}
        for _ in range(8):
            last = self._fill_exclusive_code_once(payload)
            if last.get("filled"):
                logger.info("已填入購票序號（輸入框 %s）", last.get("where") or "exclusive-code")
                return True
            if last.get("reason") == "no-field":
                break
            self.wait_seconds(0.15)
        logger.debug("頁面上沒有可填的購票序號輸入框：%s", last.get("reason") or "no-input")
        return False

    def _fill_exclusive_code_once(self, code: str) -> Dict[str, Any]:
        result = self.execute_js(
            """
            const code = arguments[0];

            function visible(el) {
                if (!el || el.disabled || el.readOnly) return false;
                const style = window.getComputedStyle(el);
                const box = el.getBoundingClientRect();
                if (style.visibility === 'hidden' || style.display === 'none') return false;
                if (Number(style.opacity) === 0) return false;
                return box.width >= 2 && box.height >= 2;
            }

            function typeOk(el) {
                const t = String(el.type || 'text').toLowerCase();
                return t === 'text' || t === 'search' || t === '';
            }

            function looksLikeCode(text) {
                const s = String(text || '');
                return s.includes('遠傳優先購') || s.includes('優先購序號');
            }

            function setValue(input, value) {
                input.focus();
                const desc = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                if (desc && desc.set) desc.set.call(input, value);
                else input.value = value;
                input.dispatchEvent(new Event('input', {bubbles: true}));
                input.dispatchEvent(new Event('change', {bubbles: true}));
            }

            function pickInput() {
                const official = document.querySelector('.exclusive-code');
                if (official) {
                    const input = official.querySelector('input');
                    if (input && typeOk(input) && visible(input)) {
                        return {input: input, where: 'exclusive-code'};
                    }
                    return null;
                }
                const inputs = Array.from(document.querySelectorAll('input')).filter((el) => typeOk(el) && visible(el));
                for (const input of inputs) {
                    const box = input.closest('.v-input, .v-text-field, .v-form, label') || input.parentElement;
                    const text = [
                        (box && box.innerText) || '',
                        input.placeholder || '',
                        input.getAttribute('aria-label') || '',
                    ].join(' ');
                    if (looksLikeCode(text)) return {input: input, where: 'placeholder'};
                }
                return null;
            }

            const picked = pickInput();
            if (!picked) return {filled: 0, reason: 'no-field'};
            setValue(picked.input, code);
            return {filled: 1, where: picked.where};
            """,
            code,
        )
        return result if isinstance(result, dict) else {"filled": 0}

    def agree_terms(self) -> bool:
        result = self.execute_js(
            """
            let checked = 0;
            const boxes = document.querySelectorAll('input[type="checkbox"]');
            for (const box of boxes) {
                if (!box.checked) {
                    box.click();
                    if (!box.checked) {
                        box.checked = true;
                        box.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }
                if (box.checked) checked += 1;
            }
            return checked;
            """
        )
        return bool(result)

    def reservation_info(self) -> Dict[str, Any]:
        """讀 Vue store 的鎖票結果。選位成功後不可再重選或重整。"""
        result = self.execute_js(
            """
            try {
                const app = document.querySelector('#app');
                const vue = app && app.__vue__;
                const reserved = vue && vue.$store && vue.$store.state.order
                    && vue.$store.state.order.currentReserved;
                const tickets = (reserved && reserved.tickets) || [];
                const seats = tickets.flatMap((t) => t.seats || []);
                const qty = tickets.reduce((sum, t) => sum + (Number(t.count) || 0), 0);
                return {
                    ok: Boolean(reserved && String(reserved.errCode) === '00' && tickets.length > 0),
                    remain: reserved ? Number(reserved.remainSecond || 0) : 0,
                    qty: qty,
                    seats: seats.length,
                };
            } catch (e) {
                return {ok: false, remain: 0, qty: 0, seats: 0};
            }
            """
        )
        return result if isinstance(result, dict) else {"ok": False, "qty": 0, "seats": 0}

    def has_hold(self) -> bool:
        info = self.reservation_info()
        return bool(info.get("ok"))

    def looks_like_area_picker(self) -> bool:
        """活動頁殘留在 /order 網址，或尚未進入購票元件。"""
        return bool(self.execute_js("return Boolean(document.querySelector('#buyTicket'));"))

    def next_enabled(self) -> bool:
        return bool(
            self.execute_js(
                """
                const deny = ['清除選擇', '更新票數', '立即購買', '登入', '登出'];
                const allow = ['下一步', '前往付款', '確認付款', '立即付款'];
                const buttons = Array.from(document.querySelectorAll('button.nextBtn, .order-footer button'));
                return buttons.some((b) => {
                    if (!b || b.disabled) return false;
                    if (b.classList.contains('disabledBtn') || b.classList.contains('v-btn--disabled')) return false;
                    if (b.classList.contains('stepNum')) return false;
                    const text = (b.innerText || '').replace(/\\s+/g, '');
                    if (!text || deny.some((d) => text.includes(d))) return false;
                    return allow.some((a) => text.includes(a));
                });
                """
            )
        )

    def click_update_ticket_count(self) -> bool:
        """點購票頁「更新票數」。未開賣、沒票時都要按。

        按下後按鈕會變成轉圈、暫時沒有文字，這次視為已在更新，不要重找失敗。
        """
        clicked = self.execute_js(
            """
            function visible(el) {
                if (!el) return false;
                const style = window.getComputedStyle(el);
                const box = el.getBoundingClientRect();
                if (style.visibility === 'hidden' || style.display === 'none') return false;
                if (Number(style.opacity) === 0) return false;
                return box.width >= 2 && box.height >= 2;
            }
            function isUpdateBtn(b) {
                if (!b || b.disabled) return false;
                if (!visible(b)) return false;
                const text = (b.innerText || '').replace(/\\s+/g, '');
                if (text.includes('更新票數')) return true;
                const isFloat = b.classList.contains('float-btn');
                const refreshing = Boolean(b.querySelector('.v-progress-circular, .mdi-refresh'));
                return isFloat && refreshing;
            }
            const buttons = Array.from(document.querySelectorAll('button.float-btn, button'));
            const btn = buttons.find(isUpdateBtn);
            if (!btn) return false;
            if (btn.querySelector('.v-progress-circular')) return true;
            btn.click();
            return true;
            """
        )
        return bool(clicked)

    def click_next(self) -> bool:
        return self.click_advance()

    def click_advance(self) -> bool:
        clicked = self.execute_js(
            """
            const deny = ['清除選擇', '更新票數', '立即購買', '登入', '登出'];
            const allow = ['下一步', '前往付款', '確認付款', '立即付款'];
            const buttons = Array.from(document.querySelectorAll('button.nextBtn, .order-footer button'));
            const btn = buttons.find((b) => {
                if (!b || b.disabled) return false;
                if (b.classList.contains('disabledBtn') || b.classList.contains('v-btn--disabled')) return false;
                if (b.classList.contains('stepNum')) return false;
                const text = (b.innerText || '').replace(/\\s+/g, '');
                if (!text || deny.some((d) => text.includes(d))) return false;
                return allow.some((a) => text.includes(a));
            });
            if (!btn) return false;
            btn.click();
            return true;
            """
        )
        if clicked:
            logger.info("已點擊下一步")
        return bool(clicked)

    def dismiss_failure_dialog(self) -> bool:
        texts = json.dumps(list(self.FAILURE_TEXTS), ensure_ascii=False)
        result = self.execute_js(
            """
            const failureTexts = arguments[0];
            const buttonTexts = ['我知道了', '知道了', '確定', 'OK', 'Ok'];
            const dialogs = document.querySelectorAll('[role="dialog"], .v-dialog, .v-dialog__content');
            for (const dialog of dialogs) {
                if (dialog.offsetParent === null) continue;
                const text = (dialog.textContent || '').trim();
                if (!failureTexts.some(t => text.includes(t))) continue;
                const buttons = dialog.querySelectorAll('button');
                for (const btn of buttons) {
                    const btnText = (btn.textContent || '').trim();
                    if (buttonTexts.some(t => btnText.includes(t))) {
                        btn.click();
                        return true;
                    }
                }
                return true;
            }
            return false;
            """,
            json.loads(texts),
        )
        return bool(result)

    def has_reached_checkout(self) -> bool:
        """是否已到付款頁。不可用注意事項內文判斷。"""
        return is_payment_url(self.current_url)

    def click_pay_or_next(self) -> bool:
        return self.click_advance()

    def select_pickup_radios(self) -> int:
        """只在確認資料頁勾取票 / 付款方式，避免動到電腦配位選項。"""
        return int(
            self.execute_js(
                """
                const keywords = ['取票', '付款', 'ibon', '超商', '信用卡', 'ATM', '虛擬帳號'];
                let clicked = 0;
                const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                const groups = {};
                for (const radio of radios) {
                    const name = radio.name || radio.id || 'anon';
                    if (!groups[name]) groups[name] = [];
                    groups[name].push(radio);
                }
                for (const list of Object.values(groups)) {
                    if (list.some((r) => r.checked)) continue;
                    const context = list.map((r) => {
                        const box = r.closest('label, .v-radio, .v-input, .col, li, div');
                        return ((box && box.innerText) || '') + (r.value || '');
                    }).join(' ');
                    if (!keywords.some((k) => context.includes(k))) continue;
                    const first = list.find((r) => !r.disabled);
                    if (!first) continue;
                    first.click();
                    clicked += 1;
                }
                return clicked;
                """
            )
            or 0
        )
