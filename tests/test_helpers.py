from datetime import datetime
from pathlib import Path

from src.models.ticket_config import TicketConfig
from src.utils.helpers import (
    classify_kktix_page_alert,
    area_keyword_matches,
    clamp_parallel_windows,
    classify_area_sale_text,
    detect_platform,
    extract_event_id,
    extract_kktix_slug,
    parse_kktix_countdown_remaining,
    parse_kktix_sale_at,
    parse_remaining_count,
    resolve_buy_quantity,
    extract_session_id,
    is_activity_url,
    is_charity_ticket_name,
    is_confirm_url,
    is_kktix_held_url,
    is_kktix_login_url,
    is_kktix_payment_url,
    is_kktix_registration_url,
    is_kktix_url,
    is_login_url,
    is_mock_url,
    is_order_url,
    is_payment_url,
    is_success_url,
    keyword_matches,
    normalize_mobile,
    normalize_text,
    taipei_tz,
)

TEST_EVENT = "d1b4147aaeaa2e233f0fdc827cd55310"
TARGET_EVENT = "af39103d211724c82069c4ab5e40e95c"


def test_extract_event_id_from_activity_url():
    url = f"https://ticketplus.com.tw/activity/{TARGET_EVENT}"
    assert extract_event_id(url) == TARGET_EVENT


def test_extract_event_id_from_order_url():
    url = f"https://ticketplus.com.tw/order/{TARGET_EVENT}/d08e405792a3d35fa5716eb831a1065a"
    assert extract_event_id(url) == TARGET_EVENT
    assert extract_session_id(url) == "d08e405792a3d35fa5716eb831a1065a"


def test_extract_event_id_trailing_slash():
    url = f"https://ticketplus.com.tw/activity/{TEST_EVENT}/"
    assert extract_event_id(url) == TEST_EVENT


def test_url_kind_helpers():
    activity = f"https://ticketplus.com.tw/activity/{TEST_EVENT}"
    order = f"https://ticketplus.com.tw/order/{TEST_EVENT}/abc"
    confirm = f"https://ticketplus.com.tw/confirm/{TEST_EVENT}/abc"
    seat = f"https://ticketplus.com.tw/confirmSeat/{TEST_EVENT}/abc"
    checkout = f"https://ticketplus.com.tw/checkout/{TEST_EVENT}/abc"
    done = "https://ticketplus.com.tw/done/order123"
    assert is_activity_url(activity)
    assert is_login_url("https://ticketplus.com.tw/login")
    assert not is_login_url(activity)
    assert not is_order_url(activity)
    assert is_order_url(order)
    assert is_confirm_url(confirm)
    assert is_confirm_url(seat)
    assert is_confirm_url(f"https://ticketplus.com.tw/confirmSeat/{TEST_EVENT}/abc")
    assert not is_payment_url(confirm)
    assert not is_payment_url(order)
    assert not is_payment_url(activity)
    assert is_payment_url(checkout)
    assert is_payment_url(done)
    assert is_success_url(checkout)
    assert not is_success_url(order)
    assert not is_success_url(confirm)


def test_activity_and_order_urls_are_not_payment():
    """活動 / 訂票頁即使內文有『付款方式』也不可判定成功。"""
    activity = f"https://ticketplus.com.tw/activity/{TEST_EVENT}"
    order = f"https://ticketplus.com.tw/order/{TEST_EVENT}/abc"
    assert not is_payment_url(activity)
    assert not is_payment_url(order)


def test_keyword_matches_vip():
    assert keyword_matches("VIP3區  $6100  剩餘 12", "VIP3區")
    assert keyword_matches("VIP3區", "VIP3")
    assert not keyword_matches("VIP1區", "VIP3區")


def test_area_keyword_matches_nested_zones():
    assert area_keyword_matches("特B3區", "特B3區")
    assert area_keyword_matches("特B3區 $5380", "特B3")
    assert area_keyword_matches("特 B3 區", "特B3區")
    assert not area_keyword_matches("特B1區", "特B3區")
    assert not area_keyword_matches("特B1區", "特B3區")


def test_normalize_text():
    assert normalize_text("VIP 3 區") == "vip3區"


def test_clamp_parallel_windows():
    assert clamp_parallel_windows(1) == 1
    assert clamp_parallel_windows(3) == 3
    assert clamp_parallel_windows(0) == 1
    assert clamp_parallel_windows(9) == 3
    assert clamp_parallel_windows("2") == 2
    assert clamp_parallel_windows("nope") == 1


def test_normalize_mobile_taiwan():
    assert normalize_mobile("0912345678") == "0912345678"
    assert normalize_mobile("912345678") == "0912345678"
    assert normalize_mobile("+886912345678") == "0912345678"
    assert normalize_mobile("886-912-345-678") == "0912345678"


def test_ticket_config_validate_ok():
    cfg = TicketConfig(
        activity_url=f"https://ticketplus.com.tw/activity/{TARGET_EVENT}",
        quantity=2,
    )
    assert cfg.validate() == []


def test_parse_remaining_count_from_official_header():
    assert parse_remaining_count("VIP1區 剩餘 1 NT.6,100") == 1
    assert parse_remaining_count("剩餘\n                          1") == 1
    assert parse_remaining_count("VIP4區 剩餘 12") == 12
    assert parse_remaining_count("特B3區 剩餘 0") == 0
    assert parse_remaining_count("特B3區 熱賣中 NT.5,380") is None
    assert parse_remaining_count("特B2區 已售完") == 0


def test_resolve_buy_quantity_accepts_remaining_by_default():
    assert resolve_buy_quantity(2, 1, require_exact=False) == 1
    assert resolve_buy_quantity(2, 4, require_exact=False) == 2
    assert resolve_buy_quantity(2, None, require_exact=False) == 2
    assert resolve_buy_quantity(2, 0, require_exact=False) is None


def test_resolve_buy_quantity_requires_exact_when_asked():
    assert resolve_buy_quantity(2, 1, require_exact=True) is None
    assert resolve_buy_quantity(2, 2, require_exact=True) == 2
    assert resolve_buy_quantity(2, None, require_exact=True) == 2


def test_classify_area_sale_text_from_order_page():
    """未開賣顯示開賣時間；可選數量或已售完 / 剩餘 / 熱賣中代表已開賣。"""
    assert classify_area_sale_text("VIP3區 NT.6,100 2026/08/14 11:00 開賣時間") == "not_on_sale"
    assert classify_area_sale_text("VIP4區 尚未開賣") == "not_on_sale"
    assert classify_area_sale_text("特A1區 剩餘 0 NT.6,375") == "on_sale"
    assert classify_area_sale_text("特B3區 熱賣中 NT.5,380") == "on_sale"
    assert classify_area_sale_text("特B2區 已售完 NT.5,380") == "on_sale"
    assert classify_area_sale_text("搖滾 A 區 NT.2,600", has_quantity_control=True) == "on_sale"
    assert classify_area_sale_text("VIP3區 NT.6,100") == "unknown"


def test_ticket_config_rejects_wrong_site():
    cfg = TicketConfig(activity_url="https://tixcraft.com/activity/x", quantity=2)
    errors = cfg.validate()
    assert any("ticketplus" in e for e in errors)


def test_mock_url_is_allowed():
    url = "http://127.0.0.1:8765/activity/a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1"
    assert is_mock_url(url)
    assert extract_event_id(url) == "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1"
    cfg = TicketConfig(activity_url=url, quantity=2)
    assert cfg.validate() == []
    assert not is_mock_url("https://ticketplus.com.tw/activity/a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1")


def test_wsl_path_to_windows():
    from src.utils.windows_chrome import wsl_path_to_windows

    converted = wsl_path_to_windows(Path("/mnt/c/Users/User/Desktop/x"))
    assert converted.startswith("C:\\")
    assert "Users\\User\\Desktop\\x" in converted


def test_ticket_config_rejects_too_many_tickets():
    cfg = TicketConfig(
        activity_url=f"https://ticketplus.com.tw/activity/{TEST_EVENT}",
        quantity=5,
    )
    assert any("4" in e for e in cfg.validate())


def test_detect_platform_ticketplus_and_kktix():
    assert detect_platform("https://ticketplus.com.tw/activity/abc") == "ticketplus"
    assert detect_platform("https://kktix.com/events/sbgr01/registrations/new") == "kktix"
    assert detect_platform("https://www.kktix.com/events/sbgr01/registrations/new") == "kktix"
    assert detect_platform("https://binliveco.kktix.cc/events/sbgr01") == "kktix"
    assert detect_platform("http://127.0.0.1:8765/activity/a" + "1" * 31) == "ticketplus"
    assert detect_platform("http://127.0.0.1:8765/events/mock-kktix/registrations/new") == "kktix"
    assert detect_platform("https://example.com") == ""


def test_extract_kktix_slug():
    assert extract_kktix_slug("https://kktix.com/events/sbgr01/registrations/new") == "sbgr01"
    assert extract_kktix_slug("https://binliveco.kktix.cc/events/sbgr01") == "sbgr01"
    assert extract_kktix_slug("http://127.0.0.1:8765/events/mock-kktix/registrations/new") == "mock-kktix"
    assert extract_kktix_slug("https://ticketplus.com.tw/activity/abc") is None


def test_kktix_url_stages():
    reg = "https://kktix.com/events/sbgr01/registrations/new"
    held = "https://kktix.com/events/sbgr01/registrations/abc123"
    login = "https://kktix.com/users/sign_in"
    pay = "https://kktix.com/events/sbgr01/registrations/abc123/pay"
    adyen = "https://checkoutshopper-live.adyen.com/checkoutshopper/foo"
    assert is_kktix_url(reg)
    assert is_kktix_registration_url(reg)
    assert not is_kktix_registration_url(held)
    assert is_kktix_held_url(held)
    assert not is_kktix_held_url(reg)
    assert is_kktix_login_url(login)
    assert is_kktix_payment_url(pay)
    assert is_kktix_payment_url(adyen)
    assert is_kktix_payment_url("https://acs.example.com/3dsecure")
    assert not is_kktix_payment_url(reg)
    assert not is_kktix_payment_url(held)


def test_is_charity_ticket_name():
    assert is_charity_ticket_name("愛心票")
    assert is_charity_ticket_name("身障陪同票")
    assert is_charity_ticket_name("身心障礙席 TWD$1900")
    assert not is_charity_ticket_name("全票 TWD$3800")
    assert not is_charity_ticket_name("B2層電腦配位")


def test_parse_kktix_sale_at_countdown_and_datetime():
    now = 1_000_000.0
    assert parse_kktix_sale_at("尚未開賣 3秒後開賣", now=now) == now + 3
    assert parse_kktix_sale_at("尚未開賣，0 秒後開賣", now=now) == now
    assert parse_kktix_countdown_remaining("尚未開賣 0秒後開賣") == 0
    assert parse_kktix_countdown_remaining("熱賣中") is None
    ts = parse_kktix_sale_at("全票 2026/09/05 12:00(+0800) ~ 2026/12/19 18:59(+0800)")
    assert ts == datetime(2026, 9, 5, 12, 0, tzinfo=taipei_tz()).timestamp()
    assert parse_kktix_sale_at("全票 TWD$3800") is None
    tz = taipei_tz()
    morning = datetime(2026, 9, 5, 11, 0, tzinfo=tz).timestamp()
    assert parse_kktix_sale_at("尚未開賣 12:00", now=morning) == datetime(
        2026, 9, 5, 12, 0, tzinfo=tz
    ).timestamp()
    afternoon = datetime(2026, 9, 5, 13, 0, tzinfo=tz).timestamp()
    assert parse_kktix_sale_at("開賣 12:00", now=afternoon) == datetime(
        2026, 9, 6, 12, 0, tzinfo=tz
    ).timestamp()


def test_is_rechoose_alert_text():
    from src.utils.helpers import is_rechoose_alert_text

    assert is_rechoose_alert_text("目前的訂單將先行取消，座位亦不保留，您確定要重新選票嗎？")
    assert not is_rechoose_alert_text("查詢空位中")


def test_is_cloudflare_challenge_text():
    from src.utils.helpers import is_cloudflare_challenge_text

    assert is_cloudflare_challenge_text("正在驗證您是否是人類。這可能需要幾秒鐘的時間。")
    assert is_cloudflare_challenge_text("此網站使用安全服務抵禦惡意機器人。")
    assert is_cloudflare_challenge_text("Just a moment...")
    assert not is_cloudflare_challenge_text("全票 熱賣中")


def test_navigation_refused_hint_for_mock():
    from src.utils.helpers import is_connection_refused, navigation_refused_hint

    assert is_connection_refused(RuntimeError("unknown error: net::ERR_CONNECTION_REFUSED"))
    hint = navigation_refused_hint("http://127.0.0.1:8765/events/mock-kktix/registrations/new")
    assert "python -m mock.server" in hint
    assert "8765" in hint


def test_classify_kktix_page_alert():
    assert classify_kktix_page_alert("請先驗證電話號碼後再購票") == "verification"
    assert classify_kktix_page_alert("驗證失敗，將更新頁面，請重新購票。") == "csrf"
    assert classify_kktix_page_alert("目前沒有可以購買的票券。") == "failure"
    assert classify_kktix_page_alert("流量管制中，請稍後再試。") == "busy"
    assert classify_kktix_page_alert("全票 熱賣中") == ""
