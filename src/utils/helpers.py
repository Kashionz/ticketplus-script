"""輔助函數。"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Iterable, Optional
from urllib.parse import urlparse


def taipei_tz() -> tzinfo:
    """Windows 預設沒有 IANA 時區資料，失敗時退回 UTC+8。"""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Taipei")
    except Exception:
        return timezone(timedelta(hours=8))


EVENT_ID_RE = re.compile(r"^[0-9a-f]{32}$", re.IGNORECASE)


def extract_event_id(url: str) -> Optional[str]:
    """從 TicketPlus 網址取出 eventId。"""
    if not url:
        return None
    parsed = urlparse(url.strip())
    parts = [p for p in parsed.path.split("/") if p]
    for key in ("activity", "order", "checkout", "confirm", "confirmseat"):
        if key in parts:
            idx = parts.index(key)
            if idx + 1 < len(parts) and EVENT_ID_RE.match(parts[idx + 1]):
                return parts[idx + 1].lower()
    if parts and EVENT_ID_RE.match(parts[-1]):
        return parts[-1].lower()
    return None


def extract_session_id(url: str) -> Optional[str]:
    """從 /order|/checkout|/confirm 網址取出 sessionId。"""
    if not url:
        return None
    parsed = urlparse(url.strip())
    parts = [p for p in parsed.path.split("/") if p]
    for key in ("order", "checkout", "confirm", "confirmseat"):
        if key in parts:
            idx = parts.index(key)
            if idx + 2 < len(parts) and EVENT_ID_RE.match(parts[idx + 2]):
                return parts[idx + 2].lower()
    return None


def normalize_text(text: str) -> str:
    """去掉空白與全形空白，方便關鍵字比對。"""
    if not text:
        return ""
    return re.sub(r"[\s\u3000]+", "", text).lower()


def keyword_matches(text: str, keyword: str) -> bool:
    """關鍵字以空白拆成 AND 條件。"""
    haystack = normalize_text(text)
    if not keyword or not keyword.strip():
        return True
    parts = [p for p in keyword.strip().split() if p]
    return all(normalize_text(p) in haystack for p in parts)


def area_keyword_matches(name: str, keyword: str) -> bool:
    """票區比對：完整名稱、去掉「區」、或關鍵字本身被包含。"""
    haystack = normalize_text(name)
    needle = normalize_text(keyword)
    if not needle:
        return True
    if needle in haystack:
        return True
    stripped = needle[:-1] if needle.endswith("區") else needle
    return bool(stripped) and stripped in haystack


def any_keyword_in(text: str, keywords: Iterable[str]) -> bool:
    haystack = normalize_text(text)
    return any(normalize_text(k) in haystack for k in keywords if k)


# 購票頁票區欄位：官方文案對應 TicketPlus i18n
ORDER_ON_SALE_MARKERS = (
    "已售完",
    "剩餘",
    "熱賣中",
    "熱賣",
    "暫停銷售",
    "銷售截止",
    "無可販售票種",
    "無可販售票區",
    "暫無票券",
)
ORDER_NOT_ON_SALE_MARKERS = (
    "開賣時間",
    "尚未開賣",
    "開放登記",
    "尚未開放",
)
_SALE_DATE_RE = re.compile(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}")
_SALE_TIME_RE = re.compile(r"\d{1,2}:\d{2}")


def classify_area_sale_text(text: str, has_quantity_control: bool = False) -> str:
    """依票區欄位判斷是否已開賣。

    - 可選數量（+/-）或顯示已售完 / 剩餘 / 熱賣中 → on_sale
    - 顯示開賣時間或尚未開賣 → not_on_sale
    """
    if has_quantity_control:
        return "on_sale"
    blob = text or ""
    if any(marker in blob for marker in ORDER_ON_SALE_MARKERS):
        return "on_sale"
    if any(marker in blob for marker in ORDER_NOT_ON_SALE_MARKERS):
        return "not_on_sale"
    if _SALE_DATE_RE.search(blob) and _SALE_TIME_RE.search(blob):
        return "not_on_sale"
    return "unknown"


def url_path_segments(url: str) -> list[str]:
    return [p.lower() for p in urlparse(url or "").path.split("/") if p]


# 真正的付款 / 完成頁（到這裡才交給使用者）
PAYMENT_SEGMENTS = frozenset({"checkout", "done", "ordered", "payment"})
# 訂票後、付款前的確認頁，還要繼續按下一步
CONFIRM_SEGMENTS = frozenset({"confirm", "confirmseat", "seat"})
PAYMENT_HOST_HINTS = (
    "3dsecure",
    "acs.",
    "visa.com",
    "mastercard.",
    "jcb",
    "amex",
    "ctbcbank",
    "taishin",
    "cathaybk",
    "esunbank",
    "tcb-bank",
    "firstbank",
)


def is_payment_url(url: str) -> bool:
    """只在官方付款頁或 3D 驗證網域回傳 True。

    不可用頁面內文判斷：活動注意事項常出現「付款方式」「訂單成立」。
    /confirm 也還不是付款頁。
    """
    segs = url_path_segments(url)
    if segs and segs[0] in PAYMENT_SEGMENTS:
        return True
    host = (urlparse(url or "").hostname or "").lower()
    return any(hint in host for hint in PAYMENT_HOST_HINTS)


def is_success_url(url: str) -> bool:
    """相容舊名稱；語意等同 is_payment_url。"""
    return is_payment_url(url)


def is_confirm_url(url: str) -> bool:
    segs = url_path_segments(url)
    return bool(segs) and segs[0] in CONFIRM_SEGMENTS


def is_order_url(url: str) -> bool:
    segs = url_path_segments(url)
    return bool(segs) and segs[0] == "order"


def is_activity_url(url: str) -> bool:
    segs = url_path_segments(url)
    return bool(segs) and segs[0] == "activity"


MAX_PARALLEL_WINDOWS = 3


def clamp_parallel_windows(count: object) -> int:
    try:
        value = int(count)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 1
    return max(1, min(MAX_PARALLEL_WINDOWS, value))


def is_login_url(url: str) -> bool:
    segs = url_path_segments(url)
    return bool(segs) and segs[0] in {"login", "signin", "sign-in"}


def normalize_mobile(mobile: str, country_code: str = "+886") -> str:
    """遠大台灣門號欄位通常要 09xxxxxxxx，不要把 +886 填進區碼選單。"""
    digits = re.sub(r"\D", "", mobile or "")
    cc = re.sub(r"\D", "", country_code or "")
    if cc and digits.startswith(cc):
        digits = digits[len(cc) :]
    if cc in {"886", ""} and len(digits) == 9 and digits.startswith("9"):
        digits = "0" + digits
    return digits


MOCK_HOSTS = frozenset({"127.0.0.1", "localhost", "0.0.0.0", "::1"})


def is_mock_url(url: str) -> bool:
    """本機模擬站，用來驗證搶票流程，不是正式遠大網站。"""
    host = (urlparse(url or "").hostname or "").lower()
    return host in MOCK_HOSTS or host.endswith(".localhost")


class Timer:
    def __init__(self) -> None:
        self.start_time: Optional[float] = None

    def start(self) -> None:
        self.start_time = time.time()

    def elapsed(self) -> float:
        if self.start_time is None:
            return 0.0
        return time.time() - self.start_time
