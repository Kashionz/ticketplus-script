(() => {
  const SLUG = "mock-kktix";
  const params = new URLSearchParams(location.search);
  const scenario = params.get("scenario") || "happy";
  const saleAfter = Number(params.get("saleAfter") || 2);
  const path = location.pathname || "/";
  const isLogin = path === "/users/sign_in" || path.endsWith("/users/sign_in");
  const isPay = /\/registrations\/[^/]+\/pay\/?$/.test(path);
  const isNew = /\/registrations\/new\/?$/.test(path);
  const isHeld = /\/registrations\//.test(path) && !isNew && !isPay;

  const reloads = Number(sessionStorage.getItem("mockKktixReloads") || "0");
  let reloadMarked = false;
  function markReload() {
    if (reloadMarked || !isNew) return;
    reloadMarked = true;
    sessionStorage.setItem("mockKktixReloads", String(reloads + 1));
  }
  window.addEventListener("pageshow", markReload);
  window.addEventListener("load", markReload);

  if (!sessionStorage.getItem("mockKktixStart")) {
    sessionStorage.setItem("mockKktixStart", String(Date.now()));
  }
  const startedAt = Number(sessionStorage.getItem("mockKktixStart"));
  const saleAtMs = startedAt + saleAfter * 1000;

  function hasUser() {
    return document.cookie.split(";").some((part) => part.trim().startsWith("mock_kktix_user="));
  }

  function qs() {
    return location.search || "";
  }

  function tickets() {
    const happy = [
      { name: "全票", price: "3800", status: "on_sale" },
      { name: "全票", price: "3600", status: "on_sale" },
      { name: "愛心票", price: "1900", status: "on_sale" },
    ];
    if (scenario === "charity-only") {
      return [
        { name: "全票", price: "3800", status: "unavailable" },
        { name: "全票", price: "3600", status: "unavailable" },
        { name: "愛心票", price: "1900", status: "on_sale" },
      ];
    }
    if (scenario === "priority-unavailable") {
      return [
        { name: "全票", price: "3800", status: reloads >= 1 ? "on_sale" : "unavailable" },
        { name: "全票", price: "3600", status: "on_sale" },
        { name: "愛心票", price: "1900", status: "on_sale" },
      ];
    }
    if (scenario === "presale") {
      const elapsed = (Date.now() - startedAt) / 1000;
      const unlocked = elapsed >= saleAfter && reloads >= 1;
      if (!unlocked) {
        return happy.map((row) => Object.assign({}, row, { status: "not_on_sale" }));
      }
    }
    return happy;
  }

  function statusLabel(status, remainSec) {
    if (status === "unavailable") return "暫無票券";
    if (status === "sold_out") return "已售完";
    if (status === "not_on_sale") {
      const sec = Math.max(0, Math.ceil(remainSec));
      return sec > 0 ? `尚未開賣 ${sec}秒後開賣` : "尚未開賣 0秒後開賣";
    }
    return "熱賣中";
  }

  function renderTicketRows() {
    const remainSec = (saleAtMs - Date.now()) / 1000;
    return tickets()
      .map((row) => {
        const buyable = row.status === "on_sale";
        const qty = buyable
          ? `<span class="qty">
              <button type="button" data-act="minus">-</button>
              <input class="ticket-quantity" type="number" min="0" max="4" value="0">
              <button type="button" data-act="plus">+</button>
            </span>`
          : `<span class="qty"></span>`;
        const klass = row.status === "on_sale" ? "status-onsale" : "status-unavailable";
        return `<div class="display-table-row" data-ticket-row data-name="${row.name}" data-price="${row.price}" data-status="${row.status}">
          <span>${row.name}</span>
          <span>TWD$${row.price}</span>
          <span class="${klass}">${statusLabel(row.status, remainSec)}</span>
          ${qty}
        </div>`;
      })
      .join("");
  }

  function countdownHtml() {
    if (scenario !== "presale") return "";
    const remainSec = Math.max(0, (saleAtMs - Date.now()) / 1000);
    const saleAt = Math.floor(saleAtMs / 1000);
    return `<div id="sale-countdown" data-sale-at="${saleAt}">尚未開賣，${Math.ceil(remainSec)} 秒後開賣</div>`;
  }

  function renderNew() {
    return `
      <div id="registrationsNewApp">
        <header>
          <div class="brand">KKTIX</div>
          <div>模擬活動 mock-kktix · ${scenario}</div>
        </header>
        ${countdownHtml()}
        <div id="queue-spinner">查詢空位中，請勿重新讀取或關閉此頁</div>
        <div class="ticket-table">${renderTicketRows()}</div>
        <label><input type="checkbox" id="person_agree_terms"> 我已閱讀並同意服務條款</label>
        <div class="register-new-next-button-area">
          <button type="button" data-act="self-seat">自行選位</button>
          <button type="button" data-act="auto-seat">電腦配位</button>
          <button type="button" data-act="next">下一步</button>
        </div>
      </div>`;
  }

  function renderHeld() {
    return `
      <div class="held-box" id="registrationsNewApp">
        <div class="btn-group-for-seat">
          <button type="button" class="btn btn-primary" data-act="confirm-seat">
            確認座位 <span class="badge">2</span>
          </button>
          <div class="dropdown-block" id="seat-dropdown">
            <div class="ticket-bar">
              <div class="total">
                <a href="javascript:void(0)" class="btn btn-primary" data-act="finish-seat">完成選位</a>
              </div>
              <ul class="ticket-list">
                <li class="ticket"><span class="ticket-seat">全區 13排 33號</span></li>
                <li class="ticket"><span class="ticket-seat">全區 13排 34號</span></li>
              </ul>
            </div>
          </div>
        </div>
        <div id="held-form" hidden>
          <h1>確認報名資料</h1>
          <p>劃位完成，請確認資料後按下一步。</p>
          <div class="register-new-next-button-area">
            <button type="button" data-act="next">下一步</button>
          </div>
        </div>
      </div>`;
  }

  function renderPay() {
    return `
      <div id="pay-app">
        <h1>付款</h1>
        <label>卡號 <input name="cardNumber" autocomplete="cc-number"></label>
      </div>`;
  }

  function renderLogin() {
    return `
      <form id="login-form">
        <h1>會員登入</h1>
        <label>Email <input type="email" name="email" autocomplete="username"></label>
        <label>密碼 <input type="password" name="password" autocomplete="current-password"></label>
        <button type="submit">登入</button>
      </form>`;
  }

  function showQueueThenHold() {
    const spinner = document.getElementById("queue-spinner");
    if (spinner) {
      spinner.classList.add("is-visible");
      spinner.hidden = false;
    }
    const ms = scenario === "queue" ? 1500 : 400;
    setTimeout(() => {
      location.href = `/events/${SLUG}/registrations/held1` + qs();
    }, ms);
  }

  function bind(root) {
    root.addEventListener("click", (event) => {
      const btn = event.target.closest("[data-act]");
      if (!btn) return;
      const act = btn.getAttribute("data-act");
      if (act === "plus" || act === "minus") {
        const row = btn.closest("[data-ticket-row]");
        if (!row || row.getAttribute("data-status") !== "on_sale") return;
        const input = row.querySelector("input.ticket-quantity");
        if (!input) return;
        let n = Number(input.value || 0);
        n = act === "plus" ? n + 1 : n - 1;
        input.value = String(Math.max(0, Math.min(4, n)));
        return;
      }
      if (act === "auto-seat") {
        showQueueThenHold();
        return;
      }
      if (act === "confirm-seat") {
        const drop = document.getElementById("seat-dropdown");
        if (drop) drop.classList.toggle("show");
        return;
      }
      if (act === "finish-seat") {
        const group = document.querySelector(".btn-group-for-seat");
        const form = document.getElementById("held-form");
        if (group) group.hidden = true;
        if (form) form.hidden = false;
        return;
      }
      if (act === "next") {
        if (isHeld) {
          location.href = `/events/${SLUG}/registrations/held1/pay` + qs();
          return;
        }
        if (isNew) showQueueThenHold();
      }
    });

    const login = root.querySelector("#login-form");
    if (login) {
      login.addEventListener("submit", (event) => {
        event.preventDefault();
        document.cookie = "mock_kktix_user=1; path=/";
        const next = params.get("next") || `/events/${SLUG}/registrations/new`;
        location.href = next;
      });
    }
  }

  function tickCountdown() {
    const el = document.getElementById("sale-countdown");
    if (!el || scenario !== "presale") return;
    const remainSec = Math.max(0, (saleAtMs - Date.now()) / 1000);
    el.textContent = remainSec > 0 ? `尚未開賣，${Math.ceil(remainSec)} 秒後開賣` : "尚未開賣，0 秒後開賣";
    document.querySelectorAll("[data-ticket-row][data-status='not_on_sale'] .status-unavailable").forEach((node) => {
      node.textContent = statusLabel("not_on_sale", remainSec);
    });
  }

  const app = document.getElementById("app");
  if (!app) return;

  if (isLogin) {
    app.innerHTML = renderLogin();
    bind(app);
    return;
  }

  if (scenario === "need-login" && !hasUser() && (isNew || isHeld || isPay)) {
    const next = encodeURIComponent(path + qs());
    location.replace("/users/sign_in?next=" + next);
    return;
  }

  if (isPay) {
    app.innerHTML = renderPay();
    return;
  }
  if (isHeld) {
    app.innerHTML = renderHeld();
    bind(app);
    return;
  }

  app.innerHTML = renderNew();
  bind(app);
  if (scenario === "presale") {
    tickCountdown();
    setInterval(tickCountdown, 200);
  }
})();
