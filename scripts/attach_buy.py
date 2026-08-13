"""Attach to Windows Chrome and walk the official TicketPlus UI to /checkout."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from src.pages.activity_page import ActivityPage
from src.pages.order_page import OrderPage
from src.utils.helpers import (
    extract_event_id,
    is_activity_url,
    is_confirm_url,
    is_order_url,
    is_payment_url,
)

LOG = ROOT / "logs" / "attach_buy.log"
TEST_URL = "https://ticketplus.com.tw/activity/4b47b5360d42451f65704664c40b1c72"


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = msg.rstrip() + "\n"
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line)
    try:
        print(line, end="", flush=True)
    except UnicodeEncodeError:
        print(line.encode("utf-8", "replace").decode("utf-8"), end="", flush=True)


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=options)
    activity = ActivityPage(driver)
    order = OrderPage(driver)
    event_id = extract_event_id(TEST_URL)
    priorities = ["全區", "預售票"]
    quantity = 1
    log(f"url={driver.current_url}")
    log(f"logged_in={activity.is_logged_in()}")
    if not activity.is_logged_in():
        log("ERROR: 這個除錯用 Chrome 尚未登入")
        return 1

    if not is_activity_url(driver.current_url):
        activity.open(TEST_URL)
        time.sleep(1)

    for step in range(40):
        url = driver.current_url
        log(f"[{step}] {url}")
        if is_payment_url(url):
            log("SUCCESS: 已到達付款頁，停止自動化")
            return 0
        if activity.has_recaptcha():
            log("WAIT: 出現 reCAPTCHA，請在瀏覽器完成後再跑一次")
            return 2
        if activity.is_in_queue():
            log("QUEUE: 官方排隊中，等待 2 秒")
            time.sleep(2)
            continue

        if is_activity_url(url):
            activity.wait_vue_ready(timeout=6)
            activity.dismiss_popups()
            opened = activity.try_open_session(event_id or "", "", [])
            log(f"  click session={opened}")
            time.sleep(1.2)
            continue

        if is_order_url(url) or is_confirm_url(url):
            if order.has_hold() or is_confirm_url(url):
                hold = order.reservation_info()
                log(f"  hold={hold}")
                if order.has_loading_overlay():
                    order.wait_loading_overlay(timeout=12)
                    continue
                clicked = order.click_advance()
                log(f"  advance={clicked}")
                time.sleep(1.2)
                continue
            order.wait_vue_ready(timeout=8)
            if order.dismiss_failure_dialog():
                log("  dismissed failure dialog")
                time.sleep(0.8)
                continue
            selected = order.select_area_and_quantity(priorities, quantity)
            log(f"  select area={selected}")
            if not selected:
                time.sleep(1)
                continue
            clicked = order.click_advance()
            log(f"  next={clicked}")
            time.sleep(1.2)
            continue

        log("  unexpected page, stay and inspect")
        time.sleep(1.5)

    log(f"FAILED: 未到付款頁，最後停在 {driver.current_url}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
