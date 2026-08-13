"""讀取 TicketPlus 公開活動資料（getS3）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests

GETS3_URL = "https://apis.ticketplus.com.tw/config/api/v1/getS3"
HOME_URL = "https://ticketplus.com.tw"


@dataclass
class TicketArea:
    ticket_area_id: str
    session_id: str
    name: str
    price: int
    hidden: bool = False


@dataclass
class Product:
    product_id: str
    session_id: str
    name: str
    price: int
    ticket_area_id: str = ""
    hidden: bool = False


@dataclass
class Session:
    session_id: str
    name: str
    date: str
    time: str
    location: str
    has_areas: bool
    expose_start: str = ""
    expose_end: str = ""


@dataclass
class EventCatalog:
    event_id: str
    title: str
    location: str
    address: str
    sessions: List[Session] = field(default_factory=list)
    products: List[Product] = field(default_factory=list)
    areas: List[TicketArea] = field(default_factory=list)

    @property
    def activity_url(self) -> str:
        return f"{HOME_URL}/activity/{self.event_id}"

    def areas_for_session(self, session_id: str) -> List[TicketArea]:
        return [a for a in self.areas if a.session_id == session_id]

    def products_for_session(self, session_id: str) -> List[Product]:
        return [p for p in self.products if p.session_id == session_id]


def _get_s3(path: str, timeout: int = 15) -> Dict[str, Any]:
    response = requests.get(
        GETS3_URL,
        params={"path": path},
        headers={"User-Agent": "Mozilla/5.0 TicketPlusInspect/1.0"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, dict) and data.get("errCode"):
        raise RuntimeError(f"getS3 錯誤 {data.get('errCode')}: {data.get('errMsg')}")
    return data


def fetch_event_catalog(event_id: str) -> EventCatalog:
    event = _get_s3(f"event/{event_id}/event.json")
    sessions_raw = _get_s3(f"event/{event_id}/sessions.json").get("sessions") or []
    products_raw = _get_s3(f"event/{event_id}/products.json").get("products") or []
    areas_raw = _get_s3(f"event/{event_id}/ticketAreas.json").get("ticketAreas") or []

    sessions = [
        Session(
            session_id=item.get("sessionId", ""),
            name=item.get("name", ""),
            date=item.get("date", ""),
            time=item.get("time", ""),
            location=item.get("location", ""),
            has_areas=bool(item.get("ticketArea")),
            expose_start=item.get("exposeStart", "") or "",
            expose_end=item.get("exposeEnd", "") or "",
        )
        for item in sessions_raw
        if not item.get("hidden")
    ]
    products = [
        Product(
            product_id=item.get("productId", ""),
            session_id=item.get("sessionId", ""),
            name=item.get("name", ""),
            price=int(item.get("price") or 0),
            ticket_area_id=item.get("ticketAreaId", "") or "",
            hidden=bool(item.get("hidden")),
        )
        for item in products_raw
        if not item.get("hidden")
    ]
    areas = [
        TicketArea(
            ticket_area_id=item.get("ticketAreaId", ""),
            session_id=item.get("sessionId", ""),
            name=item.get("name", ""),
            price=int(item.get("price") or 0),
            hidden=bool(item.get("hidden")),
        )
        for item in areas_raw
        if not item.get("hidden")
    ]
    return EventCatalog(
        event_id=event.get("event_id") or event_id,
        title=event.get("title", ""),
        location=event.get("location", ""),
        address=event.get("address", ""),
        sessions=sessions,
        products=products,
        areas=areas,
    )


def format_catalog(catalog: EventCatalog, area_filter: Optional[str] = None) -> str:
    lines = [
        f"活動：{catalog.title}",
        f"eventId：{catalog.event_id}",
        f"地點：{catalog.location} / {catalog.address}",
        f"網址：{catalog.activity_url}",
        "",
    ]
    if not catalog.sessions:
        lines.append("（尚無場次資料）")
        return "\n".join(lines)

    for session in catalog.sessions:
        lines.append(f"場次：{session.name}")
        lines.append(f"  sessionId：{session.session_id}")
        lines.append(f"  日期 / 時間：{session.date}  {session.time}")
        lines.append(f"  公開期間：{session.expose_start} ~ {session.expose_end}")
        areas = catalog.areas_for_session(session.session_id)
        products = catalog.products_for_session(session.session_id)
        if area_filter:
            needle = area_filter.lower()
            areas = [a for a in areas if needle in a.name.lower()]
            products = [p for p in products if needle in p.name.lower()]
        if areas:
            lines.append("  票區：")
            for area in areas:
                lines.append(f"    - {area.name:<12} ${area.price:<6} {area.ticket_area_id}")
        elif products:
            lines.append("  票種：")
            for product in products:
                lines.append(f"    - {product.name:<12} ${product.price:<6} {product.product_id}")
        else:
            lines.append("  （此場次沒有可見票區 / 票種）")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
