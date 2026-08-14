(() => {
  const EVENT_ID = "a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1";
  const SESSIONS = [
    { sessionId: "b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1", name: "2026 INFINITE FANMEETING [INFINITE RALLY V] in TAIPEI（9/19場次）", date: "2026-09-19", weekday: "六", time: "18:00" },
    { sessionId: "c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1", name: "2026 INFINITE FANMEETING [INFINITE RALLY V] in TAIPEI（9/20場次）", date: "2026-09-20", weekday: "日", time: "16:00" },
  ];
  const TITLE = "2026 INFINITE FANMEETING [INFINITE RALLY V] in TAIPEI";
  const HOST = "SHOW Office Entertainment.co.ltd";
  const VENUE = "國立體育大學綜合體育館";
  const ADDRESS = "桃園市龜山區文化一路250號";
  const BANNER = "https://static.ticketplus.com.tw/event/af39103d211724c82069c4ab5e40e95c/picBigActiveMain_1786355125587.jpeg";
  const THUMB = "https://static.ticketplus.com.tw/event/af39103d211724c82069c4ab5e40e95c/picBigOrderThumbnail_1786355126555.jpeg";

  const params = new URLSearchParams(location.search);
  const storeKey = "tp-mock-state";

  function loadState() {
    const saved = JSON.parse(sessionStorage.getItem(storeKey) || "{}");
    const scenario = params.get("scenario") || saved.scenario || "presale";
    return {
      scenario,
      saleAfter: Number(params.get("saleAfter") || saved.saleAfter || 2),
      updateClicks: saved.updateClicks || 0,
      loggedIn: saved.loggedIn !== undefined ? saved.loggedIn : false,
      selected: saved.selected || {},
      hold: saved.hold || null,
      failUsed: Boolean(saved.failUsed),
      serial: saved.serial || "",
      agreed: Boolean(saved.agreed),
      refreshing: false,
      overlay: false,
      dialog: null,
      tab: saved.tab || "announce",
      queueUntil: saved.queueUntil || (scenario === "queue" ? Date.now() + 1800 : 0),
    };
  }

  const state = loadState();

  function saveState() {
    sessionStorage.setItem(
      storeKey,
      JSON.stringify({
        scenario: state.scenario,
        saleAfter: state.saleAfter,
        updateClicks: state.updateClicks,
        loggedIn: state.loggedIn,
        selected: state.selected,
        hold: state.hold,
        failUsed: state.failUsed,
        serial: state.serial,
        agreed: state.agreed,
        tab: state.tab,
        queueUntil: state.queueUntil,
      })
    );
  }

  function applyAuthCookie() {
    if (state.loggedIn) document.cookie = "user=account%3Dmock; path=/";
    else document.cookie = "user=; path=/; max-age=0";
  }

  function opened() {
    return state.updateClicks >= state.saleAfter;
  }

  function areaStatus(area) {
    const sc = state.scenario;
    if (sc === "presale" && !opened()) return { kind: "pending", remain: null };
    if (sc === "stock-later" && area.id === "vip3" && !opened()) return { kind: "sold", remain: 0 };
    if (sc === "priority-soldout" && (area.id === "vip3" || area.id === "vip4")) return { kind: "sold", remain: 0 };
    if (area.kind === "hot") return { kind: "hot", remain: null };
    if (area.kind === "sold") return { kind: "sold", remain: 0 };
    return { kind: "remain", remain: area.remain };
  }

  const AREA_TREE = [
    {
      name: "6100 區",
      color: "#111111",
      children: [
        { id: "vip3", name: "VIP3區", price: 6100, kind: "hot", color: "#c9a227" },
        { id: "vip4", name: "VIP4區", price: 6100, remain: 10, kind: "remain", color: "#d4af37" },
      ],
    },
    {
      name: "5380 區",
      color: "#e07a2f",
      children: [
        {
          name: "特B",
          color: "#e07a2f",
          children: [
            { id: "tb1", name: "特B1區", price: 5380, remain: 4, kind: "remain", color: "#e07a2f" },
            { id: "tb2", name: "特B2區", price: 5380, kind: "sold", color: "#e07a2f" },
            { id: "tb3", name: "特B3區", price: 5380, remain: 0, kind: "sold", color: "#e07a2f" },
          ],
          open: true,
        },
      ],
    },
    {
      name: "1980 區",
      color: "#2e7d4f",
      children: [
        { id: "rocka", name: "搖滾A區", price: 1980, kind: "hot", color: "#2e7d4f" },
        { id: "rockb", name: "搖滾B區", price: 1980, remain: 6, kind: "remain", color: "#43a047" },
      ],
    },
  ];

  function parseRoute() {
    const parts = location.pathname.split("/").filter(Boolean);
    const head = (parts[0] || "").toLowerCase();
    return { name: head || "home", eventId: parts[1] || EVENT_ID, sessionId: parts[2] || "" };
  }

  function sessionById(id) {
    return SESSIONS.find((s) => s.sessionId === id) || SESSIONS[0];
  }

  function money(n) {
    return "NT." + Number(n).toLocaleString("en-US");
  }

  function controlBar() {
    const options = ["happy", "presale", "priority-soldout", "stock-later", "need-login", "need-serial", "queue", "fail-once", "overlay"]
      .map((s) => `<option value="${s}" ${s === state.scenario ? "selected" : ""}>${s}</option>`)
      .join("");
    return `
      <div class="mock-control">
        <strong>模擬控制</strong>
        <label>場景 <select id="mock-scenario">${options}</select></label>
        <label>更新後開賣 <input id="mock-sale-after" type="number" min="0" max="20" value="${state.saleAfter}"></label>
        <span>已更新 ${state.updateClicks} 次</span>
        <button type="button" data-act="reset">重設</button>
      </div>`;
  }

  function header() {
    const auth = state.loggedIn
      ? `<div class="auth-box">0966***000<span role="button" class="primary-1--text ml-3 cursor-pointer" data-act="logout">登出</span></div>`
      : `<button type="button" class="login-pill" data-act="open-login"><i class="mdi mdi-account-outline"></i> 會員登入</button>`;
    return `
      <header class="headerApp v-sheet theme--light v-toolbar v-app-bar v-app-bar--fixed white" id="appBar">
        <div class="v-toolbar__content">
          <div class="cus-container">
            <div class="header-row">
              <a class="nav-item brand" href="/activity/${EVENT_ID}${location.search}"><div class="brand-logo" title="Ticket Plus"></div></a>
              <div class="nav-item">關於我們</div>
              <div class="nav-item">常見問題</div>
              <div class="nav-item">會員專區</div>
              <div class="spacer"></div>
              ${auth}
              <hr class="v-divider v-divider--vertical">
              <div class="lang-pill"><i class="mdi mdi-web"></i> 中文 <i class="mdi mdi-menu-down"></i></div>
            </div>
          </div>
        </div>
      </header>`;
  }

  function footer() {
    return `
      <footer class="site-footer v-footer">
        <div class="foot-grid">
          <div><strong>聯絡電話</strong>02-2778-1570</div>
          <div><strong>電子郵件</strong>service@farentasia.com</div>
          <div><strong>服務時間</strong>週一至週五 10:00 - 18:00 (國定假日除外)</div>
        </div>
        <div class="cus-container copy">遠大娛樂股份有限公司版權所有 © Far Entertainment Co.｜統一編號 83118342</div>
      </footer>`;
  }

  function steps(active) {
    const labels = ["選擇票區", "選擇座位", "確認資料", "付款結帳"];
    return `
      <div class="cus-container steps-bar">
        ${labels
          .map(
            (label, i) =>
              `<button type="button" class="stepNum mr-2 v-btn v-btn--fab v-btn--round ${i < active ? "active" : ""}">${i + 1}</button>${label}`
          )
          .join("")}
      </div>`;
  }

  function leafStatusHtml(area) {
    const st = areaStatus(area);
    if (st.kind === "pending") {
      return `<div class="pending-box"><div class="text-nine">2026/08/14 11:00</div><div class="text-nine">開賣時間</div></div>`;
    }
    if (st.kind === "hot") return `<span class="v-chip">熱賣中</span>`;
    if (st.kind === "sold") {
      if (area.forceSoldText) return `<span class="remain-tag soldout">已售完</span>`;
      return `<span class="remain-tag">剩餘 0</span>`;
    }
    return `<span class="remain-tag">剩餘 ${st.remain}</span>`;
  }

  function qtyBox(area) {
    const st = areaStatus(area);
    if (st.kind === "pending") return "";
    if (st.kind === "sold") return `<span class="soldout disabled-text">已售完</span>`;
    const n = state.selected[area.id] || 0;
    return `
      <div class="count-button d-flex justify-space-between align-center">
        <button type="button" class="v-btn v-btn--fab v-size--x-small" data-act="minus" data-id="${area.id}"><i class="mdi mdi-minus"></i></button>
        <div>${n}</div>
        <button type="button" class="v-btn v-btn--fab v-size--x-small" data-act="plus" data-id="${area.id}"><i class="mdi mdi-plus"></i></button>
      </div>`;
  }

  function renderArea(node, open = true) {
    const color = node.color || "#cccccc";
    if (node.children) {
      const inner = node.children.map((c) => renderArea(c, false)).join("");
      const isOpen = node.open !== undefined ? node.open : open;
      return `
        <div class="v-expansion-panel ${isOpen ? "v-expansion-panel--active" : ""}">
          <button type="button" class="v-expansion-panel-header ${isOpen ? "v-expansion-panel-header--active" : ""}" data-act="toggle">
            <span class="area-color" style="background:${color}"></span>
            <span class="grow">${node.name}</span>
          </button>
          <div class="v-expansion-panel-content"><div class="v-expansion-panels">${inner}</div></div>
        </div>`;
    }
    const st = areaStatus(node);
    const selected = (state.selected[node.id] || 0) > 0;
    const soldCls = st.kind === "sold" ? "soldout" : "";
    return `
      <div class="v-expansion-panel ${selected ? "v-expansion-panel--active" : ""} ${soldCls}">
        <button type="button" class="v-expansion-panel-header" data-act="toggle">
          <span class="area-color" style="background:${color}"></span>
          <span class="grow">${node.name}${leafStatusHtml(node)}</span>
          <span class="price">${money(node.price)}</span>
        </button>
        <div class="v-expansion-panel-content">${qtyBox(node)}</div>
      </div>`;
  }

  function totalQty() {
    return Object.values(state.selected).reduce((s, n) => s + Number(n || 0), 0);
  }

  function needSerial() {
    return state.scenario === "need-serial";
  }

  function canNextOrder() {
    if (totalQty() < 1 || !state.agreed) return false;
    if (needSerial() && !String(state.serial || "").trim()) return false;
    return true;
  }

  function installVue(hold) {
    const app = document.getElementById("app");
    app.__vue__ = { $store: { state: { order: { currentReserved: hold || null } } } };
    const eventRoot = document.querySelector(".eventClass");
    if (eventRoot) {
      eventRoot.__vue__ = {
        $data: {
          sessions: SESSIONS.map((s) => ({
            sessionId: s.sessionId,
            name: s.name,
            date: s.date,
            loadingStatusFinished: false,
          })),
        },
      };
    }
  }

  function overlayHtml() {
    if (state.queueUntil && Date.now() < state.queueUntil) {
      return `<div class="v-dialog">排隊購票中<br>請別離開頁面<br>請勿關閉網頁<br>請勿同時使用多個裝置或視窗購票</div>`;
    }
    if (!state.overlay) return "";
    return `<div class="v-overlay v-overlay--active"><div class="v-progress-circular"></div><div>電腦配位處理中</div></div>`;
  }

  function dialogHtml() {
    if (!state.dialog) return "";
    return `<div role="dialog" class="v-dialog">${state.dialog}<div><button type="button" class="nextBtn" data-act="dismiss"><span class="v-btn__content">我知道了</span></button></div></div>`;
  }

  function loginForm() {
    return `
      ${header()}
      <main class="v-main">
        <div class="login-card v-card">
          <div class="brand-logo"></div>
          <input type="tel" placeholder="手機號碼">
          <input type="password" placeholder="密碼">
          <div class="text-small cursor-pointer" style="text-align:right">忘記密碼？</div>
          <button type="button" class="nextBtn v-btn v-btn--block" data-act="login"><span class="v-btn__content">登入</span></button>
          <div class="mt-5 text-small font-weight-bold">還不是會員嗎？<span class="primary-1--text">立即註冊新帳號</span></div>
        </div>
      </main>
      ${footer()}`;
  }

  function activityTabs() {
    const tabs = [
      ["announce", "最新公告"],
      ["buy", "立即購買"],
      ["info", "活動介紹"],
      ["notice", "注意事項"],
      ["remind", "購買提醒"],
      ["pickup", "取票方式"],
      ["refund", "退票規定"],
    ];
    return tabs
      .map(([id, label]) => `<div role="tab" class="v-tab ${state.tab === id ? "v-tab--active" : ""}" data-act="tab" data-tab="${id}">${label}</div>`)
      .join("");
  }

  function renderActivity() {
    const notOnSale = state.scenario === "presale" && !opened();
    const rows = SESSIONS.map((s) => {
      const btn = notOnSale
        ? `<button class="nextBtn pending-sale float-right v-btn v-btn--block v-btn--rounded" type="button"><span class="v-btn__content">尚未開賣</span></button>`
        : `<button class="nextBtn float-right v-btn v-btn--block v-btn--rounded" type="button" data-act="buy" data-sid="${s.sessionId}"><span class="v-btn__content">立即購買</span></button>`;
      return `
        <div class="sesstion-item">
          <div class="row pa-4">
            <div class="col-info">
              <div class="col-name">${s.name}</div>
              <div class="col-date">${s.date}(${s.weekday})</div>
              <div class="col-time">${s.time}</div>
              <div class="col-place"><div class="location-content">${VENUE}<span class="text-small">${ADDRESS}</span></div></div>
            </div>
            <div class="col-status">${btn}</div>
          </div>
        </div>`;
    }).join("");
    return `
      ${header()}
      <main class="v-main">
        <div class="eventClass">
          <div class="banner-stage">
            <div class="cus-container">
              <div id="banner"><img src="${BANNER}" alt="${TITLE}"></div>
              <div class="event-below">
                <div class="domain"><i class="mdi mdi-domain"></i> ${HOST}</div>
                <h1 class="event-h1">${TITLE}</h1>
              </div>
            </div>
          </div>
          <div id="campainTabs" class="campainTabs">
            <div class="cus-container"><div class="v-tabs-bar">${activityTabs()}</div></div>
          </div>
          <div class="cus-container">
            <div class="mt-5 rwd-padding text-center bg-yellow v-card v-sheet" id="announcement">
              <h4>最新公告</h4>
              <div class="campaign-content-frame text-left">
                <p>若信用卡刷卡付款失敗，<span style="color:#ff0000">會將刷卡失敗的訂單，陸續轉為【ATM虛擬帳號付款】</span>，屆時請依「<a href="#">我的訂單</a>」顯示之「銀行帳號」、「銀行代碼」於「匯款期限」內完成付款，系統將以款項實際入帳時間為準，<span style="color:#ff0000">請於繳費後一小時至「<a href="#">我的訂單</a>」確認</span>，若訂單付款狀態顯示為「待繳費」，須等待銀行回傳付款狀態；若逾期未付款，系統收到銀行回傳付款狀態後將自動取消該筆訂單並顯示「付款失敗」，會員帳號之購票額度將於訂單取消之後釋出，各家銀行轉帳入帳時間不同，請盡早繳款以保障您的權益。</p>
                <p>※ 請留意【ATM虛擬帳號付款】<strong style="color:#ff0000">匯款期限為15分鐘</strong>。</p>
                <p>※ 刷卡付款失敗時，訂單將自動轉為【ATM虛擬帳號付款】；<strong style="color:#ff0000">若尚未顯示ATM虛擬帳號，請重整訂單頁面</strong>。</p>
              </div>
            </div>
            <div class="mt-5 rwd-padding text-center v-card v-sheet" id="buyTicket">
              <h4 class="mb-3">立即購買</h4>
              <div class="session-head">
                <div class="col-info">
                  <div class="col-name">場次名稱</div>
                  <div class="col-date">場次日期</div>
                  <div class="col-time">場次時間</div>
                  <div class="col-place">場次地點</div>
                </div>
                <div class="col-status">售票狀態</div>
              </div>
              ${rows}
            </div>
            <div class="mt-5 rwd-padding text-center v-card v-sheet" id="activityInfo">
              <h4>活動介紹</h4>
              <div class="campaign-content-frame text-left">
                <p><strong>${TITLE}</strong></p>
                <p>主辦：${HOST}</p>
                <p>地點：${VENUE}（${ADDRESS}）</p>
              </div>
            </div>
            <div class="mt-5 rwd-padding text-center v-card v-sheet" id="notice">
              <h4>注意事項</h4>
              <div class="campaign-content-frame text-left">
                <ol>
                  <li>消費者須以真實姓名、手機號碼購票及填寫有效個人資訊。</li>
                  <li>請確實核對訂購內容，票券一經售出，表示購票人同意支付本次交易的內容與價格。</li>
                  <li>本模擬站僅供驗證搶票流程，畫面中的「付款方式」「訂單成立」不是真正付款頁。</li>
                </ol>
              </div>
            </div>
          </div>
        </div>
      </main>
      ${footer()}`;
  }

  function renderOrder(session) {
    const trees = AREA_TREE.map((g) => renderArea(g, true)).join("");
    const nextDisabled = canNextOrder() ? "" : "disabled";
    const serialValue = String(state.serial || "").replace(/"/g, "&quot;");
    return `
      ${header()}
      <main class="v-main">
        <div class="order-page">
        <div class="order-hero">
          <div class="cus-container order-hero-inner">
            <img class="order-thumb" src="${THUMB}" alt="">
            <div class="order-meta">
              <h1>${TITLE}</h1>
              <div>${session.name}</div>
              <div>${session.date}　${session.time}</div>
              <div>${VENUE}（${ADDRESS}）</div>
              <div>${HOST}</div>
            </div>
          </div>
        </div>
        ${steps(1)}
        <div class="cus-container seats-area">
          <div class="seats-title">票區一覽</div>
          <div class="v-expansion-panels">${trees}</div>
          <div class="order-code-row">
            <input type="text" value="${serialValue}" data-act="serial" autocomplete="off">
          </div>
          <label class="agree-row"><input type="checkbox" data-act="agree" ${state.agreed ? "checked" : ""}> 我已閱讀並同意注意事項</label>
          <div class="order-footer">
            <div class="seat-mode">電腦選位</div>
            <button type="button" class="ghost">清除選擇</button>
            <button type="button" class="nextBtn ${canNextOrder() ? "" : "disabledBtn"}" ${nextDisabled} data-act="order-next"><span class="v-btn__content">下一步</span></button>
          </div>
        </div>
        <div class="cus-container">
          <div class="mt-5 rwd-padding v-card v-sheet" id="notice">
            <h4>注意事項</h4>
            <div class="campaign-content-frame">付款方式、訂單成立僅為注意事項內文，此頁不是付款頁。</div>
          </div>
        </div>
        </div>
      </main>
      ${footer()}
      <button type="button" class="float-btn white--text v-btn v-btn--rounded" data-act="refresh">
        ${state.refreshing ? `<span class="v-progress-circular"></span>` : `<span class="v-btn__content">更新票數<i class="mdi mdi-refresh"></i></span>`}
      </button>`;
  }

  function renderConfirmSeat(session) {
    const hold = state.hold;
    const info = hold ? `已為您電腦配位 ${hold.tickets[0].count} 張 / ${hold.tickets[0].ticketAreaName}` : "等待電腦配位結果";
    return `
      ${header()}
      <main class="v-main">
        ${steps(2)}
        <div class="cus-container">
          <div class="mt-5 rwd-padding v-card v-sheet">
            <h4>選擇座位</h4>
            <p>${session.name}</p>
            <p>${info}</p>
            <div class="order-footer">
              <button type="button" class="nextBtn" data-act="to-confirm"><span class="v-btn__content">下一步</span></button>
            </div>
          </div>
        </div>
      </main>
      ${footer()}`;
  }

  function renderConfirm(session) {
    return `
      ${header()}
      <main class="v-main">
        ${steps(3)}
        <div class="cus-container">
          <div class="mt-5 rwd-padding v-card v-sheet">
            <h4>確認資料</h4>
            <p>${session.name}</p>
            <div class="radio-row"><label><input type="radio" name="pickup"> ibon 超商取票</label></div>
            <div class="radio-row"><label><input type="radio" name="pickup"> 現場取票</label></div>
            <div class="radio-row"><label><input type="radio" name="pay"> 信用卡付款</label></div>
            <label class="agree-row"><input type="checkbox" data-act="agree" ${state.agreed ? "checked" : ""}> 我已閱讀並同意注意事項</label>
            <div class="order-footer">
              <button type="button" class="nextBtn" data-act="to-checkout"><span class="v-btn__content">下一步</span></button>
            </div>
          </div>
        </div>
      </main>
      ${footer()}`;
  }

  function renderCheckout() {
    return `
      ${header()}
      <main class="v-main">
        ${steps(4)}
        <div class="cus-container">
          <div class="mt-5 rwd-padding text-center v-card v-sheet">
            <h4>付款結帳</h4>
            <p>此為模擬付款頁。搶票工具應在此停止，改由人工完成付款。</p>
          </div>
        </div>
      </main>
      ${footer()}`;
  }

  function renderHome() {
    return renderActivity();
  }

  function wrap(inner) {
    return `<div class="v-application--wrap"><div class="grey lighten-2">${inner}${overlayHtml()}${dialogHtml()}</div></div>${controlBar()}`;
  }

  function render() {
    applyAuthCookie();
    const route = parseRoute();
    const session = sessionById(route.sessionId);
    const showLogin = !state.loggedIn && (route.name === "login" || params.get("login") === "1");
    let body = "";
    if (showLogin || route.name === "login") body = loginForm();
    else if (route.name === "order" && state.scenario === "need-login" && !state.loggedIn) body = loginForm();
    else if (route.name === "order") body = renderOrder(session);
    else if (route.name === "confirmseat") body = renderConfirmSeat(session);
    else if (route.name === "confirm") body = renderConfirm(session);
    else if (route.name === "checkout" || route.name === "done") body = renderCheckout();
    else body = renderActivity();

    const app = document.getElementById("app");
    app.innerHTML = wrap(body);
    document.title = `${TITLE} - Ticket Plus遠大售票系統`;
    installVue(state.hold);
    bind();
  }

  function go(path) {
    saveState();
    history.pushState({}, "", path);
    render();
  }

  function setHoldFromSelection() {
    const picked = Object.entries(state.selected).find(([, n]) => n > 0);
    const id = picked ? picked[0] : "vip3";
    const qty = picked ? picked[1] : 1;
    const names = { vip3: "VIP3區", vip4: "VIP4區", tb3: "特B3區", rocka: "搖滾A區", rockb: "搖滾B區", tb1: "特B1區" };
    state.hold = {
      errCode: "00",
      remainSecond: 600,
      tickets: [{ count: qty, ticketAreaName: names[id] || id, seats: Array.from({ length: qty }, (_, i) => ({ ticketAreaName: names[id] || id, seatId: i + 1 })) }],
    };
    saveState();
  }

  function bind() {
    const scenarioEl = document.getElementById("mock-scenario");
    if (scenarioEl) {
      scenarioEl.addEventListener("change", () => {
        sessionStorage.removeItem(storeKey);
        const next = new URL(location.href);
        next.searchParams.set("scenario", scenarioEl.value);
        location.href = next.toString();
      });
    }
    const saleEl = document.getElementById("mock-sale-after");
    if (saleEl) {
      saleEl.addEventListener("change", () => {
        state.saleAfter = Number(saleEl.value || 0);
        saveState();
      });
    }
    document.querySelectorAll("[data-act]").forEach((el) => {
      if (el.dataset.act === "serial") {
        el.addEventListener("input", () => {
          state.serial = el.value;
          saveState();
          render();
        });
        return;
      }
      el.addEventListener("click", () => {
        const act = el.dataset.act;
        if (act === "tab") {
          state.tab = el.dataset.tab;
          saveState();
          render();
          const target = { announce: "announcement", buy: "buyTicket", info: "activityInfo", notice: "notice" }[state.tab];
          if (target && document.getElementById(target)) document.getElementById(target).scrollIntoView({ behavior: "smooth", block: "start" });
          return;
        }
        if (act === "toggle") {
          el.closest(".v-expansion-panel").classList.toggle("v-expansion-panel--active");
          return;
        }
        if (act === "plus") {
          state.selected[el.dataset.id] = Math.min(4, (state.selected[el.dataset.id] || 0) + 1);
          saveState();
          render();
          return;
        }
        if (act === "minus") {
          state.selected[el.dataset.id] = Math.max(0, (state.selected[el.dataset.id] || 0) - 1);
          saveState();
          render();
          return;
        }
        if (act === "agree") {
          state.agreed = el.checked;
          saveState();
          render();
          return;
        }
        if (act === "refresh") {
          state.refreshing = true;
          state.updateClicks += 1;
          saveState();
          render();
          setTimeout(() => {
            state.refreshing = false;
            saveState();
            render();
          }, 350);
          return;
        }
        if (act === "buy") {
          if (state.scenario === "need-login" && !state.loggedIn) {
            go(`/login${location.search}`);
            return;
          }
          go(`/order/${EVENT_ID}/${el.dataset.sid}${location.search}`);
          return;
        }
        if (act === "order-next") {
          if (!canNextOrder()) return;
          if (state.scenario === "fail-once" && !state.failUsed) {
            state.failUsed = true;
            state.dialog = "購票失敗<br>您選擇的票種已售完";
            saveState();
            render();
            return;
          }
          const delay = state.scenario === "overlay" ? 1200 : 350;
          state.overlay = true;
          render();
          setTimeout(() => {
            state.overlay = false;
            setHoldFromSelection();
            go(`/confirmSeat/${EVENT_ID}/${parseRoute().sessionId}${location.search}`);
          }, delay);
          return;
        }
        if (act === "to-confirm") {
          go(`/confirm/${EVENT_ID}/${parseRoute().sessionId}${location.search}`);
          return;
        }
        if (act === "to-checkout") {
          go(`/checkout/${EVENT_ID}/${parseRoute().sessionId}${location.search}`);
          return;
        }
        if (act === "dismiss") {
          state.dialog = null;
          saveState();
          render();
          return;
        }
        if (act === "login") {
          state.loggedIn = true;
          saveState();
          applyAuthCookie();
          go(`/activity/${EVENT_ID}${location.search}`);
          return;
        }
        if (act === "logout") {
          state.loggedIn = false;
          saveState();
          applyAuthCookie();
          render();
          return;
        }
        if (act === "open-login") {
          go(`/login${location.search}`);
          return;
        }
        if (act === "reset") {
          sessionStorage.removeItem(storeKey);
          location.reload();
        }
      });
    });
  }

  window.addEventListener("popstate", render);
  if (state.queueUntil && Date.now() < state.queueUntil) {
    setTimeout(render, state.queueUntil - Date.now() + 30);
  }
  render();
})();
