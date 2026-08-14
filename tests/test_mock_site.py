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
        assert "order-code-row" in script
        assert 'data-act="serial"' in script
        assert "電腦選位" in script
        assert "need-serial" in script
        order = urlopen(f"{origin}/order/{EVENT_ID}/{SESSION_919}?scenario=presale", timeout=5).read().decode("utf-8")
        assert "id=\"app\"" in order
        health = urlopen(f"{origin}/api/health", timeout=5).read().decode("utf-8")
        assert EVENT_ID in health
    finally:
        server.shutdown()
        server.server_close()
