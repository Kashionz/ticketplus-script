"""讀取 KKTIX 公開活動資料（register_info + 活動頁票種表）。僅供 inspect，不下單。"""

from __future__ import annotations

import re
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from urllib.parse import urlparse

import requests

from ..utils.helpers import detect_platform, extract_kktix_slug, is_mock_url

UA = "Mozilla/5.0 TicketPlusInspect/1.0"
REGISTER_INFO_URL = "https://kktix.com/g/events/{slug}/register_info"
EVENT_PAGE_URL = "https://kktix.com/events/{slug}"

STATUS_ZH = {
    "COMING_SOON": "尚未開賣",
    "IN_STOCK": "販售中",
    "SOLD_OUT": "售完",
    "OUT_OF_STOCK": "無庫存",
}

TicketRow = Union[Tuple[str, str], Tuple[str, str, str], Sequence[str]]


def _looks_like_cloudflare(html: str, status_code: int = 200) -> bool:
    if status_code == 403:
        return True
    blob = (html or "")[:2500].lower()
    return "just a moment" in blob and "cloudflare" in blob


def _get(url: str, timeout: int = 15) -> requests.Response:
    response = requests.get(
        url,
        headers={"User-Agent": UA},
        timeout=timeout,
        allow_redirects=True,
    )
    response.raise_for_status()
    return response


def _event_page_candidates(url: str, slug: str) -> List[str]:
    primary = _event_page_url(url, slug)
    generic = EVENT_PAGE_URL.format(slug=slug)
    seen: List[str] = []
    for item in (primary, generic):
        if item not in seen:
            seen.append(item)
    return seen


def _fetch_event_html(url: str, slug: str) -> str:
    """活動頁可能被 Cloudflare 擋；失敗回空字串，仍可用 register_info。"""
    last_error: Optional[Exception] = None
    for candidate in _event_page_candidates(url, slug):
        try:
            response = requests.get(
                candidate,
                headers={"User-Agent": UA},
                timeout=15,
                allow_redirects=True,
            )
            if _looks_like_cloudflare(response.text, response.status_code):
                last_error = RuntimeError(f"Cloudflare 擋住 {candidate}")
                continue
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            continue
    if last_error:
        return ""
    return ""


def _strip_tags(html: str) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", html or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_register_info(data: Dict[str, Any]) -> Dict[str, Any]:
    tickets = data.get("tickets") or []
    if not isinstance(tickets, list):
        tickets = []
    in_stock_count = sum(1 for item in tickets if isinstance(item, dict) and item.get("in_stock"))
    return {
        "register_status": data.get("register_status") or "",
        "tickets": tickets,
        "ticket_count": len(tickets),
        "in_stock_count": in_stock_count,
        "sections": data.get("sections") or [],
        "now": data.get("now") or "",
    }


def parse_event_title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html or "", re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return unescape(re.sub(r"\s+", " ", match.group(1))).strip()


_ROW_RE = re.compile(
    r"<tr>\s*<td class=\"name\">(.*?)</td>\s*<td class=\"period\">(.*?)</td>\s*"
    r"<td class=\"price\">(.*?)</td>\s*</tr>",
    re.IGNORECASE | re.DOTALL,
)


def parse_ticket_table(html: str) -> List[Tuple[str, str, str]]:
    """從活動頁票種表取出 (name, period, price)。"""
    rows: List[Tuple[str, str, str]] = []
    for name_html, period_html, price_html in _ROW_RE.findall(html or ""):
        cleaned_name = re.sub(r"<p[\s\S]*?</p>", "", name_html, flags=re.IGNORECASE)
        cleaned_name = re.sub(r"<i[\s\S]*?</i>", "", cleaned_name, flags=re.IGNORECASE)
        name = _strip_tags(cleaned_name)
        period = _strip_tags(period_html)
        value_match = re.search(
            r'class="currency-value"[^>]*>([^<]+)',
            price_html,
            re.IGNORECASE,
        )
        if value_match:
            price = value_match.group(1).replace(",", "").strip()
        else:
            price = _strip_tags(price_html).replace("TWD$", "").replace(",", "").strip()
        if name:
            rows.append((name, period, price))
    return rows


def format_kktix_catalog(
    slug: str,
    title: str,
    register_info: Dict[str, Any],
    tickets: Iterable[TicketRow],
) -> str:
    parsed = parse_register_info(register_info or {})
    status = parsed.get("register_status") or ""
    status_zh = STATUS_ZH.get(status, "")
    if status and status_zh:
        status_line = f"開賣狀態：{status}（{status_zh}）"
    elif status:
        status_line = f"開賣狀態：{status}"
    else:
        status_line = "開賣狀態：（無）"

    lines = [
        f"活動：{title}",
        f"slug：{slug}",
        f"網址：https://kktix.com/events/{slug}/registrations/new",
        status_line,
        "",
        "票種：",
    ]
    any_ticket = False
    for item in tickets:
        parts = list(item)
        if len(parts) >= 3:
            name, period, price = parts[0], parts[1], parts[2]
        elif len(parts) == 2:
            name, price = parts[0], parts[1]
            period = ""
        else:
            continue
        any_ticket = True
        extra = f"  {period}" if period else ""
        lines.append(f"  - {name:<8} ${price}{extra}")
    if not any_ticket:
        lines.append("  （尚無票種資料）")
    ticket_count = parsed.get("ticket_count") or 0
    in_stock_count = parsed.get("in_stock_count") or 0
    if ticket_count:
        lines.append("")
        lines.append(f"register_info 票種數：{ticket_count}（in_stock {in_stock_count}）")
    return "\n".join(lines).rstrip() + "\n"


def _event_page_url(url: str, slug: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    scheme = urlparse(url or "").scheme or "https"
    if host.endswith(".kktix.cc"):
        return f"{scheme}://{host}/events/{slug}"
    return EVENT_PAGE_URL.format(slug=slug)


def fetch_register_info(slug: str) -> Dict[str, Any]:
    data = _get(REGISTER_INFO_URL.format(slug=slug)).json()
    if not isinstance(data, dict):
        raise RuntimeError("register_info 格式錯誤")
    return data


def fetch_kktix_catalog(url: str) -> str:
    """回傳格式化文字。模擬站不下 HTTP；網路錯誤向外拋。"""
    if detect_platform(url) != "kktix":
        raise ValueError("請提供有效的 KKTIX 活動網址")
    slug = extract_kktix_slug(url)
    if is_mock_url(url):
        slug = slug or "mock-kktix"
        return (
            "KKTIX 模擬站\n"
            f"slug：{slug}\n"
            f"網址：{url}\n"
            "票種：全票 $3800 / $3600（模擬資料，未連線官方）\n"
            "開賣狀態依模擬站 scenario 而定。\n"
        )
    if not slug:
        raise ValueError("無法從 KKTIX 網址解析活動代碼")
    info = fetch_register_info(slug)
    html = _fetch_event_html(url, slug)
    title = parse_event_title(html) or slug
    tickets = parse_ticket_table(html)
    text = format_kktix_catalog(slug, title, info, tickets)
    if not html:
        text = text.rstrip() + "\n（活動頁無法讀取，可能被 Cloudflare 擋住；僅顯示 register_info。）\n"
    return text
