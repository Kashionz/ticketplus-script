from pathlib import Path

from src.models.ticket_config import TicketConfig
from src.utils.helpers import (
    area_keyword_matches,
    clamp_parallel_windows,
    classify_area_sale_text,
    extract_event_id,
    extract_session_id,
    is_activity_url,
    is_confirm_url,
    is_login_url,
    is_mock_url,
    is_order_url,
    is_payment_url,
    is_success_url,
    keyword_matches,
    normalize_mobile,
    normalize_text,
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
