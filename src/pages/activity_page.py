"""活動頁：選場次並進入購票。"""

from __future__ import annotations

import json
import logging
from typing import List, Optional

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from urllib.parse import urlparse

from .base_page import BasePage
from ..utils.helpers import any_keyword_in, extract_event_id, is_mock_url, keyword_matches

logger = logging.getLogger("ticket-helper")


class ActivityPage(BasePage):
    BUY_TICKET = (By.CSS_SELECTOR, "div#buyTicket")
    SESSION_ITEM = (By.CSS_SELECTOR, "div#buyTicket div.sesstion-item")
    NEXT_BTN = (By.CSS_SELECTOR, "button.nextBtn")
    FLOAT_REFRESH = (By.CSS_SELECTOR, "button.float-btn")

    BUYABLE_TEXTS = ("立即購", "立即購買")
    NOT_YET_TEXTS = ("尚未開售", "尚未開賣", "即將開賣")
    SOLD_OUT_TEXTS = ("銷售一空", "已售完", "售完")

    def __init__(self, driver: WebDriver, timeout: int = 8):
        super().__init__(driver, timeout)

    def open(self, url: str) -> bool:
        logger.info("開啟活動頁: %s", url)
        return self.navigate_to(url)

    def wait_vue_ready(self, timeout: float = 8.0) -> bool:
        deadline = timeout
        interval = 0.15
        elapsed = 0.0
        while elapsed < deadline:
            ready = self.execute_js(
                """
                const root = document.querySelector('.eventClass') || document.querySelector('#buyTicket');
                const items = document.querySelectorAll('div#buyTicket div.sesstion-item, button.nextBtn');
                const spinner = document.querySelector('#buyTicket .v-progress-circular');
                return Boolean(root) && items.length > 0 && !spinner;
                """
            )
            if ready:
                return True
            self.wait_seconds(interval)
            elapsed += interval
        return False

    def dismiss_popups(self) -> None:
        self.execute_js(
            """
            const buttons = Array.from(document.querySelectorAll('button, .v-btn'));
            for (const btn of buttons) {
                const text = (btn.innerText || '').trim();
                if (['我知道了', '知道了', '確定', '關閉', 'OK'].some(t => text.includes(t))) {
                    const dialog = btn.closest('[role="dialog"], .v-dialog');
                    if (dialog) btn.click();
                }
            }
            const closeIcon = document.querySelector('div[role="dialog"] i.v-icon.mdi-close, .v-dialog button.primary-1');
            if (closeIcon) closeIcon.click();
            """
        )

    def list_session_summaries(self) -> List[str]:
        result = self.execute_js(
            """
            const nodes = Array.from(document.querySelectorAll('div#buyTicket div.sesstion-item, div#buyTicket div.row.pa-4'));
            return nodes.map(n => (n.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean);
            """
        )
        return result or []

    def try_open_session(
        self,
        event_id: str,
        target_session: str,
        exclude_keywords: List[str],
    ) -> bool:
        """優先走官方頁面的立即購按鈕；失敗時再用 Vue 資料導向 /order。"""
        if self._click_session_button(target_session, exclude_keywords):
            return True
        return self._navigate_via_vue(event_id, target_session, exclude_keywords)

    def _click_session_button(self, target_session: str, exclude_keywords: List[str]) -> bool:
        payload = json.dumps(
            {
                "keyword": target_session or "",
                "exclude": exclude_keywords or [],
                "buyable": list(self.BUYABLE_TEXTS),
                "notYet": list(self.NOT_YET_TEXTS),
                "soldOut": list(self.SOLD_OUT_TEXTS),
            },
            ensure_ascii=False,
        )
        result = self.execute_js(
            """
            const cfg = arguments[0];
            const normalize = (s) => (s || '').replace(/[\\s\\u3000]/g, '').toLowerCase();
            const keyword = normalize(cfg.keyword);
            const exclude = (cfg.exclude || []).map(normalize).filter(Boolean);
            let containers = Array.from(document.querySelectorAll('div#buyTicket div.sesstion-item'));
            if (!containers.length) {
                containers = Array.from(document.querySelectorAll('div#buyTicket div.row.pa-4'));
            }
            const usable = [];
            for (const box of containers) {
                const text = (box.innerText || '');
                const norm = normalize(text);
                if (exclude.some(k => k && norm.includes(k))) continue;
                const sold = cfg.soldOut.some(k => text.includes(k));
                const buyBtn = box.querySelector('button.nextBtn, button');
                if (!buyBtn) continue;
                const btnText = buyBtn.innerText || '';
                const buyable = cfg.buyable.some(k => btnText.includes(k) || text.includes(k));
                if (sold || !buyable) continue;
                if (keyword && !norm.includes(keyword)) continue;
                usable.push({box, buyBtn, text});
            }
            if (!usable.length) return {ok: false, reason: 'no-buyable'};
            usable[0].buyBtn.click();
            return {ok: true, text: usable[0].text.slice(0, 80)};
            """,
            json.loads(payload),
        )
        if isinstance(result, dict) and result.get("ok"):
            logger.info("已點選場次: %s", result.get("text"))
            return True
        return False

    def _navigate_via_vue(
        self,
        event_id: str,
        target_session: str,
        exclude_keywords: List[str],
    ) -> bool:
        data = self.execute_js(
            """
            const el = document.querySelector('.eventClass');
            if (!el || !el.__vue__) return null;
            const sessions = el.__vue__.$data.sessions || [];
            return sessions.map(s => ({
                sessionId: s.sessionId || '',
                name: s.name || '',
                date: s.date || '',
                finished: Boolean(s.loadingStatusFinished)
            }));
            """
        )
        if not data:
            return False
        chosen = None
        for item in data:
            blob = f"{item.get('name', '')} {item.get('date', '')}"
            if any_keyword_in(blob, exclude_keywords):
                continue
            if target_session and not keyword_matches(blob, target_session):
                continue
            if item.get("sessionId"):
                chosen = item
                break
        if not chosen and not target_session:
            for item in data:
                blob = f"{item.get('name', '')} {item.get('date', '')}"
                if not any_keyword_in(blob, exclude_keywords) and item.get("sessionId"):
                    chosen = item
                    break
        if not chosen:
            return False
        session_id = chosen["sessionId"]
        current = urlparse(self.current_url)
        if is_mock_url(self.current_url) and current.scheme and current.netloc:
            base = f"{current.scheme}://{current.netloc}"
            query = f"?{current.query}" if current.query else ""
        else:
            base = self.BASE_URL
            query = ""
        url = f"{base}/order/{event_id}/{session_id}{query}"
        logger.info("以場次資料進入購票頁: %s (%s)", chosen.get("name"), session_id)
        return self.navigate_to(url)

    def has_not_on_sale(self) -> bool:
        text = self.page_text()
        return any(token in text for token in self.NOT_YET_TEXTS)

    def has_sold_out_only(self) -> bool:
        summaries = self.list_session_summaries()
        if not summaries:
            return False
        return all(any(token in s for token in self.SOLD_OUT_TEXTS) for s in summaries)

    def click_partial_refresh(self) -> bool:
        """只點活動頁的局部更新，不要點到購票頁的「更新票數」。"""
        return bool(
            self.execute_js(
                """
                const buttons = Array.from(document.querySelectorAll('button.float-btn, button'));
                const btn = buttons.find((b) => {
                    if (!b || b.disabled) return false;
                    const style = window.getComputedStyle(b);
                    const box = b.getBoundingClientRect();
                    if (style.visibility === 'hidden' || style.display === 'none' || box.width < 2 || box.height < 2) return false;
                    const text = (b.innerText || '').replace(/\\s+/g, '');
                    if (text.includes('更新票數')) return false;
                    return text === '更新' || text === '重新整理';
                });
                if (!btn) return false;
                btn.click();
                return true;
                """
            )
        )

    def refresh_for_sale(self, full_reload: bool = False) -> None:
        if not full_reload and self.click_partial_refresh():
            return
        self.refresh()

    def current_event_id(self) -> Optional[str]:
        return extract_event_id(self.current_url)
