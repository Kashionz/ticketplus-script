import time
from datetime import datetime

import pytest
from mock.catalog import mock_kktix_url
from mock.server import start_mock_server
from src.core.browser import BrowserManager
from src.pages.kktix.registration_page import KktixRegistrationPage
from src.utils.helpers import taipei_tz


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
        assert checkout.has_seat_confirm_ui()
        assert checkout.confirm_assigned_seats() == "done"
        time.sleep(0.2)
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


def test_set_quantity_on_official_plus_minus_markup(tmp_path):
    server, _ = start_mock_server(port=18789)
    browser = None
    try:
        browser = _start_browser(tmp_path, "qty-official")
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        page = KktixRegistrationPage(driver)
        page.open(mock_kktix_url(port=18789) + "?scenario=happy")
        time.sleep(0.2)
        driver.execute_script(
            """
            document.getElementById('app').innerHTML = `
              <div id="registrationsNewApp">
                <div class="display-table-row">
                  <div>全票</div>
                  <div>TWD$3800</div>
                  <div class="ticket-quantity">
                    <a href="javascript:void(0)" class="minus">-</a>
                    <input ng-model="ticket.quantity" value="0">
                    <a href="javascript:void(0)" class="plus">+</a>
                  </div>
                </div>
              </div>`;
            const row = document.querySelector('.display-table-row');
            const input = row.querySelector('input');
            row.querySelector('.plus').addEventListener('click', () => {
              input.value = String(Number(input.value || 0) + 1);
            });
            row.querySelector('.minus').addEventListener('click', () => {
              input.value = String(Math.max(0, Number(input.value || 0) - 1));
            });
            """
        )
        assert page.set_quantity(0, 2)
        assert driver.execute_script("return document.querySelector('input').value") == "2"
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()


def test_confirm_assigned_seats_clicks_done(tmp_path):
    server, _ = start_mock_server(port=18788)
    browser = None
    try:
        browser = _start_browser(tmp_path, "seat-confirm")
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        from src.pages.kktix.checkout_page import KktixCheckoutPage

        driver.get("http://127.0.0.1:18788/events/mock-kktix/registrations/new?scenario=happy")
        time.sleep(0.2)
        driver.execute_script(
            """
            document.getElementById('app').innerHTML = `
              <div class="btn-group-for-seat">
                <button type="button" class="btn btn-primary">確認座位 <span class="badge">2</span></button>
                <div class="dropdown-block">
                  <a href="javascript:void(0)" class="btn btn-primary" ng-click="done()">完成選位</a>
                  <ul class="ticket-list">
                    <li class="ticket"><span class="ticket-seat">全區 13排 33號</span></li>
                    <li class="ticket"><span class="ticket-seat">全區 13排 34號</span></li>
                  </ul>
                </div>
              </div>`;
            window.__seatDone = 0;
            document.querySelector('[ng-click="done()"]').addEventListener('click', () => { window.__seatDone = 1; });
            """
        )
        checkout = KktixCheckoutPage(driver)
        assert checkout.has_seat_confirm_ui()
        assert checkout.confirm_assigned_seats() == "done"
        assert driver.execute_script("return window.__seatDone") == 1
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()


def test_disabled_computer_assign_does_not_click_next(tmp_path):
    server, _ = start_mock_server(port=18784)
    browser = None
    try:
        browser = _start_browser(tmp_path, "assign-disabled")
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        page = KktixRegistrationPage(driver)
        page.open(mock_kktix_url(port=18784) + "?scenario=happy")
        time.sleep(0.4)
        driver.execute_script(
            """
            const auto = document.querySelector('[data-act="auto-seat"]');
            auto.disabled = true;
            window.__nextClicked = false;
            window.__autoClicked = false;
            document.querySelector('[data-act="next"]').addEventListener('click', () => {
                window.__nextClicked = true;
            }, true);
            auto.addEventListener('click', () => { window.__autoClicked = true; }, true);
            """
        )
        assert page.click_computer_assign() is False
        flags = driver.execute_script("return {next: window.__nextClicked, auto: window.__autoClicked};")
        assert flags == {"next": False, "auto": False}
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()


def test_list_rows_visible_plus_and_datetime_not_on_sale(tmp_path):
    server, _ = start_mock_server(port=18785)
    browser = None
    try:
        browser = _start_browser(tmp_path, "rows")
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        page = KktixRegistrationPage(driver)
        page.open(mock_kktix_url(port=18785) + "?scenario=happy")
        time.sleep(0.3)
        driver.execute_script(
            """
            document.getElementById('app').innerHTML = `
              <div id="registrationsNewApp">
                <div class="display-table-row" data-ticket-row>
                  <span>票種</span><span>價格</span><span>狀態</span>
                </div>
                <div class="display-table-row" data-ticket-row data-name="全票" data-price="3800">
                  <span>全票</span>
                  <span>TWD$3800</span>
                  <span>2026/09/05 12:00</span>
                  <span class="qty" hidden>
                    <button type="button" data-act="plus" hidden>+</button>
                    <input class="ticket-quantity" hidden value="0">
                  </span>
                </div>
                <div class="display-table-row" data-ticket-row data-name="全票" data-price="3600">
                  <span>全票</span>
                  <span>TWD$3600</span>
                  <span>熱賣中</span>
                  <span class="qty">
                    <button type="button" data-act="plus">+</button>
                    <input class="ticket-quantity" value="0">
                  </span>
                </div>
              </div>`;
            """
        )
        time.sleep(0.1)
        rows = page.list_rows()
        by_price = {r.price_text: r for r in rows if r.price_text}
        assert by_price["3800"].status == "not_on_sale"
        assert by_price["3800"].purchasable is False
        assert by_price["3600"].status == "on_sale"
        assert any(r.status == "unknown" for r in rows)
        sale_at = page.sale_at_epoch()
        expected = datetime(2026, 9, 5, 12, 0, tzinfo=taipei_tz()).timestamp()
        assert sale_at == pytest.approx(expected, abs=1)
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()


def test_sale_at_epoch_parses_countdown_without_data_attr(tmp_path):
    server, _ = start_mock_server(port=18786)
    browser = None
    try:
        browser = _start_browser(tmp_path, "sale-text")
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        page = KktixRegistrationPage(driver)
        page.open(mock_kktix_url(port=18786) + "?scenario=happy")
        time.sleep(0.3)
        driver.execute_script(
            """
            document.getElementById('app').innerHTML = `
              <div id="registrationsNewApp">
                <div>尚未開賣 4秒後開賣</div>
                <div class="display-table-row" data-ticket-row data-name="全票" data-price="3800">
                  <span>全票</span><span>TWD$3800</span><span>尚未開賣 4秒後開賣</span>
                </div>
              </div>`;
            """
        )
        before = time.time()
        sale_at = page.sale_at_epoch()
        remaining = page.sale_countdown_remaining()
        assert remaining == 4
        assert sale_at is not None
        assert abs(sale_at - (before + 4)) < 2
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()
