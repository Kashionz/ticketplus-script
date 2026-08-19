"""本機 TicketPlus / KKTIX 模擬站。"""

from __future__ import annotations

import argparse
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from .catalog import DEFAULT_HOST, DEFAULT_PORT, EVENT_ID, mock_activity_url, mock_kktix_url

STATIC_DIR = Path(__file__).resolve().parent / "static"
APP_PREFIXES = (
    "/activity/",
    "/order/",
    "/confirmseat/",
    "/confirm/",
    "/checkout/",
    "/done/",
    "/login",
)


class MockHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path or "/"
        lower = path.lower()
        if path == "/api/health":
            self._json({"ok": True, "eventId": EVENT_ID})
            return
        if path == "/api/catalog":
            from .catalog import SESSION_919, SESSION_920, TITLE

            self._json(
                {
                    "title": TITLE,
                    "eventId": EVENT_ID,
                    "sessions": [
                        {"name": "9/19 場次", "sessionId": SESSION_919},
                        {"name": "9/20 場次", "sessionId": SESSION_920},
                    ],
                }
            )
            return
        if path.startswith("/events/") or path in {"/users/sign_in", "/kktix.js"}:
            if path.endswith("/kktix.js") or path == "/kktix.js":
                self._send_file(STATIC_DIR / "kktix.js", "application/javascript; charset=utf-8")
                return
            if path.endswith("/pay"):
                self._send_file(STATIC_DIR / "kktix.html", "text/html; charset=utf-8")
                return
            self._send_file(STATIC_DIR / "kktix.html", "text/html; charset=utf-8")
            return
        if path == "/" or path == "/control" or any(lower.startswith(p) for p in APP_PREFIXES):
            self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        super().do_GET()

    def _json(self, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_mock_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> Tuple[ThreadingHTTPServer, threading.Thread]:
    class ReuseServer(ThreadingHTTPServer):
        allow_reuse_address = True

    server = ReuseServer((host, port), partial(MockHandler))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="TicketPlus / KKTIX 本機模擬站")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    server, _thread = start_mock_server(args.host, args.port)
    print(f"模擬站已啟動: {mock_activity_url(args.host, args.port)}")
    print(f"KKTIX: {mock_kktix_url(args.host, args.port)}")
    print(f"KKTIX 例: {mock_kktix_url(args.host, args.port)}?scenario=presale")
    print("場景可在頁面上方切換，或加 ?scenario=presale&saleAfter=2")
    print("可用場景: happy / presale / priority-soldout / stock-later / low-stock / need-login / need-serial / queue / fail-once / overlay")
    print("KKTIX 場景: happy / presale / priority-unavailable / queue / need-login / charity-only")
    print("Ctrl+C 結束")
    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        print("\n模擬站已停止")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
