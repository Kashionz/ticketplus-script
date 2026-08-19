from urllib.request import urlopen

from mock.catalog import EVENT_ID, SESSION_919, mock_activity_url
from mock.server import start_mock_server


def test_mock_server_serves_activity_and_order(tmp_path):
    server, _thread = start_mock_server(port=18765)
    try:
        origin = mock_activity_url(port=18765).rsplit("/activity", 1)[0]
        activity = urlopen(f"{origin}/activity/{EVENT_ID}", timeout=5).read().decode("utf-8")
        assert "Ticket Plus" in activity
        assert "/app.js" in activity
        script = urlopen(f"{origin}/app.js", timeout=5).read().decode("utf-8")
        assert "開賣時間" in script
        assert "更新票數" in script
        assert "已售完" in script
        assert SESSION_919 in script
        assert "exclusive-code" in script
        assert "遠傳優先購序號" in script
        assert 'data-act="serial"' in script
        assert "電腦選位" in script
        assert "need-serial" in script
        assert "low-stock" in script
        assert "small class=\"ml-1\"" in script
        assert "data-limit" in script
        order = urlopen(f"{origin}/order/{EVENT_ID}/{SESSION_919}?scenario=presale", timeout=5).read().decode("utf-8")
        assert "id=\"app\"" in order
        health = urlopen(f"{origin}/api/health", timeout=5).read().decode("utf-8")
        assert EVENT_ID in health
    finally:
        server.shutdown()
        server.server_close()


def test_kktix_mock_routes():
    server, _thread = start_mock_server(port=18767)
    try:
        origin = "http://127.0.0.1:18767"
        html = urlopen(origin + "/events/mock-kktix/registrations/new", timeout=5).read().decode("utf-8")
        assert "registrationsNewApp" in html
        assert "person_agree_terms" in html
        assert "電腦配位" in html
        assert "自行選位" in html
        js = urlopen(origin + "/kktix.js", timeout=5).read().decode("utf-8")
        assert "暫無票券" in js
        assert "priority-unavailable" in js
        assert "charity-only" in js
        pay = urlopen(origin + "/events/mock-kktix/registrations/held1/pay", timeout=5).read().decode("utf-8")
        assert "cardNumber" in pay
    finally:
        server.shutdown()
        server.server_close()
