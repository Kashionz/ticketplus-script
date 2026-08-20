import json
from pathlib import Path
from unittest.mock import patch

from src.api.kktix_api import (
    fetch_kktix_catalog,
    format_kktix_catalog,
    parse_event_title,
    parse_register_info,
    parse_ticket_table,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE = {"register_status": "COMING_SOON", "tickets": [{"id": 1, "in_stock": True}]}


def test_format_coming_soon():
    text = format_kktix_catalog("sbgr01", "Atarayo", SAMPLE, [("全票", "3800"), ("愛心票", "1900")])
    assert "COMING_SOON" in text or "尚未開賣" in text
    assert "3800" in text


def test_parse_register_info_fixture():
    data = json.loads((FIXTURES / "kktix_register_info.json").read_text(encoding="utf-8"))
    parsed = parse_register_info(data)
    assert parsed["register_status"] == "COMING_SOON"
    assert parsed["ticket_count"] == 3
    assert parsed["in_stock_count"] == 2


def test_parse_ticket_table_sbgr01_snippet():
    html = (FIXTURES / "kktix_ticket_table.html").read_text(encoding="utf-8")
    rows = parse_ticket_table(html)
    assert len(rows) >= 3
    names = [r[0] for r in rows]
    prices = [r[2].replace(",", "") for r in rows]
    assert "全票" in names
    assert "愛心票" in names
    assert any(p.replace(",", "") in {"3800", "3,800"} or "3800" in p.replace(",", "") for p in prices)
    assert any("1900" in p.replace(",", "") for p in prices)
    assert "2026/09/05" in rows[0][1]
    title = parse_event_title(html)
    assert "Atarayo" in title


def test_fetch_mock_url_skips_http():
    url = "http://127.0.0.1:8765/events/mock-kktix/registrations/new"
    with patch("src.api.kktix_api.requests.get") as mocked:
        text = fetch_kktix_catalog(url)
    mocked.assert_not_called()
    assert "mock-kktix" in text
    assert "模擬" in text


def test_fetch_catalog_falls_back_when_event_page_blocked():
    info = {"register_status": "COMING_SOON", "tickets": [{"id": 1, "in_stock": True}]}
    calls = []

    def side_effect(url, **kwargs):
        calls.append(url)
        if "register_info" in url:

            class OK:
                status_code = 200
                text = "{}"

                def json(self):
                    return info

                def raise_for_status(self):
                    return None

            return OK()

        class Blocked:
            status_code = 403
            text = "Just a moment... cloudflare"

            def raise_for_status(self):
                import requests as req

                raise req.HTTPError("403")

        return Blocked()

    with patch("src.api.kktix_api.requests.get", side_effect=side_effect):
        text = fetch_kktix_catalog("https://kktix.com/events/sbgr01/registrations/new")
    assert "COMING_SOON" in text or "尚未開賣" in text
    assert "無法讀取" in text
    assert any("register_info" in u for u in calls)


def test_inspect_command_kktix_mock(capsys):
    from argparse import Namespace

    from src.main import run_inspect

    args = Namespace(
        url="http://127.0.0.1:8765/events/mock-kktix/registrations/new",
        config="config/config.yaml",
    )
    assert run_inspect(args) == 0
    assert "mock-kktix" in capsys.readouterr().out
