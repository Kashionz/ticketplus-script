# KKTIX Computer-Assignment Booking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add KKTIX computer-assignment booking to the existing TicketPlus assistant so a KKTIX URL uses the same GUI, waits for sale-time F5, picks non-charity ticket types by price/name, and stops at the payment page.

**Architecture:** `BotEngine._execute()` dispatches on `detect_platform(url)`. TicketPlus keeps the current loop. KKTIX runs `KktixFlow` against new page objects. Ticket matching is a pure function so refresh-vs-fallback and charity exclusion can be unit-tested without Chrome.

**Tech Stack:** Python 3.10+, Selenium, PyQt6, pytest, existing `mock` HTTP server.

## Global Constraints

- UI-only: click visible official (or mock) controls; do not POST hidden booking APIs. `register_info` is inspect-only.
- Computer assignment only: click 「電腦配位」 if present, else 「下一步」; never 「自行選位」.
- Charity tickets (name contains 愛心 / 身障 / 身心障礙 / 陪同) are never selected.
- Preferred type 「暫無票券」 and `fallback_first_available=false` → full page refresh after `refresh_interval`. Fallback true → first purchasable non-charity type, no refresh.
- Never refresh during 查詢空位, after hold, or on the payment page.
- After hold: do not edit form fields; click next until payment (user prefilled KKTIX account data).
- Stop at payment (Adyen / 3DS / `/pay`); do not fill card numbers.
- KKTIX parallel windows forced to 1.
- Existing TicketPlus tests in `tests/` must keep passing.
- Quantity stays 1–4.

## File map

| File | Responsibility |
|------|----------------|
| `src/utils/helpers.py` | Platform detect, KKTIX slug/URLs, charity name |
| `src/core/kktix_select.py` | Pure ticket-row pick (select / fallback / refresh / wait_sale) |
| `src/models/ticket_config.py` | Accept KKTIX and KKTIX-mock URLs |
| `src/pages/kktix/registration_page.py` | `/registrations/new` DOM |
| `src/pages/kktix/login_page.py` | KKTIX sign-in |
| `src/pages/kktix/checkout_page.py` | Post-hold next clicks |
| `src/core/kktix_flow.py` | KKTIX state machine |
| `src/core/bot_engine.py` | Dispatch + home URL + no extra windows on KKTIX |
| `src/api/kktix_api.py` | Inspect: event page tickets + `register_info` |
| `mock/server.py` + `mock/static/kktix.html` + `mock/static/kktix.js` | KKTIX mock routes |
| `src/gui/main_window.py` | URL-based labels, Atarayo preset, inspect |
| `config/config.example.yaml`, `README.md` | Documented usage |

Do not change TicketPlus behavior in `activity_page.py` / `order_page.py`.

---

### Task 1: Platform URL helpers and charity names

**Files:**
- Modify: `src/utils/helpers.py`
- Test: `tests/test_helpers.py`

**Interfaces:**
- Consumes: existing `url_path_segments`, `is_mock_url`, `normalize_text`
- Produces:
  - `detect_platform(url: str) -> str` returns `"ticketplus"` | `"kktix"` | `""`
  - `extract_kktix_slug(url: str) -> Optional[str]`
  - `is_kktix_url(url: str) -> bool`
  - `is_kktix_registration_url(url: str) -> bool`
  - `is_kktix_login_url(url: str) -> bool`
  - `is_kktix_held_url(url: str) -> bool`
  - `is_kktix_payment_url(url: str) -> bool`
  - `is_charity_ticket_name(name: str) -> bool`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_helpers.py`:

```python
from src.utils.helpers import (
    detect_platform,
    extract_kktix_slug,
    is_charity_ticket_name,
    is_kktix_held_url,
    is_kktix_login_url,
    is_kktix_payment_url,
    is_kktix_registration_url,
    is_kktix_url,
)


def test_detect_platform_ticketplus_and_kktix():
    assert detect_platform("https://ticketplus.com.tw/activity/abc") == "ticketplus"
    assert detect_platform("https://kktix.com/events/sbgr01/registrations/new") == "kktix"
    assert detect_platform("https://binliveco.kktix.cc/events/sbgr01") == "kktix"
    assert detect_platform("http://127.0.0.1:8765/activity/a" + "1" * 31) == "ticketplus"
    assert detect_platform("http://127.0.0.1:8765/events/mock-kktix/registrations/new") == "kktix"
    assert detect_platform("https://example.com") == ""


def test_extract_kktix_slug():
    assert extract_kktix_slug("https://kktix.com/events/sbgr01/registrations/new") == "sbgr01"
    assert extract_kktix_slug("https://binliveco.kktix.cc/events/sbgr01") == "sbgr01"
    assert extract_kktix_slug("http://127.0.0.1:8765/events/mock-kktix/registrations/new") == "mock-kktix"
    assert extract_kktix_slug("https://ticketplus.com.tw/activity/abc") is None


def test_kktix_url_stages():
    reg = "https://kktix.com/events/sbgr01/registrations/new"
    held = "https://kktix.com/events/sbgr01/registrations/abc123"
    login = "https://kktix.com/users/sign_in"
    pay = "https://kktix.com/events/sbgr01/registrations/abc123/pay"
    adyen = "https://checkoutshopper-live.adyen.com/checkoutshopper/foo"
    assert is_kktix_url(reg)
    assert is_kktix_registration_url(reg)
    assert not is_kktix_registration_url(held)
    assert is_kktix_held_url(held)
    assert not is_kktix_held_url(reg)
    assert is_kktix_login_url(login)
    assert is_kktix_payment_url(pay)
    assert is_kktix_payment_url(adyen)
    assert is_kktix_payment_url("https://acs.example.com/3dsecure")
    assert not is_kktix_payment_url(reg)
    assert not is_kktix_payment_url(held)


def test_is_charity_ticket_name():
    assert is_charity_ticket_name("愛心票")
    assert is_charity_ticket_name("身障陪同票")
    assert is_charity_ticket_name("身心障礙席 TWD$1900")
    assert not is_charity_ticket_name("全票 TWD$3800")
    assert not is_charity_ticket_name("B2層電腦配位")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_helpers.py::test_detect_platform_ticketplus_and_kktix tests/test_helpers.py::test_extract_kktix_slug tests/test_helpers.py::test_kktix_url_stages tests/test_helpers.py::test_is_charity_ticket_name -v`

Expected: FAIL with `ImportError` or `not defined`.

- [ ] **Step 3: Implement helpers**

Add to `src/utils/helpers.py` (keep existing TicketPlus helpers unchanged):

```python
KKTIX_CHARITY_MARKERS = ("愛心", "身障", "身心障礙", "陪同")


def detect_platform(url: str) -> str:
    host = (urlparse(url or "").hostname or "").lower()
    path = (urlparse(url or "").path or "").lower()
    if is_mock_url(url):
        if "/events/" in path:
            return "kktix"
        return "ticketplus"
    if "ticketplus.com.tw" in host:
        return "ticketplus"
    if host == "kktix.com" or host.endswith(".kktix.cc"):
        return "kktix"
    return ""


def extract_kktix_slug(url: str) -> Optional[str]:
    parts = [p for p in urlparse(url or "").path.split("/") if p]
    if "events" not in [p.lower() for p in parts]:
        return None
    idx = [p.lower() for p in parts].index("events")
    if idx + 1 >= len(parts):
        return None
    slug = parts[idx + 1]
    if slug.lower() in {"new", "registrations"}:
        return None
    return slug


def is_kktix_url(url: str) -> bool:
    return detect_platform(url) == "kktix"


def is_kktix_registration_url(url: str) -> bool:
    segs = url_path_segments(url)
    return "registrations" in segs and segs[-1:] == ["new"]


def is_kktix_login_url(url: str) -> bool:
    segs = url_path_segments(url)
    return segs[:2] == ["users", "sign_in"] or segs[:2] == ["users", "sign_up"]


def is_kktix_held_url(url: str) -> bool:
    segs = url_path_segments(url)
    if "registrations" not in segs:
        return False
    idx = segs.index("registrations")
    return idx + 1 < len(segs) and segs[idx + 1] != "new"


def is_kktix_payment_url(url: str) -> bool:
    if not url:
        return False
    segs = url_path_segments(url)
    if segs and segs[-1] in {"pay", "payments", "payment"}:
        return True
    if "payments" in segs or "pay" in segs:
        return True
    host = (urlparse(url).hostname or "").lower()
    hints = ("adyen", "checkoutshopper", "3dsecure", "acs.")
    return any(h in host for h in hints)


def is_charity_ticket_name(name: str) -> bool:
    blob = name or ""
    return any(mark in blob for mark in KKTIX_CHARITY_MARKERS)
```

Also extend `is_login_url` is **not** required for TicketPlus; KKTIX flow will call `is_kktix_login_url` directly.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_helpers.py -q`

Expected: PASS (old + new).

- [ ] **Step 5: Commit**

```bash
git add src/utils/helpers.py tests/test_helpers.py
git commit -m "feat: detect KKTIX URLs and charity ticket names"
```

---

### Task 2: Pure ticket pick (refresh vs fallback, skip charity)

**Files:**
- Create: `src/core/kktix_select.py`
- Test: `tests/test_kktix_select.py`

**Interfaces:**
- Consumes: `area_keyword_matches`, `resolve_buy_quantity`, `is_charity_ticket_name`
- Produces:
  - `@dataclass KktixTicketRow(index: int, name: str, price_text: str, status: str, remaining: Optional[int], purchasable: bool)`
  - `@dataclass KktixPick(action: str, index: Optional[int] = None, quantity: Optional[int] = None)`
  - `pick_kktix_ticket(rows, priorities, quantity, fallback_first_available, require_exact_quantity) -> KktixPick`
  - `action` is one of `"select"`, `"fallback"`, `"refresh"`, `"wait_sale"`

Row `status`: `"not_on_sale"` | `"unavailable"` | `"sold_out"` | `"on_sale"`.
`purchasable` is True only when the row can accept a quantity (on sale, not sold out, not 暫無票券).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_kktix_select.py`:

```python
from src.core.kktix_select import KktixTicketRow, pick_kktix_ticket


def _row(index, name, price, status, remaining=None, purchasable=None):
    if purchasable is None:
        purchasable = status == "on_sale"
    return KktixTicketRow(
        index=index,
        name=name,
        price_text=price,
        status=status,
        remaining=remaining,
        purchasable=purchasable,
    )


def _atarayo(priority_status="unavailable"):
    return [
        _row(0, "全票", "3800", priority_status),
        _row(1, "全票", "3600", "on_sale"),
        _row(2, "愛心票", "1900", "on_sale"),
    ]


def test_wait_sale_when_all_not_on_sale():
    rows = [_row(0, "全票", "3800", "not_on_sale", purchasable=False)]
    pick = pick_kktix_ticket(rows, ["3800"], 2, False, False)
    assert pick.action == "wait_sale"


def test_refresh_when_priority_unavailable_without_fallback():
    pick = pick_kktix_ticket(_atarayo("unavailable"), ["3800"], 2, False, False)
    assert pick.action == "refresh"
    assert pick.index is None


def test_fallback_skips_charity():
    pick = pick_kktix_ticket(_atarayo("unavailable"), ["3800"], 2, True, False)
    assert pick.action == "fallback"
    assert pick.index == 1
    assert pick.quantity == 2


def test_never_select_charity_even_if_price_listed():
    pick = pick_kktix_ticket(_atarayo("unavailable"), ["1900"], 1, False, False)
    assert pick.action == "refresh"


def test_empty_priorities_picks_first_non_charity():
    pick = pick_kktix_ticket(_atarayo("on_sale"), [], 2, False, False)
    assert pick.action == "select"
    assert pick.index == 0


def test_charity_only_available_refreshes():
    rows = [
        _row(0, "全票", "3800", "unavailable"),
        _row(1, "愛心票", "1900", "on_sale"),
    ]
    pick = pick_kktix_ticket(rows, [], 1, True, False)
    assert pick.action == "refresh"


def test_select_matching_price():
    pick = pick_kktix_ticket(_atarayo("on_sale"), ["3600"], 2, False, False)
    assert pick.action == "select"
    assert pick.index == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_kktix_select.py -v`

Expected: FAIL, module not found.

- [ ] **Step 3: Implement `src/core/kktix_select.py`**

```python
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
    if not rows:
        return KktixPick("wait_sale")
    if rows and all(r.status == "not_on_sale" for r in rows):
        return KktixPick("wait_sale")

    eligible = _eligible(rows)
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_kktix_select.py tests/test_helpers.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/kktix_select.py tests/test_kktix_select.py
git commit -m "feat: pick KKTIX tickets with charity skip and refresh"
```

---

### Task 3: TicketConfig accepts KKTIX URLs

**Files:**
- Modify: `src/models/ticket_config.py`
- Test: `tests/test_helpers.py` (existing `test_ticket_config_validate_ok`) and add `tests/test_ticket_config_kktix.py`

**Interfaces:**
- Consumes: `detect_platform`, `extract_kktix_slug`, `extract_event_id`, `is_mock_url`
- Produces: `TicketConfig.validate()` accepts kktix.com / *.kktix.cc / mock `/events/{slug}/...`; `TicketConfig.get_kktix_slug() -> Optional[str]`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ticket_config_kktix.py`:

```python
from src.models.ticket_config import TicketConfig


def test_kktix_url_validates():
    cfg = TicketConfig(activity_url="https://kktix.com/events/sbgr01/registrations/new", quantity=2)
    assert cfg.validate() == []
    assert cfg.get_kktix_slug() == "sbgr01"


def test_kktix_organizer_subdomain_validates():
    cfg = TicketConfig(activity_url="https://binliveco.kktix.cc/events/sbgr01", quantity=4)
    assert cfg.validate() == []


def test_kktix_mock_url_validates():
    cfg = TicketConfig(
        activity_url="http://127.0.0.1:8765/events/mock-kktix/registrations/new",
        quantity=2,
    )
    assert cfg.validate() == []
    assert cfg.get_kktix_slug() == "mock-kktix"


def test_kktix_url_without_slug_fails():
    cfg = TicketConfig(activity_url="https://kktix.com/events", quantity=1)
    errors = cfg.validate()
    assert errors


def test_unknown_host_still_fails():
    cfg = TicketConfig(activity_url="https://example.com/foo", quantity=1)
    assert any("ticketplus" in e or "kktix" in e for e in cfg.validate())


def test_ticketplus_still_requires_event_id():
    cfg = TicketConfig(activity_url="https://ticketplus.com.tw/activity/not-an-id", quantity=1)
    assert cfg.validate()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_ticket_config_kktix.py -v`

Expected: FAIL (`get_kktix_slug` missing and/or URL rejected).

- [ ] **Step 3: Update `TicketConfig`**

```python
from ..utils.helpers import detect_platform, extract_event_id, extract_kktix_slug, is_mock_url

def get_kktix_slug(self) -> Optional[str]:
    return extract_kktix_slug(self.activity_url)

def validate(self) -> List[str]:
    errors: List[str] = []
    if not self.activity_url:
        errors.append("活動網址不能為空")
    else:
        platform = detect_platform(self.activity_url)
        if platform == "kktix":
            if not self.get_kktix_slug():
                errors.append("無法從 KKTIX 網址解析活動代碼")
        elif platform == "ticketplus":
            if is_mock_url(self.activity_url) and not self.get_event_id():
                errors.append("無法從模擬站網址解析 eventId")
            elif not is_mock_url(self.activity_url) and not self.get_event_id():
                errors.append("無法從活動網址解析 eventId")
        else:
            errors.append("活動網址必須是 ticketplus.com.tw、kktix.com 或本機模擬站")
    if self.quantity < 1:
        errors.append("購票張數必須大於 0")
    elif self.quantity > 4:
        errors.append("購票張數不能超過 4 張")
    return errors
```

Keep `get_event_id()` as TicketPlus-only.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_ticket_config_kktix.py tests/test_helpers.py::test_ticket_config_validate_ok tests/test_config_file.py -q`

Expected: PASS. Do not change `test_local_config_points_to_test_event`.

- [ ] **Step 5: Commit**

```bash
git add src/models/ticket_config.py tests/test_ticket_config_kktix.py
git commit -m "feat: allow KKTIX activity URLs in TicketConfig"
```

---

### Task 4: KKTIX mock site

**Files:**
- Modify: `mock/server.py`, `mock/catalog.py` (add KKTIX slug constant)
- Create: `mock/static/kktix.html`, `mock/static/kktix.js`
- Test: `tests/test_mock_site.py`

**Interfaces:**
- Consumes: none from previous Python APIs
- Produces:
  - `KKTIX_SLUG = "mock-kktix"`
  - `mock_kktix_url(host, port) -> str` = `http://{host}:{port}/events/mock-kktix/registrations/new`
  - Routes: `/events/mock-kktix/registrations/new`, `/events/mock-kktix/registrations/{id}`, `/events/mock-kktix/registrations/{id}/pay`, `/users/sign_in`
  - Query `?scenario=` values: `happy`, `presale`, `priority-unavailable`, `queue`, `need-login`, `charity-only`

DOM that page objects will use (keep these IDs/classes stable):

- `#registrationsNewApp`
- `[data-ticket-row]` with `data-name`, `data-price`, `data-status`, plus/minus and `input.ticket-quantity`
- `#person_agree_terms`
- `button[data-act="auto-seat"]` text 電腦配位
- `button[data-act="self-seat"]` text 自行選位
- `button[data-act="next"]` text 下一步
- `#queue-spinner` visible with text 查詢空位中 when queuing
- sale countdown `#sale-countdown` for presale
- login form `#login-form` with email/password on `/users/sign_in`
- payment page `#pay-app` contains `input[name="cardNumber"]` and path `/pay`

Scenarios:

| scenario | behavior |
|----------|----------|
| `happy` | 3800/3600 on_sale, 愛心票 on_sale; auto-seat → brief queue → `/registrations/held1` form with 下一步 → `/pay` |
| `presale` | all `not_on_sale` until `saleAfter` seconds (default 2) **or** until a full reload after that time; then behave as happy |
| `priority-unavailable` | 3800 `unavailable` (暫無票券), 3600 on_sale, 愛心 on_sale. After a full reload, 3800 becomes on_sale |
| `queue` | like happy but spinner 1.5s |
| `need-login` | if cookie `mock_kktix_user` missing, redirect `/users/sign_in?next=...`; login sets cookie and returns |
| `charity-only` | 3800 unavailable, only 愛心票 on_sale; reload keeps this (bot should keep refreshing) |

- [ ] **Step 1: Write failing mock-site tests**

Append to `tests/test_mock_site.py`:

```python
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
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_mock_site.py::test_kktix_mock_routes -v`

Expected: FAIL (404 or missing strings). Existing `test_mock_server_serves_activity_and_order` must still pass after implementation.

- [ ] **Step 3: Implement mock routes and pages**

`mock/catalog.py` add:

```python
KKTIX_SLUG = "mock-kktix"

def mock_kktix_url(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    return f"http://{host}:{port}/events/{KKTIX_SLUG}/registrations/new"
```

`mock/server.py` in `do_GET`, before TicketPlus prefixes:

```python
if path.startswith("/events/") or path in {"/users/sign_in", "/kktix.js"}:
    if path.endswith("/kktix.js") or path == "/kktix.js":
        self._send_file(STATIC_DIR / "kktix.js", "application/javascript; charset=utf-8")
        return
    if path.endswith("/pay"):
        self._send_file(STATIC_DIR / "kktix.html", "text/html; charset=utf-8")
        return
    self._send_file(STATIC_DIR / "kktix.html", "text/html; charset=utf-8")
    return
```

`mock/static/kktix.html` is a small shell that loads `/kktix.js` and has empty `#app`. `kktix.js` reads `location.pathname` + `scenario` query and renders the DOM listed above. Use `sessionStorage.mockKktixReloads` incremented on `pageshow`/`load` so `priority-unavailable` unlocks 3800 after reload count >= 1.

Presale: store `sessionStorage.mockKktixStart = Date.now()` on first visit; after `saleAfter` seconds **and** a reload (to satisfy sale-time F5), switch to on_sale. Also allow becoming on_sale after reload if elapsed >= saleAfter even if the in-page countdown already hit 0 (bot will F5 at T=0).

Login: `document.cookie = "mock_kktix_user=1; path=/"` on submit.

Computer-assign click: show `#queue-spinner` for 400ms (1500ms if queue scenario), then `location.href = '/events/mock-kktix/registrations/held1' + location.search`.

Held page: a single 「下一步」 going to `/events/mock-kktix/registrations/held1/pay`.

Pay page: `<input name="cardNumber">` and heading 付款.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_mock_site.py -q`

Expected: PASS both TicketPlus and KKTIX mock tests.

- [ ] **Step 5: Commit**

```bash
git add mock/server.py mock/catalog.py mock/static/kktix.html mock/static/kktix.js tests/test_mock_site.py
git commit -m "feat: add KKTIX mock registration pages"
```

---

### Task 5: KKTIX page objects

**Files:**
- Create: `src/pages/kktix/__init__.py`
- Create: `src/pages/kktix/registration_page.py`
- Create: `src/pages/kktix/login_page.py`
- Create: `src/pages/kktix/checkout_page.py`
- Test: `tests/test_kktix_pages.py` (Selenium against mock; skip if Chrome missing, same pattern as `test_mock_bot.py`)

**Interfaces:**
- Consumes: `KktixTicketRow`, `pick_kktix_ticket`, URL helpers, `BasePage`
- Produces:

`KktixRegistrationPage`:
- `open(url: str) -> None`
- `list_rows() -> list[KktixTicketRow]`
- `detect_sale_state() -> str` (`not_on_sale` / `on_sale` / `unknown`)
- `sale_at_epoch() -> Optional[float]` (unix seconds in local/page clock; None if unknown)
- `is_queue() -> bool`
- `has_recaptcha() -> bool`
- `has_question_captcha() -> bool`
- `agree_terms() -> bool`
- `set_quantity(index: int, quantity: int) -> bool`
- `click_computer_assign() -> bool` (電腦配位 if present else 下一步; never 自行選位)
- `has_invitation_field() -> bool`
- `fill_invitation(code: str) -> bool`

`KktixLoginPage`:
- `is_logged_in() -> bool`
- `has_login_form() -> bool`
- `fill_and_submit(email: str, password: str) -> bool`

`KktixCheckoutPage`:
- `dismiss_seat_notice() -> None`
- `click_advance() -> bool`
- `has_card_field() -> bool`

- [ ] **Step 1: Write a Selenium test against mock happy path widgets**

```python
# tests/test_kktix_pages.py
import time
import pytest
from mock.catalog import mock_kktix_url
from mock.server import start_mock_server
from src.core.browser import BrowserManager
from src.pages.kktix.registration_page import KktixRegistrationPage


def test_registration_page_reads_rows_and_clicks_auto_seat(tmp_path):
    server, _ = start_mock_server(port=18768)
    browser = None
    try:
        browser = BrowserManager(
            headless=True,
            user_data_dir=str(tmp_path / "c"),
            prefer_windows_chrome=False,
            page_load_timeout=20,
        )
        try:
            driver = browser.start()
        except Exception as exc:
            pytest.skip(f"無法啟動 Chrome: {exc}")
        page = KktixRegistrationPage(driver)
        page.open(mock_kktix_url(port=18768) + "?scenario=happy")
        time.sleep(0.4)
        rows = page.list_rows()
        assert any(r.price_text.find("3800") >= 0 for r in rows)
        assert any("愛心" in r.name for r in rows)
        assert page.set_quantity(0, 2)
        assert page.agree_terms()
        assert page.click_computer_assign()
    finally:
        if browser:
            browser.stop()
        server.shutdown()
        server.server_close()
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_kktix_pages.py -v`

Expected: FAIL import, or skip if no Chrome — if skip due to Chrome, still implement pages so later mock-bot can use them. Do not treat Chrome-skip as task success; unit-level `list_rows` JS can be validated when Chrome exists.

- [ ] **Step 3: Implement page objects**

`registration_page.py` `list_rows` via `execute_js` scanning `[data-ticket-row]` **and** `#registrationsNewApp .display-table-row`. Map innerText:

- 尚未開賣 / 秒後開賣 → `not_on_sale`
- 暫無票券 → `unavailable`
- 已售完 → `sold_out`
- plus button or 熱賣 / 剩 → `on_sale`
- `purchasable` = status == on_sale

`click_computer_assign`: prefer `button` whose text contains 電腦配位; else enabled `.btn-primary` in `.register-new-next-button-area` whose text is 下一步; never click 自行選位.

`is_queue`: body text 查詢空位中 or `.kk-busy-spinner--enqueue` or `#queue-spinner` displayed.

`has_question_captcha`: `.custom-captcha-inner` present.

`KktixLoginPage.is_logged_in` for mock: cookie `mock_kktix_user` or absence of `#login-form`. For real KKTIX: no `/users/sign_in` URL and no login form; nav contains 我的票券 / account menu.

`KktixCheckoutPage.click_advance`: click visible primary button 下一步 / 確認訂單 / 確認訂單並繳費 / 知道了. `has_card_field`: `input[name=cardNumber], input[autocomplete=cc-number]`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_kktix_pages.py tests/test_mock_site.py -q`

Expected: PASS or skip-only if no Chrome. Mock site tests must PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pages/kktix tests/test_kktix_pages.py
git commit -m "feat: add KKTIX registration login and checkout pages"
```

---

### Task 6: KktixFlow and BotEngine dispatch

**Files:**
- Create: `src/core/kktix_flow.py`
- Modify: `src/core/bot_engine.py`
- Modify: `src/core/browser.py` only if `open_home` needs a URL argument — prefer passing URL from flow (`driver.get`) instead of changing TicketPlus home.
- Test: `tests/test_kktix_flow.py` for decision helpers if extracted; `tests/test_mock_bot.py` remains TicketPlus. New `tests/test_kktix_mock_bot.py`.

**Interfaces:**
- Consumes: page objects, `pick_kktix_ticket`, URL helpers, `BotEngine` callbacks (`_log`, `_update_state`, `_should_stop`, `_sleep`, `_handle`-style waits)
- Produces: `KktixFlow(engine: BotEngine).run() -> bool`

`BotEngine._execute` first lines:

```python
from ..utils.helpers import detect_platform
if detect_platform(self.config.activity_url) == "kktix":
    from .kktix_flow import KktixFlow
    return KktixFlow(self).run()
```

`BotEngine._run` login wait: if KKTIX, open `https://kktix.com/` or mock registration URL (mock → activity_url; live → `https://kktix.com/`). Do not force TicketPlus home for KKTIX.

`_prepare_parallel_windows`: if platform is kktix, log that KKTIX forbids multi-window and return immediately (keep 1).

`_ensure_login` for KKTIX: use `KktixLoginPage` instead of TicketPlus `LoginPage`. Implement this inside `KktixFlow` rather than overloading TicketPlus login.

Flow loop (max_retries, same stop flag):

1. If browser dead → False.
2. If `is_kktix_payment_url` or checkout `has_card_field` → True.
3. If login URL / login form → auto-fill email/password if configured; else wait. Do not refresh registration.
4. If recaptcha or question captcha → wait human (`wait_for_human`).
5. If queue → sleep 1s, never refresh.
6. If held URL → `KktixCheckoutPage.dismiss_seat_notice`; `agree` if checkbox; `click_advance`. Never refresh.
7. If registration URL:
   - rows = list_rows(); pick = pick_kktix_ticket(...)
   - `wait_sale`: if `sale_at_epoch()` known and now >= sale_at and not yet did sale F5 → `refresh()` once, set flag. Else `_sleep()`.
   - `refresh`: `_sleep()` then `refresh()` (not during queue/hold).
   - `select` / `fallback`: set_quantity, fill invitation if field+config, agree_terms, click_computer_assign.
8. Else: navigate back to registration URL (only if not queued/held/payment).

Sale F5 flag is per run (`self._did_sale_refresh`). If already `on_sale` when booking starts, skip sale F5.

- [ ] **Step 1: Write failing mock-bot test**

Create `tests/test_kktix_mock_bot.py` modeled on `tests/test_mock_bot.py`:

```python
def test_kktix_bot_happy_reaches_pay(tmp_path):
    ...
    ticket = TicketConfig(
        activity_url=mock_kktix_url(port=18769) + "?scenario=happy",
        quantity=2,
        area_priorities=["3800"],
        account="user@example.com",
        password="mock-pass",
    )
    ...
    assert status == BotStatus.SUCCESS
```

Also:

```python
def test_kktix_bot_skips_charity_and_refreshes_priority(tmp_path):
    # scenario=priority-unavailable, fallback false, priorities ["3800"]
    # after start, should succeed by buying 3800 after reload (mock unlocks 3800)
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_kktix_mock_bot.py -v`

Expected: FAIL (KktixFlow missing or still trying TicketPlus eventId).

- [ ] **Step 3: Implement flow + dispatch**

Keep TicketPlus `_execute` body after the platform `if`.

KktixFlow should not import PyQt. Use engine methods: `_log`, `_update_state`, `_should_stop`, `_sleep`, `_browser_still_open`, `_looks_like_dead_browser`.

Invitation: if `has_invitation_field()` and `config.exclusive_code`, fill; if field present and code empty, log once and continue looping without submit.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_kktix_mock_bot.py tests/test_bot_engine.py tests/test_mock_bot.py tests/test_kktix_select.py -q`

Expected: PASS; Chrome-missing tests skip.

- [ ] **Step 5: Commit**

```bash
git add src/core/kktix_flow.py src/core/bot_engine.py tests/test_kktix_mock_bot.py
git commit -m "feat: run KKTIX computer-assignment flow from BotEngine"
```

---

### Task 7: GUI, inspect API, example config

**Files:**
- Create: `src/api/kktix_api.py`
- Modify: `src/gui/main_window.py`
- Modify: `src/main.py` (`inspect` command)
- Modify: `config/config.example.yaml`
- Test: `tests/test_kktix_api.py` (parse a fixture HTML/JSON, no network required); `tests/test_config_file.py` still loads example

**Interfaces:**
- Consumes: `extract_kktix_slug`, `detect_platform`
- Produces:
  - `fetch_kktix_catalog(url: str) -> str` formatted text
  - GUI Atarayo button, Email label when URL is KKTIX, session/code disabled hint, parallel windows forced 1, inspect branches

`kktix_api.py`:
- GET `https://kktix.com/g/events/{slug}/register_info` with UA header
- GET event page `https://kktix.com/events/{slug}` (follows organizer redirect) and regex/parse ticket table rows (name, period, price)
- Format like TicketPlus `format_catalog`
- On mock URL, return a short mock description without HTTP
- Network errors: raise; GUI shows the message
- Tests: parse a saved snippet of sbgr01 ticket table + sample register_info JSON in `tests/fixtures/kktix_register_info.json`

GUI constants:

```python
KKTIX_ATARAYO = "https://kktix.com/events/sbgr01/registrations/new"
KKTIX_MOCK = "http://127.0.0.1:8765/events/mock-kktix/registrations/new"
```

「載入 Atarayo」: url Atarayo, quantity 2, priorities 3800 / 3600 / 3200, clear session and exclusive code.

On `activity_url_input.textChanged`: if `detect_platform == kktix`, account label 「Email」, placeholder Email, `windows_spin.setValue(1); setEnabled(False)`, session placeholder 「KKTIX 不使用場次關鍵字」. Else restore TicketPlus labels and enable windows_spin.

Inspect: if kktix, call `fetch_kktix_catalog`.

`main.py` inspect: same branch.

Example yaml: keep TicketPlus default; add commented KKTIX Atarayo block.

- [ ] **Step 1: Write API unit test with fixture JSON**

```python
# tests/test_kktix_api.py
from src.api.kktix_api import format_kktix_catalog, parse_register_info

SAMPLE = {"register_status": "COMING_SOON", "tickets": [{"id": 1, "in_stock": True}]}

def test_format_coming_soon():
    text = format_kktix_catalog("sbgr01", "Atarayo", SAMPLE, [("全票", "3800"), ("愛心票", "1900")])
    assert "COMING_SOON" in text or "尚未開賣" in text
    assert "3800" in text
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_kktix_api.py -v`

- [ ] **Step 3: Implement API + GUI + example yaml comments**

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_kktix_api.py tests/test_config_file.py tests/test_ticket_config_kktix.py -q`

- [ ] **Step 5: Commit**

```bash
git add src/api/kktix_api.py src/gui/main_window.py src/main.py config/config.example.yaml tests/test_kktix_api.py
git commit -m "feat: add KKTIX inspect and GUI presets"
```

---

### Task 8: README and full test run

**Files:**
- Modify: `README.md`
- Modify: `mock/server.py` startup print to mention KKTIX URL
- Test: full `python -m pytest tests -q`

**Interfaces:** none new.

README additions (Traditional Chinese, same style as existing):

- Title can stay; add a 「支援平台」 note: TicketPlus + KKTIX（電腦配位）
- New section 「KKTIX」 covering: paste `/events/{slug}/registrations/new`, Atarayo 2026/09/05 12:00, priorities by price, charity skip, 暫無票券 refresh unless fallback checked, prefill at kktix.com/account/prefills, stop at payment, no multi-window, mock URL
- Mock table: add KKTIX scenarios
- Do not delete TicketPlus docs

- [ ] **Step 1: Update README and mock server help text**

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest tests -q`

Expected: all PASS except Chrome-dependent tests may skip.

- [ ] **Step 3: Manually sanity-check mock KKTIX in GUI** (if Chrome available): `python -m mock.server` then 「載入」 `http://127.0.0.1:8765/events/mock-kktix/registrations/new?scenario=presale`

- [ ] **Step 4: Commit**

```bash
git add README.md mock/server.py
git commit -m "docs: describe KKTIX computer-assignment booking"
```

---

## Spec coverage

| Spec requirement | Task |
|------------------|------|
| Same GUI, URL platform detect | 1, 3, 7 |
| Computer assign only | 5, 6 |
| Member prefill, click next after hold | 5, 6 |
| Sale-time F5 once | 4 (presale), 6 |
| Match price or row text | 2, 5 |
| Always skip charity | 1, 2 |
| Preferred 暫無票券 + no fallback → F5 | 2, 4, 6 |
| Fallback → first non-charity, no refresh | 2, 6 |
| No refresh in queue / hold / pay | 6 |
| Stop at payment | 5, 6 |
| Parallel windows = 1 | 6, 7 |
| Inspect register_info + event table | 7 |
| KKTIX mock + tests | 4, 5, 6, 8 |
| TicketPlus tests keep passing | every task run |
| README | 8 |
| Atarayo preset 3800/3600/3200 | 7 |
| Invitation field only if visible | 5, 6 |
| No hidden booking API | 6, 7 |

## Type names (locked)

- `detect_platform` → `"ticketplus"` \| `"kktix"` \| `""`
- `KktixTicketRow`, `KktixPick`, `pick_kktix_ticket`
- `KktixPick.action` → `"select"` \| `"fallback"` \| `"refresh"` \| `"wait_sale"`
- `KktixFlow(engine).run() -> bool`
- Mock slug `mock-kktix`
