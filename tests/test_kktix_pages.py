import time
import pytest
from mock.catalog import mock_kktix_url
from mock.server import start_mock_server
from src.core.browser import BrowserManager
from src.pages.kktix.registration_page import KktixRegistrationPage


def test_registration_page_reads_rows_and_clicks_auto_seat(tmp_path):
    server, _ = start_mock_server(port=18768)
    browser = None
    try:
        browser = BrowserManager(
            headless=True,
            user_data_dir=str(tmp_path / "c"),
            prefer_windows_chrome=False,
            page_load_timeout=20,
        )
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        page = KktixRegistrationPage(driver)
        page.open(mock_kktix_url(port=18768) + "?scenario=happy")
        time.sleep(0.4)
        rows = page.list_rows()
        assert any(r.price_text.find("3800") >= 0 for r in rows)
        assert any("愛心" in r.name for r in rows)
        assert page.set_quantity(0, 2)
        assert page.agree_terms()
        assert page.click_computer_assign()
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()


def _start_browser(tmp_path, name: str = "c") -> BrowserManager:
    return BrowserManager(
        headless=True,
        user_data_dir=str(tmp_path / name),
        prefer_windows_chrome=False,
        page_load_timeout=20,
    )


def test_login_page_fills_mock_form(tmp_path):
    server, _ = start_mock_server(port=18780)
    browser = None
    try:
        browser = _start_browser(tmp_path, "login")
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        from src.pages.kktix.login_page import KktixLoginPage

        page = KktixLoginPage(driver)
        page.navigate_to("http://127.0.0.1:18780/users/sign_in")
        time.sleep(0.4)
        assert page.has_login_form()
        assert not page.is_logged_in()
        assert page.fill_and_submit("user@example.com", "mock-pass")
        deadline = time.time() + 8
        while time.time() < deadline and not page.is_logged_in():
            time.sleep(0.2)
        assert page.is_logged_in()
        assert not page.has_login_form()
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()


def test_checkout_and_sale_helpers_on_mock(tmp_path):
    server, _ = start_mock_server(port=18781)
    browser = None
    try:
        browser = _start_browser(tmp_path, "checkout")
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        from src.pages.kktix.checkout_page import KktixCheckoutPage

        origin = "http://127.0.0.1:18781"
        reg = KktixRegistrationPage(driver)
        reg.open(mock_kktix_url(port=18781) + "?scenario=presale&saleAfter=8")
        time.sleep(0.4)
        assert reg.detect_sale_state() == "not_on_sale"
        sale_at = reg.sale_at_epoch()
        assert sale_at is not None and sale_at > 0
        assert not reg.has_question_captcha()
        assert not reg.has_invitation_field()
        checkout = KktixCheckoutPage(driver)
        checkout.dismiss_seat_notice()
        assert not checkout.has_card_field()

        driver.get(origin + "/events/mock-kktix/registrations/held1")
        time.sleep(0.4)
        checkout.dismiss_seat_notice()
        assert checkout.click_advance()
        deadline = time.time() + 8
        while time.time() < deadline and "/pay" not in (driver.current_url or ""):
            time.sleep(0.2)
        assert "/pay" in driver.current_url
        assert checkout.has_card_field()
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()
