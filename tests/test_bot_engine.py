"""BotEngine 在瀏覽器被關掉後要能結束，讓 GUI 重新啟動。"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from src.core.bot_engine import BotEngine, BotStatus
from src.models.ticket_config import TicketConfig


def _ticket() -> TicketConfig:
    return TicketConfig(
        activity_url="https://ticketplus.com.tw/activity/af39103d211724c82069c4ab5e40e95c",
        quantity=2,
    )


def _wait_status(bot: BotEngine, status: BotStatus, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if bot.state.status == status:
            return True
        time.sleep(0.05)
    return False


def test_wait_loop_stops_when_browser_closes(monkeypatch):
    bot = BotEngine(config=_ticket(), prefer_windows_chrome=False, wait_for_human=False)
    browser = MagicMock()
    browser.is_running = True

    def fake_init() -> bool:
        bot._browser = browser
        bot._activity = MagicMock()
        bot._order = MagicMock()
        bot._login = MagicMock()
        bot._login.is_logged_in.return_value = True
        return True

    monkeypatch.setattr(bot, "_initialize", fake_init)
    assert bot.start()
    assert _wait_status(bot, BotStatus.WAITING_LOGIN)
    browser.is_running = False
    assert _wait_status(bot, BotStatus.STOPPED)
    assert bot._browser is None
    assert not bot.is_running
    assert "瀏覽器已關閉" in (bot.state.message or "")
    bot.stop(close_browser=True)


def test_looks_like_dead_browser():
    bot = BotEngine(config=_ticket(), prefer_windows_chrome=False)
    assert bot._looks_like_dead_browser(RuntimeError("invalid session id"))
    assert bot._looks_like_dead_browser(RuntimeError("no such window: target window already closed"))
    assert bot._looks_like_dead_browser(RuntimeError("chrome not reachable"))
    assert not bot._looks_like_dead_browser(RuntimeError("element not interactable"))


def test_ensure_login_pauses_and_does_not_refresh_when_logged_out():
    bot = BotEngine(config=_ticket(), prefer_windows_chrome=False)
    bot.config.account = ""
    bot.config.password = ""
    login = MagicMock()
    login.is_logged_in.return_value = False
    login.has_login_form.return_value = True
    login.current_url = "https://ticketplus.com.tw/login"
    bot._login = login
    bot._activity = MagicMock()
    assert bot._ensure_login() is True
    login.fill_and_submit.assert_not_called()
    bot._activity.open.assert_not_called()


def test_ensure_login_ready_when_already_logged_in():
    bot = BotEngine(config=_ticket(), prefer_windows_chrome=False)
    login = MagicMock()
    login.is_logged_in.return_value = True
    login.has_login_form.return_value = False
    bot._login = login
    assert bot._ensure_login() is False


def test_prepare_parallel_windows_skipped_when_count_is_one():
    bot = BotEngine(config=_ticket(), prefer_windows_chrome=False, parallel_windows=1)
    bot._browser = MagicMock()
    bot._browser.export_cookies.return_value = [{"name": "user", "value": "account=x"}]
    bot._prepare_parallel_windows()
    assert bot._extra_engines == []
    bot._browser.export_cookies.assert_not_called()


def test_declare_winner_stops_other_windows():
    bot = BotEngine(config=_ticket(), prefer_windows_chrome=False, parallel_windows=2)
    extra = MagicMock()
    extra.window_index = 2
    bot._extra_engines = [extra]
    bot._declare_winner(1)
    extra.stop.assert_called_once_with(close_browser=True)
    assert bot._winner == 1
    assert bot._extra_engines == []
    bot._declare_winner(2)
    extra.stop.assert_called_once()


def test_start_booking_without_browser_resets():
    bot = BotEngine(config=_ticket(), prefer_windows_chrome=False)
    bot._browser = MagicMock()
    bot._browser.is_running = False
    assert bot.start_booking() is False
    assert bot.state.status == BotStatus.STOPPED
    assert bot._browser is None
