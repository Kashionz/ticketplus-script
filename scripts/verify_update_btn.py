"""Verify order-page button targeting in a real Chrome session."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from src.pages.activity_page import ActivityPage
from src.pages.order_page import OrderPage

ORDER_URL = (
    "https://ticketplus.com.tw/order/"
    "e5baf60463fccb6391ae4dcb2e314978/0e5b6ce0e4a3c1b0f4571189c11b726e"
)
OUT = ROOT / "logs" / "verify_update.json"


def probe(driver) -> dict:
    return driver.execute_script(
        """
        const buttons = Array.from(document.querySelectorAll('button')).map((b) => ({
            text: (b.innerText || '').replace(/\\s+/g, ' ').trim(),
            cls: (b.className || '').toString().slice(0, 80),
            disabled: !!b.disabled,
            visible: b.offsetParent !== null,
        })).filter((b) => b.text);

        const deny = ['清除選擇', '更新票數', '立即購買', '登入', '登出'];
        const allow = ['下一步', '前往付款', '確認付款', '立即付款'];
        const advance = buttons.find((b) => {
            if (b.disabled || !b.visible) return false;
            const text = b.text.replace(/\\s+/g, '');
            if (deny.some((d) => text.includes(d))) return false;
            return allow.some((a) => text.includes(a));
        });
        const updateBtn = Array.from(document.querySelectorAll('button')).find((b) => {
            if (b.disabled) return false;
            const style = window.getComputedStyle(b);
            const box = b.getBoundingClientRect();
            if (style.display === 'none' || style.visibility === 'hidden' || box.width < 2) return false;
            return (b.innerText || '').includes('更新票數');
        });
        const update = updateBtn ? {text: (updateBtn.innerText || '').trim()} : null;
        const activityRefresh = buttons.find((b) => {
            if (!b.visible || b.disabled) return false;
            const text = b.text.replace(/\\s+/g, '');
            if (text.includes('更新票數')) return false;
            return text === '更新' || text === '重新整理';
        });
        return {
            href: location.href,
            advanceWouldClick: advance ? advance.text : null,
            updateWouldClick: update ? update.text : null,
            activityRefreshWouldClick: activityRefresh ? activityRefresh.text : null,
            nextDisabled: buttons.some((b) => b.text.includes('下一步') && b.disabled),
        };
        """
    )


def main() -> int:
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=options)
    order = OrderPage(driver)
    activity = ActivityPage(driver)

    if "/order/" not in driver.current_url and "/confirm" not in driver.current_url.lower():
        driver.get(ORDER_URL)
        time.sleep(3)

    before = probe(driver)
    report = {
        "logged_in": order.is_logged_in(),
        "before": before,
        "clicked_update": False,
        "after": None,
        "advance_avoids_update": True,
    }

    if before.get("advanceWouldClick") and "更新票數" in (before.get("advanceWouldClick") or ""):
        report["advance_avoids_update"] = False

    # Only click 更新票數 if we are on the order page and the button exists.
    if "/order/" in driver.current_url and before.get("updateWouldClick"):
        report["clicked_update"] = order.click_update_ticket_count()
        time.sleep(2)
        report["after"] = probe(driver)

    # Confirm activity helper would not click 更新票數
    report["activity_refresh_clicked"] = False
    if "/activity/" in driver.current_url:
        report["activity_refresh_clicked"] = activity.click_partial_refresh()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT)
    print("href", before.get("href"))
    print("logged_in", report["logged_in"])
    print("advance", before.get("advanceWouldClick"))
    print("update", before.get("updateWouldClick"))
    print("clicked_update", report["clicked_update"])
    print("advance_avoids_update", report["advance_avoids_update"])
    return 0 if report["advance_avoids_update"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
