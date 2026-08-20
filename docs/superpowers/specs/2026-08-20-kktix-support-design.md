# KKTIX 電腦配位購票支援

日期：2026-08-20  
狀態：待實作  
範圍：在現有購票助手中加入 KKTIX 電腦配位流程，同一套 GUI，用網址判斷平台。

## 目標

讓使用者用現有「啟動瀏覽器 → 登入 → 開始搶票」流程，對 KKTIX 活動做到：

1. 開賣當下整點強制 F5
2. 依票種優先級（價格或列文字）選張數
3. 勾條款，按「電腦配位」或「下一步」
4. 查詢空位時不重整
5. 鎖票後只往下點（表單靠 KKTIX 會員預填）
6. 進付款頁就停，信用卡與 3D 交給使用者

正式目標活動：

- 名稱：Atarayo ASIA TOUR 2026『夕立が去ったその後で』in TAIPEI
- 購票網址：`https://kktix.com/events/sbgr01/registrations/new`
- 活動頁：`https://binliveco.kktix.cc/events/sbgr01`
- 開賣：2026-09-05 12:00（+0800）
- 每人限 4 張、信用卡、電腦配位（配完可在時限內手動換位，本工具不自動換位）
- 票種活動頁上幾乎都叫「全票」，差在價格：3800 / 3600 / 3200 / 3000 / 2600；另有愛心票 1900 / 1500

開發對照：

- 電腦配位實場：`https://kktix.com/events/yuurihk2026/registrations/new`
- 流程參考（非官方）：`https://toolweb.app/tools/kktix-practice`
- 自行選位實場僅作對照，**第一版不支援**：`https://kktix.com/events/ldfeewe-02/registrations/new`

## 非目標（第一版不做）

- 不操作座位圖、不自動換位、不按「自行選位」
- 不自動填寫報名人／身分證等表單欄位（使用者事先在 [報名預填資料](https://kktix.com/account/prefills) 填好）
- 不自動解活動問答（`.custom-captcha-inner`）、不繞過 reCAPTCHA、不打隱藏下單 API
- 不代填信用卡、不完成 3D
- KKTIX 同時視窗固定為 1（此活動明示多開會失敗）
- 不把 TicketPlus 流程重寫成完整 platform plugin 框架；只抽 KKTIX 策略，遠大路徑維持可測

原則與現有 README 一致：只點官方畫面上看得到的按鈕與輸入框。

## KKTIX 現況（實測）

購票頁是 AngularJS SPA，殼在 `https://kktix.com/events/{slug}/registrations/new`。

| 項目 | 內容 |
|------|------|
| 根節點 | `#registrationsNewApp`，controller `RegistrationsNewCtrl` |
| 票種列表 | `registrations/tickets.html`；有座位圖時 `hasArena()` 會顯示 `arenas-map` |
| 條款 | `#person_agree_terms`，`ng-model="conditions.agreeTerm"` |
| 下一步 | `ng-click="challenge()"`，按鈕在 `.register-new-next-button-area` |
| 電腦配位 | 當 `isBookingSkippable` 為真時，另有按鈕 `ng-click="challenge(1)"`，文案「電腦配位」；左邊是「自行選位」 |
| 排隊 | `TIXGLOBAL.queueApi.host = queue.kktix.com`；忙碌時文案「查詢空位中，請勿重新讀取或關閉此頁」 |
| 開賣狀態 | 公開 JSON `GET https://kktix.com/g/events/{slug}/register_info` 的 `register_status`：`COMING_SOON` / `IN_STOCK` / `SOLD_OUT` / `OUT_OF_STOCK` |
| 票種庫存 | 同上 `tickets[].in_stock`、`sections[].stock_level`（`IN_STOCK` / `NEARLY_SOLD_OUT`）。**搶票過程不下單、不靠這支 API 送出** |
| 登入 | `https://kktix.com/users/sign_in`；需已驗證 Email 與手機 |
| 付款 | Adyen checkoutshopper + 信用卡 3D |

`register_info` 在 sbgr01 回 `COMING_SOON`；yuurihk2026 / ldfeewe-02 回 `IN_STOCK`。Inspect 可以用它，搶票迴圈以畫面為準。

## 產品決策

| 決策 | 選擇 |
|------|------|
| 選位模式 | 電腦配位；有「電腦配位」按鈕就按它，否則按「下一步」 |
| 表單 | 會員預填；程式只勾已出現的條款並按下一步 |
| 整合方式 | 同一 GUI，用網址自動判斷 `ticketplus` / `kktix` / `mock` |
| 開賣瞬間 | 整點強制 F5 一次，不要只等畫面解鎖 |
| 票種優先 | 沿用「票區優先級」清單，比對該列可見文字（可填 `3800` 或區名） |
| 愛心票 | **一律排除**（名稱含愛心／身障／身心障礙／陪同）。價格對到也不買 |
| 優先區暫無票券 | 未勾「改買第一個可購」時整頁重整；有勾則改買第一個非愛心可購種 |
| 問答 | 停住等使用者，不自動填 |
| 測試 | 單元測試 + 本機 KKTIX 模擬站；遠大既有測試必須繼續過 |

## 架構

BotEngine 繼續負責 Chrome、背景執行緒、登入等待、停止、日誌、成功提示。`_execute()` 開頭依平台分流：`kktix` 呼叫 `KktixFlow.run()`，其餘走現有遠大迴圈。不要把 KKTIX 判斷散進遠大的 URL 分支裡。

```
GUI / CLI
    │
    ▼
TicketConfig  ── detect_platform(url) → ticketplus | kktix | mock
    │
    ▼
BotEngine
    ├─ 遠大：現有 _execute() 迴圈，行為不變
    └─ KktixFlow.run()
            ├─ KktixLoginPage
            ├─ KktixRegistrationPage   /registrations/new
            └─ KktixCheckoutPage       鎖票後填表／確認，只按下一步
```

| 模組 | 職責 | 依賴 |
|------|------|------|
| `src/utils/helpers.py` | `detect_platform`、`extract_kktix_slug`、KKTIX URL 分類、付款判定、愛心票名稱判定 | 無 |
| `src/models/ticket_config.py` | KKTIX 網址合法；slug 可解析；張數 1–4 | helpers |
| `src/pages/kktix/registration_page.py` | 開賣／倒數、票種列、張數、條款、電腦配位、查詢空位、暫無票券 | BasePage |
| `src/pages/kktix/login_page.py` | 偵測 KKTIX 登入表單；有帳密則填 Email／密碼 | BasePage |
| `src/pages/kktix/checkout_page.py` | 鎖票後：關通知、勾剩餘條款、按下一步／確認；不改表單欄位 | BasePage |
| `src/core/kktix_flow.py` | KKTIX 主迴圈 | 上述 pages、TicketConfig |
| `src/api/kktix_api.py` | Inspect：活動頁票種表 + `register_info` 狀態 | requests |
| GUI | 網址含 kktix 時切文案、停用遠大專用欄、載入 Atarayo 預設、同時視窗鎖 1 | BotEngine |

`detect_platform(url)`：

- host 含 `ticketplus.com.tw` → `ticketplus`
- host 為 `kktix.com` 或 `*.kktix.cc` → `kktix`
- 本機 mock host → 依 path：`/activity/` 為 ticketplus mock，`/events/` 為 kktix mock
- 其他 → 驗證失敗

不在第一版做通用 plugin registry。遠大 `pages/activity_page.py`、`order_page.py` 不為了 KKTIX 改行為。

## 狀態機

成功條件：到達付款畫面（信用卡欄、Adyen iframe、或 3D 網域）。之後引擎停止自動化，瀏覽器保持開啟。

```
啟動瀏覽器
    │
    ▼
開 kktix.com 或活動頁，等待登入
    │  按「開始搶票」
    ▼
前往 /events/{slug}/registrations/new
    │
    ├─ 未登入 ────────────────────────► 停在登入頁（可自動填 Email／密碼）
    ├─ reCAPTCHA 或活動問答 ──────────► 停住等使用者，不重整
    ├─ 「查詢空位中」／queue spinner ──► 停住，禁止 refresh、禁止重選
    ├─ 尚未開賣（COMING_SOON／倒數）──► 等到開賣時刻，整點 F5 一次
    ├─ 已開賣且尚未鎖票 ─────────────► 選票種／張數／勾條款／電腦配位
    ├─ 優先種暫無票券且不走備選 ─────► 間隔後整頁 F5，重選優先種
    ├─ 優先種沒票但允許備選 ─────────► 改買第一個非愛心可購種，不重整
    ├─ 已鎖票（劃位完成／填表／確認）─► 只按下一步，不重選、不重整
    └─ 付款頁／3D ──────────────────► SUCCESS
```

### 整點 F5

「整點」以購票頁顯示的開賣時間為準（票種列倒數或「尚未開賣」旁的時間），時區 Asia/Taipei。

1. 進入購票頁後先讀取開賣時刻 `sale_at`。若畫面已可選數量或狀態已是開賣，**跳過整點 F5**，直接選票。
2. 現在時間 `< sale_at`：留在本頁等待，不要高頻 F5。
3. 時鐘到達 `sale_at`（允許 0–200ms 誤差）：**恰好重整一次**。
4. 若讀不到 `sale_at`，改看倒數：剩餘 ≤ 0 時重整一次。
5. 重整後若畫面仍未開賣（時鐘偏差）：之後才依 `refresh_interval` 再重整，直到出現可選數量或「已售完／暫無票券」。
6. 一旦判定已開賣，**禁止再走「整點 F5」**。
7. 查詢空位中、已鎖票、付款頁：**永遠不 F5**。
8. 開賣後、尚未鎖票時，優先種顯示「暫無票券」（或同等不可購）且 `fallback_first_available=false`：依 `refresh_interval` **整頁重整**，重整後重新選票。這與整點那一次 F5 分開，可重複直到選到或停止。

### 選票種與張數

對每一列可見文字（票種名 + 價格 + 狀態）做與現有 `area_keyword_matches` 相同的正規化比對。

**愛心票一律排除。** 列名含「愛心」「身障」「身心障礙」「陪同」的票種永不選入，即使優先級填了對應價格（例如 `1900`）、清單空白、或走備選第一個可購。

其餘規則：

- 優先級由上到下。使用者可填 `3800`、`3600`、或購票頁看得到的區名。
- 清單空白：選第一個可購的非愛心列。
- `fallback_first_available=true`：優先列都沒票（暫無票券／已售完／張數不夠）時，改買畫面上第一個可購的非愛心種，**不重整**。
- `fallback_first_available=false`：優先列都沒票時**不改買別種**。若畫面是「暫無票券」或同等不可購，等 `refresh_interval` 後整頁 F5，再從頭比對優先級。
- 畫面上所有非愛心種都不可購（無論是否勾備選）：同樣整頁 F5 等待釋票。
- 張數：沿用 `resolve_buy_quantity`。剩餘不足且 `require_exact_quantity=false` 時改買剩餘；為 true 則視該列沒票，走上面備選／重整規則。
- 已選定張數且下一步可按：送出，不要為了「再看有沒有更好的」而重整。
- 有「電腦配位」按鈕時按它；沒有則按「下一步」。不要按「自行選位」。

### 鎖票後

出現系統選位通知時按「知道了」之類的關閉，不要改座位。填表頁不改 input。若下一步仍因必填欄空白而無法點：日誌提示去補預填資料或手動填，然後停在該頁等使用者；使用者填完後程式可繼續按下一步。不要為了填表而重整。

## URL 與成功判定

只看 URL 與少數付款 iframe，不看活動文案裡的「付款」。

| 判定 | 規則 |
|------|------|
| 購票頁 | path 含 `/events/{slug}/registrations/new` |
| 登入 | path 以 `/users/sign_in`、`/users/sign_up` 開頭 |
| 鎖票後流程 | `/events/{slug}/registrations/` 且不是 `new`（填表、劃位、確認） |
| 付款成功結束 | host 含 `adyen`、`checkoutshopper`、`3dsecure`、`acs.`，或 path 含 `/payments`、`/pay`；或頁面出現信用卡卡號欄且網址已離開 `registrations/new` |

遠大既有 `is_payment_url` 保持不變。KKTIX 用獨立函數，由 `KktixFlow` 呼叫。

## 設定與 GUI

`TicketConfig` 欄位不新增多餘項。KKTIX 解讀如下：

| 欄位 | KKTIX |
|------|------|
| `activity_url` | 活動頁或 `/registrations/new` 均可；正規化成 slug |
| `target_session` | 忽略（一個 slug 一場）。GUI 在 KKTIX 網址時停用或註明無效 |
| `quantity` | 1–4（Atarayo 上限 4） |
| `area_priorities` | 票種列文字／價格 |
| `exclusive_code` | 僅當畫面出現邀請碼欄才填；否則忽略 |
| `account` / `password` | KKTIX 登入為 Email + 密碼。GUI 標籤在偵測到 KKTIX 時改為「Email」 |
| `fallback_first_available` | `false`（預設）：優先種暫無票券就 F5 等待。`true`：改買第一個非愛心可購種 |
| `require_exact_quantity` | 與遠大相同 |
| `parallel_windows` | KKTIX 強制 1；GUI 鎖定並提示 |

預設按鈕新增「載入 Atarayo」：

- 網址：`https://kktix.com/events/sbgr01/registrations/new`
- 張數：2
- 優先級：`3800`、`3600`、`3200`（可再改）
- 場次、序號空白

「查看活動資料」在 KKTIX 網址時改打 `kktix_api`：列出票種名稱、價格、販售時間、`register_status`。不要開瀏覽器。

## 錯誤處理

| 情況 | 行為 |
|------|------|
| 未登入 | 停在登入，不刷購票頁。有 Email／密碼則自動填送；有 reCAPTCHA 則等使用者 |
| 手機／Email 未驗證提示 | 日誌說明，停住等使用者去驗證 |
| reCAPTCHA | `wait_for_human=true` 時停住 |
| 活動問答 | 停住等使用者輸入，不解析題目 |
| 查詢空位中 | 不 F5、不重選、不關頁 |
| 流量管制／系統忙碌文案 | 等待 `refresh_interval` 後再試下一步；已鎖票則仍不重整 |
| 優先種暫無票券、未勾備選 | 尚未鎖票則整頁 F5，重選優先種 |
| 優先種暫無票券、有勾備選 | 改買第一個非愛心可購種，不重整 |
| 只有愛心票可購 | 視為沒有可購種，整頁 F5 |
| 全部非愛心都暫無票券 | 整頁 F5 等待釋票 |
| 購票失敗彈窗 | 關掉後若尚未鎖票，可重選；已鎖票則只往前 |
| CSRF／官方要求重整 | 僅在尚未鎖票時跟隨官方重整 |
| 瀏覽器被關 | 與遠大相同：結束並提示重新啟動瀏覽器 |
| 多視窗 | KKTIX 不啟動 extra engines |

## 測試

遠大既有 `tests/` 必須維持通過。

新增：

| 測試 | 內容 |
|------|------|
| `test_helpers.py` | `detect_platform`、slug 解析、KKTIX 購票／登入／付款 URL |
| `test_config_file.py` | example 裡的 KKTIX 範例網址能通過 `TicketConfig.validate()` |
| `test_kktix_api.py` | register_info 解析；離線 skip |
| `test_kktix_mock_site.py` | 模擬站靜態路由與關鍵 DOM |
| `test_kktix_mock_bot.py` | 對模擬站跑完：未開賣 → 整點後可購 → 選票 → 電腦配位 → 查詢空位 → 填表下一步 → 付款頁停止。另測：優先種暫無票券且無備選會重整；愛心票不會被選。無 Chrome 則 skip |

KKTIX 模擬站掛在現有 `mock/server.py` 的另一組路由，不取代遠大模擬：

- `http://127.0.0.1:8765/events/mock-kktix/registrations/new`
- DOM 對齊官方：`#registrationsNewApp`、票種列、`#person_agree_terms`、「電腦配位」／「下一步」、「查詢空位中」、付款頁路徑 `/pay`
- 場景：`presale`（倒數後開賣）、`happy`、`priority-unavailable`（優先種暫無票券）、`queue`、`need-login`、`charity-only`（其餘售完只剩愛心票，必須跳過並重整）

不把第三方練習器當 CI 依賴。練習器只供開發時手動對照節奏。

## 檔案變更（預期）

- 新增：`src/pages/kktix/`、`src/core/kktix_flow.py`、`src/api/kktix_api.py`
- 新增：`mock/` 底下 KKTIX 靜態頁
- 修改：`helpers.py`、`ticket_config.py`、`bot_engine.py`、`main.py`、`gui/main_window.py`、`config.example.yaml`、`README.md`
- 遠大 `pages/activity_page.py`、`order_page.py` 不為了 KKTIX 改行為

## 成功標準

1. 貼上 `https://kktix.com/events/sbgr01/registrations/new`，GUI 以 KKTIX 模式運作，遠大活動仍走舊流程。
2. 模擬站 `presale`：開賣前等待，開賣時刻 F5 一次，之後選票並進付款頁停止。
3. 開賣後優先種「暫無票券」且未勾備選：會整頁重整；有勾備選則改買第一個非愛心可購種且不因備選而重整。
4. 愛心／身障票種不會被選中（含清單空白、價格誤撞、備選第一個可購）。
5. 查詢空位期間沒有 `driver.refresh()`。
6. 有「自行選位」與「電腦配位」時只按電腦配位。
7. `python -m pytest tests -q` 含遠大舊測試全過。
8. 不呼叫任何建立訂單的隱藏 API；`register_info` 僅用於 inspect。
