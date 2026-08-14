"""模擬站活動 / 場次固定識別碼。"""

EVENT_ID = "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1"
SESSION_919 = "b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1"
SESSION_920 = "c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
TITLE = "模擬活動 INFINITE RALLY MOCK"

SCENARIOS = (
    "happy",
    "presale",
    "priority-soldout",
    "stock-later",
    "low-stock",
    "need-login",
    "need-serial",
    "queue",
    "fail-once",
    "overlay",
)


def mock_origin(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    return f"http://{host}:{port}"


def mock_activity_url(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    return f"{mock_origin(host, port)}/activity/{EVENT_ID}"
