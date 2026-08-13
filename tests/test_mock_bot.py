"""用本機模擬站驗證搶票流程。需要本機 Chrome。"""

from __future__ import annotations

import time
from contextlib import contextmanager

import pytest

from mock.catalog import EVENT_ID, mock_activity_url
from mock.server import start_mock_server
from src.core.bot_engine import BotEngine, BotStatus
from src.models.ticket_config import TicketConfig

PORT = 18766


@contextmanager
def mock_site(port: int = PORT):
    server, _thread = start_mock_server(port=port)
    try:
        yield mock_activity_url(port=port)
    finally:
        server.shutdown()
        server.server_close()


def _wait_bot(bot: BotEngine, timeout: float = 50.0) -> BotStatus:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bot.state.status in {BotStatus.SUCCESS, BotStatus.FAILED, BotStatus.ERROR, BotStatus.STOPPED}:
            return bot.state.status
        time.sleep(0.25)
    return bot.state.status


def _make_bot(url: str, tmp_path, **kwargs) -> BotEngine:
    ticket = TicketConfig(
        activity_url=url,
        target_session="9/19",
        quantity=2,
        area_priorities=kwargs.pop("area_priorities", ["VIP3區", "VIP4區"]),
        fallback_first_available=kwargs.pop("fallback_first_available", False),
        exclusive_code=kwargs.pop("exclusive_code", ""),
        account="0900000000",
        password="mock-pass",
    )
    return BotEngine(
        config=ticket,
        browser_headless=True,
        refresh_interval=250,
        max_retries=80,
        auto_agree=True,
        wait_for_human=False,
        user_data_dir=str(tmp_path / "chrome"),
        prefer_windows_chrome=False,
        page_load_timeout=20,
    )


def test_bot_reaches_checkout_on_happy_mock(tmp_path):
    try:
        with mock_site() as url:
            bot = _make_bot(url + "?scenario=happy", tmp_path)
            assert bot.start()
            deadline = time.time() + 15
            while time.time() < deadline and not bot.is_waiting_for_start():
                if bot.state.status == BotStatus.ERROR:
                    pytest.skip(f"無法啟動 Chrome: {bot.state.error}")
                time.sleep(0.1)
            if not bot.is_waiting_for_start() and bot.state.status == BotStatus.ERROR:
                pytest.skip(f"無法啟動 Chrome: {bot.state.error}")
            bot.trigger_start_booking()
            status = _wait_bot(bot)
            bot.stop(close_browser=True)
            assert status == BotStatus.SUCCESS, bot.state.message
    except Exception as exc:
        if "chrome" in str(exc).lower() or "chromedriver" in str(exc).lower():
            pytest.skip(f"本機沒有可用的 Chrome: {exc}")
        raise


def test_bot_waits_presale_then_buys_after_update(tmp_path):
    try:
        with mock_site(port=18767) as url:
            bot = _make_bot(url + "?scenario=presale&saleAfter=1", tmp_path)
            assert bot.start()
            deadline = time.time() + 15
            while time.time() < deadline and not bot.is_waiting_for_start():
                if bot.state.status == BotStatus.ERROR:
                    pytest.skip(f"無法啟動 Chrome: {bot.state.error}")
                time.sleep(0.1)
            bot.trigger_start_booking()
            status = _wait_bot(bot, timeout=55)
            message = bot.state.message
            bot.stop(close_browser=True)
            assert status == BotStatus.SUCCESS, message
    except Exception as exc:
        if "chrome" in str(exc).lower() or "chromedriver" in str(exc).lower():
            pytest.skip(f"本機沒有可用的 Chrome: {exc}")
        raise


def test_bot_fallback_when_priority_sold_out(tmp_path):
    try:
        with mock_site(port=18768) as url:
            bot = _make_bot(
                url + "?scenario=priority-soldout",
                tmp_path,
                area_priorities=["VIP3區", "VIP4區"],
                fallback_first_available=True,
            )
            assert bot.start()
            deadline = time.time() + 15
            while time.time() < deadline and not bot.is_waiting_for_start():
                if bot.state.status == BotStatus.ERROR:
                    pytest.skip(f"無法啟動 Chrome: {bot.state.error}")
                time.sleep(0.1)
            bot.trigger_start_booking()
            status = _wait_bot(bot, timeout=55)
            message = bot.state.message
            bot.stop(close_browser=True)
            assert status == BotStatus.SUCCESS, message
    except Exception as exc:
        if "chrome" in str(exc).lower() or "chromedriver" in str(exc).lower():
            pytest.skip(f"本機沒有可用的 Chrome: {exc}")
        raise
