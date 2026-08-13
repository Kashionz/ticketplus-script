import pytest

from src.api.event_api import fetch_event_catalog, format_catalog

TEST_EVENT = "d1b4147aaeaa2e233f0fdc827cd55310"
TARGET_EVENT = "af39103d211724c82069c4ab5e40e95c"


def _fetch(event_id: str):
    try:
        return fetch_event_catalog(event_id)
    except Exception as exc:
        pytest.skip(f"公開 API 無法連線: {exc}")


def test_test_event_omnific_is_on_sale_without_areas():
    catalog = _fetch(TEST_EVENT)
    assert "Omnific" in catalog.title
    assert catalog.sessions
    assert catalog.sessions[0].session_id
    names = [p.name for p in catalog.products]
    assert "預售票" in names
    assert catalog.areas == []
    text = format_catalog(catalog)
    assert "預售票" in text


def test_target_event_has_vip3_and_vip4():
    catalog = _fetch(TARGET_EVENT)
    assert "INFINITE" in catalog.title
    assert len(catalog.sessions) == 2
    names_19 = [a.name for a in catalog.areas if a.session_id == catalog.sessions[0].session_id]
    names_20 = [a.name for a in catalog.areas if a.session_id == catalog.sessions[1].session_id]
    assert "VIP3區" in names_19
    assert "VIP4區" in names_19
    assert "VIP3區" in names_20
    assert "VIP4區" in names_20
    vip3 = next(a for a in catalog.areas if a.name == "VIP3區")
    assert vip3.price == 6100
    text = format_catalog(catalog, area_filter="VIP")
    assert "VIP3區" in text
    assert "黃2B" not in text
