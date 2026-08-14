#!/usr/bin/env python3
"""TicketPlus 購票助手進入點。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TicketPlus 購票助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  python -m src.main
  python -m src.main inspect
  python -m src.main open-chrome
  python -m src.main mock
  python -m src.main --cli --attach 127.0.0.1:9222
        """,
    )
    parser.add_argument("command", nargs="?", default="", help="inspect / open-chrome / mock")
    parser.add_argument("--port", type=int, default=8765, help="模擬站埠號")
    parser.add_argument("--cli", action="store_true", help="命令列模式（不開 GUI）")
    parser.add_argument("--url", type=str, help="活動網址")
    parser.add_argument("--session", type=str, default="", help="場次關鍵字，例如 9/19")
    parser.add_argument("--quantity", type=int, help="購票張數")
    parser.add_argument("--exact-quantity", action="store_true", help="一定要買到指定張數，剩餘不足就不買")
    parser.add_argument("--code", type=str, help="購票序號")
    parser.add_argument("--headless", action="store_true", help="隱藏瀏覽器")
    parser.add_argument("--attach", type=str, default="", help="接上 Windows Chrome，例如 127.0.0.1:9222")
    parser.add_argument("--config", type=str, default="config/config.yaml", help="設定檔路徑")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def run_inspect(args: argparse.Namespace) -> int:
    from src.api.event_api import fetch_event_catalog, format_catalog
    from src.utils.config import get_config
    from src.utils.helpers import extract_event_id

    url = args.url
    if not url:
        config = get_config(args.config)
        url = config.get_ticket_config().activity_url
    event_id = extract_event_id(url or "")
    if not event_id:
        print("請提供有效的 TicketPlus 活動網址")
        return 1
    catalog = fetch_event_catalog(event_id)
    print(format_catalog(catalog))
    return 0


def run_open_chrome(args: argparse.Namespace) -> int:
    from src.utils.config import get_config
    from src.utils.windows_chrome import launch_windows_chrome

    config = get_config(args.config)
    address = launch_windows_chrome(user_data_dir=config.browser_user_data_dir)
    print(f"Windows Chrome 已開啟，除錯位址: {address}")
    print("接下來請用：")
    print(f"  python -m src.main --cli --attach {address}")
    print("或把 config.yaml 的 browser.debugger_address 設成這個位址。")
    print("請先在這個視窗登入 TicketPlus，再開始搶票。")
    return 0


def run_cli(args: argparse.Namespace) -> int:
    import time

    from src.core.bot_engine import BotEngine, BotStatus
    from src.utils.config import get_config
    from src.utils.logger import init_default_logger

    init_default_logger(level="DEBUG" if args.debug else "INFO")
    config = get_config(args.config)
    ticket = config.get_ticket_config()
    if args.url:
        ticket.activity_url = args.url
    if args.session:
        ticket.target_session = args.session
    if args.quantity:
        ticket.quantity = args.quantity
    if args.exact_quantity:
        ticket.require_exact_quantity = True
    if args.code:
        ticket.exclusive_code = args.code

    errors = ticket.validate()
    if errors:
        print("設定錯誤:")
        for item in errors:
            print(f"  - {item}")
        return 1

    print("活動網址:", ticket.activity_url)
    print("場次關鍵字:", ticket.target_session or "(第一個可購場次)")
    print(
        "張數:",
        ticket.quantity,
        "（一定要指定張數）" if ticket.require_exact_quantity else "（剩餘不足改買剩餘）",
    )
    print("票區優先:", ticket.area_priorities or "(第一個可購)")
    print("購票序號:", "已設定" if ticket.exclusive_code else "(無)")
    print("開賣判斷: 購票頁票區欄位（開賣時間=未開賣；可選數量或已售完=已開賣）")
    confirm = input("瀏覽器開啟後請先登入。按 Enter 啟動，或輸入 n 取消: ").strip().lower()
    if confirm == "n":
        return 0

    bot = BotEngine(
        config=ticket,
        browser_headless=args.headless or config.browser_headless,
        refresh_interval=config.bot_refresh_interval,
        max_retries=config.bot_max_retries,
        auto_agree=config.bot_auto_agree,
        wait_for_human=config.bot_wait_for_human,
        driver_path=config.browser_driver_path,
        user_data_dir=config.browser_user_data_dir,
        window_size=config.browser_window_size,
        page_load_timeout=config.browser_page_load_timeout,
        debugger_address=args.attach or config.browser_debugger_address,
        chrome_binary=config.browser_chrome_binary,
        prefer_windows_chrome=config.browser_prefer_windows_chrome,
        parallel_windows=config.bot_parallel_windows,
    )
    bot.add_log_callback(lambda msg, level: print(f"[{level}] {msg}"))
    bot.start()
    try:
        while bot.is_waiting_for_start():
            time.sleep(0.2)
        input("登入完成後按 Enter 開始購票...")
        bot.trigger_start_booking()
        while bot.is_running:
            time.sleep(0.4)
    except KeyboardInterrupt:
        print("\n使用者中斷")
        bot.stop()
        return 1

    if bot.state.status == BotStatus.SUCCESS:
        print("已進入付款頁，請在瀏覽器完成付款。")
        return 0
    print("結束狀態:", bot.state.status.name)
    return 1


def main() -> None:
    args = parse_args()
    if args.command == "inspect":
        sys.exit(run_inspect(args))
    if args.command in {"open-chrome", "open_chrome"}:
        sys.exit(run_open_chrome(args))
    if args.command == "mock":
        from mock.server import main as run_mock

        sys.exit(run_mock(["--port", str(args.port)]))
    if args.cli:
        sys.exit(run_cli(args))
    from src.gui.main_window import run_app

    run_app()


if __name__ == "__main__":
    main()
