"""KktixFlow dispatch and BotEngine KKTIX guards (no Chrome)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from src.core.bot_engine import BotEngine
from src.core.kktix_flow import KktixFlow, kktix_registration_url
from src.core.kktix_select import KktixTicketRow
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


def test_wait_sale_does_not_consume_max_retries(monkeypatch):
    engine = MagicMock()
    engine.max_retries = 2
    engine.refresh_interval = 0.01
    engine.auto_agree = True
    engine.wait_for_human = False
    engine.config = _kktix_ticket()
    engine._browser_still_open.return_value = True
    engine._browser.driver = object()
    loops = {"n": 0}

    def should_stop():
        loops["n"] += 1
        return loops["n"] > 8

    engine._should_stop.side_effect = should_stop

    class FakeReg:
        def __init__(self, driver, timeout=8):
            self.current_url = "https://kktix.com/events/sbgr01/registrations/new"

        def detect_sale_state(self):
            return "not_on_sale"

        def list_rows(self):
            return [KktixTicketRow(0, "全票", "3800", "not_on_sale", purchasable=False)]

        def sale_at_epoch(self):
            return time.time() + 1000

        def sale_countdown_remaining(self):
            return 1000.0

        def is_queue(self):
            return False

        def has_recaptcha(self):
            return False

        def has_question_captcha(self):
            return False

        def open(self, url):
            return None

        def refresh(self):
            raise AssertionError("wait_sale should not F5 before sale_at")

    fake_login = MagicMock()
    fake_login.has_login_form.return_value = False
    fake_checkout = MagicMock()
    fake_checkout.has_card_field.return_value = False
    monkeypatch.setattr("src.core.kktix_flow.KktixRegistrationPage", FakeReg)
    monkeypatch.setattr("src.core.kktix_flow.KktixLoginPage", lambda *a, **k: fake_login)
    monkeypatch.setattr("src.core.kktix_flow.KktixCheckoutPage", lambda *a, **k: fake_checkout)

    assert KktixFlow(engine).run() is False
    assert loops["n"] > 4


def test_failed_quantity_and_assign_sleep(monkeypatch):
    engine = MagicMock()
    engine.max_retries = 1
    engine.refresh_interval = 0.01
    engine.auto_agree = True
    engine.wait_for_human = False
    engine.config = _kktix_ticket()
    engine._browser_still_open.return_value = True
    engine._browser.driver = object()
    engine._should_stop.return_value = False

    class FakeReg:
        def __init__(self, driver, timeout=8):
            self.current_url = "https://kktix.com/events/sbgr01/registrations/new"

        def detect_sale_state(self):
            return "on_sale"

        def list_rows(self):
            return [KktixTicketRow(0, "全票", "3800", "on_sale", purchasable=True)]

        def is_queue(self):
            return False

        def has_recaptcha(self):
            return False

        def has_question_captcha(self):
            return False

        def set_quantity(self, index, quantity):
            return False

        def has_invitation_field(self):
            return False

        def click_computer_assign(self):
            return False

        def open(self, url):
            return None

    fake_login = MagicMock()
    fake_login.has_login_form.return_value = False
    fake_checkout = MagicMock()
    fake_checkout.has_card_field.return_value = False
    monkeypatch.setattr("src.core.kktix_flow.KktixRegistrationPage", FakeReg)
    monkeypatch.setattr("src.core.kktix_flow.KktixLoginPage", lambda *a, **k: fake_login)
    monkeypatch.setattr("src.core.kktix_flow.KktixCheckoutPage", lambda *a, **k: fake_checkout)

    assert KktixFlow(engine).run() is False
    assert engine._sleep.called


def test_held_disabled_next_logs_prefill(monkeypatch):
    engine = MagicMock()
    engine.max_retries = 1
    engine.refresh_interval = 0.01
    engine.auto_agree = True
    engine.wait_for_human = False
    engine.config = _kktix_ticket()
    engine._browser_still_open.return_value = True
    engine._browser.driver = object()
    engine._should_stop.return_value = False

    class FakeReg:
        def __init__(self, driver, timeout=8):
            self.current_url = "https://kktix.com/events/sbgr01/registrations/held1"

        def detect_sale_state(self):
            return "on_sale"

        def is_queue(self):
            return False

        def has_recaptcha(self):
            return False

        def has_question_captcha(self):
            return False

        def agree_terms(self):
            return True

        def open(self, url):
            return None

    fake_login = MagicMock()
    fake_login.has_login_form.return_value = False
    fake_checkout = MagicMock()
    fake_checkout.has_card_field.return_value = False
    fake_checkout.click_advance.return_value = False
    monkeypatch.setattr("src.core.kktix_flow.KktixRegistrationPage", FakeReg)
    monkeypatch.setattr("src.core.kktix_flow.KktixLoginPage", lambda *a, **k: fake_login)
    monkeypatch.setattr("src.core.kktix_flow.KktixCheckoutPage", lambda *a, **k: fake_checkout)

    assert KktixFlow(engine).run() is False
    logged = " ".join(str(c) for c in engine._log_once.call_args_list)
    assert "kktix.com/account/prefills" in logged
