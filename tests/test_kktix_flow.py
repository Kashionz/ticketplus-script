"""KktixFlow dispatch and BotEngine KKTIX guards (no Chrome)."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.core.bot_engine import BotEngine
from src.core.kktix_flow import kktix_registration_url
from src.models.ticket_config import TicketConfig


def _kktix_ticket() -> TicketConfig:
    return TicketConfig(
        activity_url="https://kktix.com/events/sbgr01/registrations/new",
        quantity=2,
        area_priorities=["3800"],
    )


def test_kktix_registration_url_normalizes_event_page():
    assert (
        kktix_registration_url("https://kktix.com/events/sbgr01/registrations/new")
        == "https://kktix.com/events/sbgr01/registrations/new"
    )
    assert (
        kktix_registration_url("https://binliveco.kktix.cc/events/sbgr01")
        == "https://kktix.com/events/sbgr01/registrations/new"
    )
    mock = "http://127.0.0.1:18769/events/mock-kktix/registrations/new?scenario=happy"
    assert kktix_registration_url(mock) == mock
    assert (
        kktix_registration_url("http://127.0.0.1:18769/events/mock-kktix?scenario=happy")
        == "http://127.0.0.1:18769/events/mock-kktix/registrations/new?scenario=happy"
    )


def test_execute_dispatches_to_kktix_flow(monkeypatch):
    bot = BotEngine(config=_kktix_ticket(), prefer_windows_chrome=False)
    ran = []

    class FakeFlow:
        def __init__(self, engine):
            ran.append(engine)

        def run(self):
            ran.append("run")
            return True

    monkeypatch.setattr("src.core.kktix_flow.KktixFlow", FakeFlow)
    assert bot._execute() is True
    assert ran[0] is bot
    assert ran[1] == "run"


def test_prepare_parallel_windows_forbidden_for_kktix():
    bot = BotEngine(config=_kktix_ticket(), prefer_windows_chrome=False, parallel_windows=3)
    bot._browser = MagicMock()
    bot._browser.is_running = True
    bot._browser.export_cookies.return_value = [{"name": "user", "value": "1"}]
    bot._prepare_parallel_windows()
    assert bot._extra_engines == []
    bot._browser.export_cookies.assert_not_called()
