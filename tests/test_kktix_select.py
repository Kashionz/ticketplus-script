from src.core.kktix_select import KktixTicketRow, pick_kktix_ticket


def _row(index, name, price, status, remaining=None, purchasable=None):
    if purchasable is None:
        purchasable = status == "on_sale"
    return KktixTicketRow(
        index=index,
        name=name,
        price_text=price,
        status=status,
        remaining=remaining,
        purchasable=purchasable,
    )


def _atarayo(priority_status="unavailable"):
    return [
        _row(0, "全票", "3800", priority_status),
        _row(1, "全票", "3600", "on_sale"),
        _row(2, "愛心票", "1900", "on_sale"),
    ]


def test_wait_sale_when_all_not_on_sale():
    rows = [_row(0, "全票", "3800", "not_on_sale", purchasable=False)]
    pick = pick_kktix_ticket(rows, ["3800"], 2, False, False)
    assert pick.action == "wait_sale"


def test_wait_sale_ignores_unknown_header_rows():
    rows = [
        _row(0, "票種", "", "unknown", purchasable=False),
        _row(1, "全票", "3800", "not_on_sale", purchasable=False),
        _row(2, "全票", "3600", "not_on_sale", purchasable=False),
    ]
    pick = pick_kktix_ticket(rows, ["3800"], 2, False, False)
    assert pick.action == "wait_sale"


def test_unknown_header_does_not_block_refresh_after_sale():
    rows = [
        _row(0, "票種", "", "unknown", purchasable=False),
        _row(1, "全票", "3800", "unavailable"),
        _row(2, "全票", "3600", "on_sale"),
    ]
    pick = pick_kktix_ticket(rows, ["3800"], 2, False, False)
    assert pick.action == "refresh"


def test_refresh_when_priority_unavailable_without_fallback():
    pick = pick_kktix_ticket(_atarayo("unavailable"), ["3800"], 2, False, False)
    assert pick.action == "refresh"
    assert pick.index is None


def test_fallback_skips_charity():
    pick = pick_kktix_ticket(_atarayo("unavailable"), ["3800"], 2, True, False)
    assert pick.action == "fallback"
    assert pick.index == 1
    assert pick.quantity == 2


def test_never_select_charity_even_if_price_listed():
    pick = pick_kktix_ticket(_atarayo("unavailable"), ["1900"], 1, False, False)
    assert pick.action == "refresh"


def test_empty_priorities_picks_first_non_charity():
    pick = pick_kktix_ticket(_atarayo("on_sale"), [], 2, False, False)
    assert pick.action == "select"
    assert pick.index == 0


def test_charity_only_available_refreshes():
    rows = [
        _row(0, "全票", "3800", "unavailable"),
        _row(1, "愛心票", "1900", "on_sale"),
    ]
    pick = pick_kktix_ticket(rows, [], 1, True, False)
    assert pick.action == "refresh"


def test_select_matching_price():
    pick = pick_kktix_ticket(_atarayo("on_sale"), ["3600"], 2, False, False)
    assert pick.action == "select"
    assert pick.index == 1
