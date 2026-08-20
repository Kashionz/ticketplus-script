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


def test_open_login_wait_page_survives_mock_connection_refused():
    bot = BotEngine(
        config=TicketConfig(
            activity_url="http://127.0.0.1:8765/events/mock-kktix/registrations/new",
            quantity=1,
        ),
        prefer_windows_chrome=False,
    )
    logs = []
    bot.add_log_callback(lambda msg, level: logs.append(msg))
    driver = MagicMock()
    driver.get.side_effect = RuntimeError("unknown error: net::ERR_CONNECTION_REFUSED")
    bot._browser = MagicMock()
    bot._browser.driver = driver
    bot._open_login_wait_page()
    assert any("mock.server" in msg for msg in logs)
    driver.get.assert_called()


def test_resolve_debugger_address_prefers_open_chrome(monkeypatch):
    from src.utils.windows_chrome import resolve_debugger_address

    monkeypatch.setattr("src.utils.windows_chrome.find_open_debugger", lambda port=9222: "127.0.0.1:9222")
    assert resolve_debugger_address("", False) == "127.0.0.1:9222"
    assert resolve_debugger_address("127.0.0.1:9333", False) == "127.0.0.1:9333"
    assert resolve_debugger_address("", True) == ""


def test_dismiss_rechoose_alert_cancels_not_accepts():
    from src.pages.base_page import BasePage

    alert = MagicMock()
    alert.text = "目前的訂單將先行取消，座位亦不保留，您確定要重新選票嗎？"
    driver = MagicMock()
    driver.switch_to.alert = alert
    page = BasePage(driver)
    assert page.dismiss_js_alert() == "rechoose"
    alert.dismiss.assert_called_once()
    alert.accept.assert_not_called()


def test_read_js_alert_peeks_rechoose_without_closing():
    from src.pages.base_page import BasePage

    alert = MagicMock()
    alert.text = "目前的訂單將先行取消，座位亦不保留，您確定要重新選票嗎？"
    driver = MagicMock()
    driver.switch_to.alert = alert
    page = BasePage(driver)
    assert page.read_js_alert() == "rechoose"
    alert.dismiss.assert_not_called()
    alert.accept.assert_not_called()


def test_execute_js_does_not_raise_on_unexpected_alert():
    from src.pages.base_page import BasePage

    driver = MagicMock()
    driver.execute_script.side_effect = RuntimeError(
        "Alert Text: 目前的訂單將先行取消，座位亦不保留，您確定要重新選票嗎？\n"
        "Message: unexpected alert open: {Alert text : 目前的訂單將先行取消，座位亦不保留，您確定要重新選票嗎？}"
    )
    page = BasePage(driver)
    assert page.execute_js("return 1") is None


def test_chrome_launch_hint_for_session_not_created():
    from src.core.browser import chrome_launch_hint

    hint = chrome_launch_hint(
        RuntimeError("session not created: Chrome instance exited"),
        ".chrome-profile",
    )
    assert "Chrome 啟動後立刻結束" in hint
    assert ".chrome-profile" in hint
    assert "open-chrome.bat" in hint


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


def _ready_order_bot() -> BotEngine:
    bot = BotEngine(config=_ticket(), prefer_windows_chrome=False, wait_for_human=False)
    order = MagicMock()
    order.dismiss_failure_dialog.return_value = False
    order.has_hold.return_value = False
    order.wait_for_area_widgets.return_value = True
    order.is_not_on_sale.return_value = False
    order.select_area_and_quantity.return_value = True
    order.next_enabled.return_value = True
    order.click_next.return_value = True
    order.has_exclusive_code_field.return_value = False
    order.fill_exclusive_code.return_value = True
    activity = MagicMock()
    activity.has_recaptcha.return_value = False
    activity.is_cloudflare_challenge.return_value = False
    activity.is_in_queue.return_value = False
    bot._order = order
    bot._activity = activity
    return bot


def test_process_order_fills_code_only_when_field_exists():
    bot = _ready_order_bot()
    bot.config.exclusive_code = "ArwPDDj"
    bot._order.has_exclusive_code_field.return_value = True
    assert bot._process_order() is True
    bot._order.fill_exclusive_code.assert_called_once_with("ArwPDDj")


def test_process_order_skips_code_when_field_absent():
    bot = _ready_order_bot()
    bot.config.exclusive_code = "ArwPDDj"
    assert bot._process_order() is True
    bot._order.fill_exclusive_code.assert_not_called()


def test_process_order_waits_when_field_exists_but_code_missing():
    bot = _ready_order_bot()
    bot.config.exclusive_code = ""
    bot._order.has_exclusive_code_field.return_value = True
    assert bot._process_order() is False
    bot._order.fill_exclusive_code.assert_not_called()
    bot._order.click_next.assert_not_called()


def test_process_order_passes_exact_quantity_flag():
    bot = _ready_order_bot()
    bot.config.require_exact_quantity = True
    bot.config.quantity = 2
    assert bot._process_order() is True
    kwargs = bot._order.select_area_and_quantity.call_args.kwargs
    assert kwargs["quantity"] == 2
    assert kwargs["require_exact_quantity"] is True
