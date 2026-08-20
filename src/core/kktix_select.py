from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from ..utils.helpers import area_keyword_matches, is_charity_ticket_name, resolve_buy_quantity


@dataclass
class KktixTicketRow:
    index: int
    name: str
    price_text: str
    status: str
    remaining: Optional[int] = None
    purchasable: bool = False

    @property
    def haystack(self) -> str:
        return f"{self.name} {self.price_text}"


@dataclass
class KktixPick:
    action: str
    index: Optional[int] = None
    quantity: Optional[int] = None


def _eligible(rows: Sequence[KktixTicketRow]) -> List[KktixTicketRow]:
    return [r for r in rows if not is_charity_ticket_name(r.name)]


def _qty(row: KktixTicketRow, want: int, require_exact: bool) -> Optional[int]:
    if not row.purchasable or row.status in {"unavailable", "sold_out", "not_on_sale"}:
        return None
    return resolve_buy_quantity(want, row.remaining, require_exact)


def pick_kktix_ticket(
    rows: Sequence[KktixTicketRow],
    priorities: Sequence[str],
    quantity: int,
    fallback_first_available: bool,
    require_exact_quantity: bool,
) -> KktixPick:
    eligible = _eligible(rows)
    started = {"on_sale", "unavailable", "sold_out"}
    if any(r.status in started for r in eligible):
        pass
    elif any(r.status in started for r in rows if is_charity_ticket_name(r.name)):
        # 開賣了但只剩愛心／身障，規格視為沒有可購種 → 重整等釋票
        return KktixPick("refresh")
    else:
        # 表頭／unknown 列不代表已開賣，避免開賣前被當成 refresh 狂 F5
        return KktixPick("wait_sale")

    want = max(1, int(quantity or 1))

    def first_buyable(pool: Sequence[KktixTicketRow]) -> Optional[tuple]:
        for row in pool:
            qty = _qty(row, want, require_exact_quantity)
            if qty:
                return row, qty
        return None

    if priorities:
        for keyword in priorities:
            if not str(keyword).strip():
                continue
            matched = [r for r in eligible if area_keyword_matches(r.haystack, str(keyword))]
            found = first_buyable(matched)
            if found:
                row, qty = found
                return KktixPick("select", row.index, qty)
        if fallback_first_available:
            found = first_buyable(eligible)
            if found:
                row, qty = found
                return KktixPick("fallback", row.index, qty)
        return KktixPick("refresh")

    found = first_buyable(eligible)
    if found:
        row, qty = found
        return KktixPick("select", row.index, qty)
    return KktixPick("refresh")
