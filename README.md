# TicketPlus 購票助手

用官方網站畫面操作的 TicketPlus（遠大）購票輔助程式。Python + Selenium 操作你看得到的 Chrome，PyQt6 提供圖形介面。程式只點官方頁面上的按鈕與輸入框，不打隱藏訂票 API、不繞過排隊或驗證碼。

進入 `/checkout` 付款頁後自動化停止，由你在瀏覽器完成取票方式、付款與 3D 驗證。

請遵守 [TicketPlus 使用條款](https://ticketplus.com.tw) 與活動注意事項。票券僅供自用；加價轉售可能涉及《社會秩序維護法》。使用本工具的後果由使用者自行承擔。

---

## 目錄

- [能做 / 不做](#能做--不做)
- [技術架構](#技術架構)
- [搶票狀態機](#搶票狀態機)
- [關鍵判斷邏輯](#關鍵判斷邏輯)
- [環境安裝](#環境安裝)
- [圖形介面使用](#圖形介面使用)
- [命令列使用](#命令列使用)
- [Windows / WSL / 接上已開的 Chrome](#windows--wsl--接上已開的-chrome)
- [設定檔](#設定檔)
- [本機模擬站](#本機模擬站)
- [測試](#測試)
- [活動對照](#活動對照)
- [常見問題](#常見問題)

---

## 能做 / 不做

**會做**

- 讀取公開活動資料（場次、票區、票價）
- 開啟或接上 Chrome，由你登入（狀態可存在 `.chrome-profile`）
- 被登出時，若有填帳密則自動重登
- 依購票頁票區欄位判斷是否開賣
- 依票區優先級選區、加減張數
- 剩餘不足時可改買剩餘，或堅持指定張數繼續刷
- 頁面出現「遠傳優先購序號」欄才填序號
- 自動勾選同意條款並按「下一步」
- 遇到官方排隊或 reCAPTCHA / 3D 驗證時停下等你
- 鎖票後只往前走，不再重選或重整
- 可選 2–3 個獨立視窗同時搶（同一登入；一個進付款就關掉其他視窗）

**不會做**

- 不繞過排隊、reCAPTCHA、流量控管
- 不直接打隱藏訂票 API、不破解簽名
- 不一次開多帳號、不自動解驗證碼
- 不代你完成付款
- `/confirm`、`/confirmSeat` 還不是付款頁，程式會繼續按下一步

遠大提醒：不要同時用多個裝置或同一帳號大量開窗購票。`同時視窗` 預設為 1。

---

## 技術架構

### 總覽

```
┌─────────────────────────────────────────────────────────────┐
│  進入點  python -m src.main                                 │
│  GUI（預設） / --cli / inspect / open-chrome / mock         │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────┐   ┌─────────────────────────────┐
│  PyQt6 GUI                │   │  公開 API（僅查詢）          │
│  main_window / 狀態 / 日誌 │   │  apis.ticketplus.com.tw     │
│  設定 ↔ config.yaml       │   │  getS3 活動 / 場次 / 票區    │
└─────────────┬─────────────┘   └─────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────┐
│  BotEngine（背景執行緒）                                      │
│  依目前網址分流：活動頁 → 購票頁 → 確認座位 → 確認資料 → 付款  │
└─────────────┬───────────────────────────────────────────────┘
              │ Selenium
              ▼
┌─────────────────────────────────────────────────────────────┐
│  BrowserManager → Chrome                                    │
│  新開 profile 或 attach 127.0.0.1:9222                      │
│  Page Object：ActivityPage / OrderPage / LoginPage          │
└─────────────────────────────────────────────────────────────┘
              │
              ▼
     TicketPlus 官方站 或  本機 mock.server
```

核心原則：**只操作畫面，用網址判斷階段**。付款與否只看 URL（`/checkout`、`/done` 或銀行 3D 網域），不用頁面內文，因為注意事項常出現「付款方式」「訂單成立」。

### 目錄

```
ticketplus-script/
├── src/
│   ├── main.py                 # CLI / GUI 進入點
│   ├── api/event_api.py        # 公開 getS3，只讀場次與票區
│   ├── core/
│   │   ├── bot_engine.py       # 搶票狀態機、多視窗協調
│   │   └── browser.py          # Chrome 啟動 / attach / cookie
│   ├── pages/
│   │   ├── base_page.py        # 共用 JS 執行、導頁、等待
│   │   ├── activity_page.py    # 活動頁選場次、立即購買
│   │   ├── order_page.py       # 開賣判斷、選區、張數、序號、下一步
│   │   └── login_page.py       # 登入表單
│   ├── gui/                    # PyQt6 主視窗、狀態列、日誌
│   ├── models/ticket_config.py # 購票設定資料模型
│   └── utils/                  # 設定、網址分類、剩餘張數、Windows Chrome
├── mock/                       # 本機模擬站（驗證流程，不連遠大）
├── config/config.example.yaml
├── tests/
├── run-windows.bat             # 用 Windows Python 開 GUI
└── open-chrome.bat             # 開可 attach 的 Chrome（9222）
```

### 各層職責

| 模組 | 職責 |
|------|------|
| `src/main.py` | 解析參數。無子命令開 GUI；`--cli` 走命令列；`inspect` / `open-chrome` / `mock` 為工具指令 |
| `BotEngine` | 背景執行緒。先等你按「開始搶票」，再依 URL 循環處理。狀態用 `BotStatus` / `BotStep` 回報 GUI |
| `BrowserManager` | 啟動 Chrome、attach 除錯埠、複製 cookie 給平行視窗。WSL 時優先開 Windows Chrome |
| `ActivityPage` | 活動頁場次列表、點「立即購買」、關掉公告彈窗、尚未開賣時刷新 |
| `OrderPage` | 購票頁主戰場：開賣偵測、票區優先級、剩餘張數、優先購序號、條款、鎖票後只按下一步 |
| `LoginPage` | 偵測登入表單；有帳密則填入；有驗證碼則停住等你 |
| `event_api` | `inspect` 與 GUI「查看活動資料」用。**搶票過程不靠這支 API 下單** |
| `TicketConfig` | 網址、場次、張數、票區、序號、帳密、剩餘張數策略 |
| `mock/` | 仿官方 Vue / Vuetify 畫面，用 `?scenario=` 模擬未開賣、售完、序號、排隊 |

### 與官方頁面對應

官方購票是多頁 Vue 流程。程式用 path 第一段分流：

| 網址 | 階段 | 程式行為 |
|------|------|----------|
| `/activity/{eventId}` | 選場次 | 點符合關鍵字的「立即購買」 |
| `/login` | 登入 | 自動填帳密，或等你登入 |
| `/order/{eventId}/{sessionId}` | 選票區 | 判斷開賣、選區、張數、序號、下一步 |
| `/confirmSeat/...` | 電腦配位 | 有鎖票就只按下一步，不重選、不重整 |
| `/confirm/...` | 確認資料 | 勾條款、選取票 / 付款方式、下一步 |
| `/checkout/...` 或銀行 3D | 付款 | **成功結束**，交給你 |

選完票後官方會電腦配位（`/confirmSeat`），不必自己點座位圖。

### GUI 與引擎的執行緒

```
主執行緒（Qt）                    背景執行緒（BotWorker / BotEngine）
啟動瀏覽器  ──────────────────►  開 Chrome，停在 WAITING_LOGIN
開始搶票    ──────────────────►  trigger_start_booking()
狀態 / 日誌  ◄──────────────────  callback（跨執行緒 signal）
停止        ──────────────────►  設 stop flag，瀏覽器可保持開啟
```

瀏覽器關掉時引擎會結束並回到可重開狀態，不必重啟整個 GUI。

---

## 搶票狀態機

`BotEngine._execute()` 在 `max_retries` 內反覆看目前 URL：

```
啟動瀏覽器
    │
    ▼
等待登入 ──►（按「開始搶票」）
    │
    ▼
開啟活動頁 ──► 選場次「立即購買」
    │              │ 尚未開賣 / 找不到按鈕
    │              └── 刷新活動頁，再試
    ▼
購票頁 /order
    │
    ├─ 未開賣（票區顯示開賣時間）──► 點「更新票數」，等待
    ├─ 排隊畫面 ──► 停住等官方放行
    ├─ reCAPTCHA ──► 停住等你在瀏覽器完成
    ├─ 已有鎖票 ──► 只按下一步
    └─ 已開賣 ──► 選區 / 張數 ──► 有序號欄才填 ──► 勾條款 ──► 下一步
                      │
                      └─ 沒選到（沒票 / 張數不夠）──► 再點「更新票數」
    ▼
confirmSeat / confirm
    │  不重選、不清空、不重整
    ▼
checkout / 3D  ──► SUCCESS，請你付款
```

鎖票後若再重整或重選，官方常會丟掉座位。所以 `has_hold()` 之後只走 `_advance_after_hold()`。

---

## 關鍵判斷邏輯

### 1. 開賣與否

看購票頁票區欄位，不看活動頁倒數、不看公開 API 時間。

| 畫面 | 判定 |
|------|------|
| 顯示「開賣時間」/「尚未開賣」 | 未開賣 → 持續點「更新票數」 |
| 有 `+/-` 張數、或「剩餘 N」/「熱賣中」/「已售完」 | 已開賣 → 開始選區 |

「已售完」也算已開賣：代表這場開始賣了，只是這區沒票。

### 2. 票區優先級

- 清單由上到下嘗試（例如 VIP3區 → VIP4區）
- 名稱比對會忽略空白，`VIP3` 與 `VIP3區` 視為相同
- **不勾**「優先票區沒票時改買第一個可購」：優先區沒票就繼續刷
- **勾了**：優先區都沒票才改選畫面上第一個還能買的區
- 清單留空：直接買畫面上第一個可購

### 3. 剩餘張數

官方票區標題：

```html
<small class="ml-1">剩餘 1</small>
```

加號到上限時會帶 `data-limit="true"`。

指定 2 張、只剩 1 張時：

| 選項 | 行為 |
|------|------|
| **不勾**「一定要買到指定張數」（預設） | 改買 1 張 |
| **勾選** | 這區不買，繼續刷到夠張或換下一優先區 |

「熱賣中」沒寫剩餘時，先點指定張數；加號提前鎖住則依上面同一規則處理。

### 4. 優先購序號

**不是**看設定裡有沒有字，而是看頁面有沒有官方區塊：

```html
<div class="exclusive-code">
  <div class="label">遠傳優先購序號</div>
  <input placeholder="請輸入遠傳優先購序號">
</div>
```

| 頁面 | 設定序號 | 行為 |
|------|----------|------|
| 有 `.exclusive-code` | 有填 | 填進這個 input |
| 有 `.exclusive-code` | 空白 | 停住，提示未填序號 |
| 沒有這個欄 | 有或沒有 | 不填，避免填錯別的框 |

一般販售沒有這個欄，程式不會亂填。

### 5. 付款頁判定

只看 URL：

- 付款：`/checkout`、`/done`、`/ordered`、`/payment`，或主機名含銀行 / 3D（`3dsecure`、`acs.`、`visa.com` 等）
- 還要繼續：`/confirm`、`/confirmSeat`

---

## 環境安裝

- Python 3.10+
- 已安裝 Google Chrome
- 建議在 **Windows** 執行。WSL 請用 `run-windows.bat` 或 attach Windows Chrome，不要用 Linux 內建瀏覽器

```bash
cd ticketplus-script
python -m venv .venv
.venv\Scripts\activate          # Linux / macOS: source .venv/bin/activate
pip install -r requirements.txt
copy config\config.example.yaml config\config.yaml
```

第一次沒有 `config.yaml` 時，程式也會從 example 複製一份。

依賴：`selenium`、`PyQt6`、`PyYAML`、`requests`、`pytest`。ChromeDriver 由 Selenium Manager 自動處理，通常不必手動放 driver。

---

## 圖形介面使用

建議路徑。Windows 可直接雙擊 `run-windows.bat`，或：

```bash
python -m src.main
```

### 介面區塊

**左側：活動**

| 項目 | 說明 |
|------|------|
| 網址 | 活動頁完整網址，需含 `ticketplus.com.tw/activity/{eventId}`，或本機模擬站 |
| 載入測試活動 | 音田雅則（已開賣、全區），用來走完整流程 |
| 載入 INFINITE | 正式目標：9/19、VIP3 / VIP4 |
| 載入模擬站 | `http://127.0.0.1:8765/activity/...`（需另開模擬站） |
| 場次 | 關鍵字，例如 `9/19`。空白 = 第一個可點立即購的場次 |
| 張數 | 1–4。優先購通常 2 張，一般販售上限 4 |
| 一定要買到指定張數 | 見[剩餘張數](#3-剩餘張數) |
| 購票序號 | 遠傳 / friDay 優先購。沒有就留空 |

**左側：帳號**

被登出才自動重登。已登入可留空。手機建議 `09xxxxxxxx`。

**左側：票區優先級**

上到下嘗試。可新增、移除、拖曳或上移下移。留空 = 第一個可購。

**左側：執行**

| 項目 | 說明 |
|------|------|
| 刷新間隔 ms | 未開賣 / 沒票時點「更新票數」的間隔，最低 200。過低容易被流量控管 |
| 自動勾選同意條款 | 預設開啟 |
| 隱藏瀏覽器視窗 | 搶票不建議勾，驗證碼需要你看到畫面 |
| 同時視窗 | 1–3。開始搶票時複製登入再開獨立 Chrome |

**右側**：狀態（步驟、重試次數、訊息）與即時日誌。

**底部按鈕**

1. **查看活動資料** — 打公開 API，列出場次與票區（不開瀏覽器）
2. **啟動瀏覽器** — 開 Chrome，停在「請先登入」
3. **開始搶票** — 登入完成後才按
4. **停止** — 停下流程；瀏覽器預設保持開啟，可改設定再搶
5. **儲存設定** — 寫入 `config/config.yaml`

### 正式搶票步驟

1. 填活動網址、場次、張數、票區。優先購把序號貼進「購票序號」。
2. 按 **儲存設定**。
3. 按 **啟動瀏覽器**。在 Chrome 登入 TicketPlus，完成手機 / Email 驗證。
4. 確認畫面已是登入狀態（右上角有帳號）。
5. 開賣前約 1 分鐘按 **開始搶票**。
6. 未開賣時程式會待在購票頁點「更新票數」，不必手動重整。
7. 出現排隊或驗證碼時看 Chrome，完成後程式會自己繼續。
8. 進入付款頁後，**在瀏覽器**選取票 / 付款並完成 3D。不要關那個視窗。

開發時按「載入測試活動」可先走完整流程（該活動通常已開賣）。

---

## 命令列使用

```bash
# 圖形介面（預設）
python -m src.main

# 查公開活動資料
python -m src.main inspect
python -m src.main inspect --url https://ticketplus.com.tw/activity/af39103d211724c82069c4ab5e40e95c

# 開可 attach 的 Windows Chrome
python -m src.main open-chrome

# 本機模擬站
python -m src.main mock --port 8765
python -m mock.server

# 命令列搶票（先讀 config.yaml，參數可覆寫）
python -m src.main --cli
python -m src.main --cli --url https://ticketplus.com.tw/activity/af39103d211724c82069c4ab5e40e95c --session 9/19 --quantity 2
python -m src.main --cli --exact-quantity --code 你的序號
python -m src.main --cli --attach 127.0.0.1:9222
```

| 參數 | 說明 |
|------|------|
| `--cli` | 不開 GUI |
| `--url` | 活動網址 |
| `--session` | 場次關鍵字 |
| `--quantity` | 張數 |
| `--exact-quantity` | 一定要買到指定張數 |
| `--code` | 購票序號 |
| `--headless` | 隱藏視窗（搶票不建議） |
| `--attach` | 接上已開的 Chrome，例如 `127.0.0.1:9222` |
| `--config` | 設定檔路徑，預設 `config/config.yaml` |
| `--debug` | DEBUG 日誌 |
| `--port` | 僅 `mock` 子命令，模擬站埠號 |

CLI 流程：印出設定 → Enter 啟動瀏覽器 → 你登入 → 再按一次 Enter 開始搶票。`Ctrl+C` 停止。

---

## Windows / WSL / 接上已開的 Chrome

在 WSL 裡跑 Selenium 常會開到 `/usr/bin/google-chrome`，不是你桌面上的 Chrome。付款頁誤判、看不到視窗，多半是這個原因。

**最穩：在 Windows 雙擊 `run-windows.bat`。** 它會建立 `.venv-win`，用 Windows Python 開看得到的 Chrome。

若要從 WSL 遠端操作桌面 Chrome：

1. 關掉其他 Chrome（除錯埠才綁得上）
2. 雙擊 `open-chrome.bat`（獨立 profile、監聽 `127.0.0.1:9222`）
3. 在那個視窗登入 TicketPlus
4. `python -m src.main --cli --attach 127.0.0.1:9222`  
   或把 `config.yaml` 的 `browser.debugger_address` 設成 `127.0.0.1:9222`

`browser.prefer_windows_chrome: true`（預設）時，在 WSL 會設法改開 Windows Chrome，而不是 Linux 內建瀏覽器。

登入狀態存在 `.chrome-profile`。要重登就關掉 Chrome 後刪掉這個資料夾。

---

## 設定檔

複製 `config/config.example.yaml` 為 `config/config.yaml`。GUI「儲存設定」也會寫這份檔。

### `ticket`

| 欄位 | 說明 |
|------|------|
| `activity_url` | 活動頁完整網址 |
| `target_session` | 場次關鍵字，例如 `9/19`。空白 = 第一個可購 |
| `quantity` | 張數 1–4 |
| `area_priorities` | 票區名稱清單，上到下 |
| `session_exclude_keywords` | 要跳過的場次關鍵字 |
| `exclusive_code` | 遠傳 / friDay 優先購序號 |
| `fallback_first_available` | `true` = 優先區沒票改買第一個可購 |
| `require_exact_quantity` | `true` = 一定要指定張數；`false` = 剩餘不足改買剩餘 |

### `account`

| 欄位 | 說明 |
|------|------|
| `mobile` | 手機，例如 `0912345678` |
| `password` | 密碼。已登入可留空 |
| `country_code` | 預設 `+886` |

### `browser`

| 欄位 | 說明 |
|------|------|
| `headless` | 無頭模式 |
| `page_load_timeout` | 頁面載入秒數 |
| `element_timeout` | 元件等待秒數 |
| `window_width` / `window_height` | 視窗大小 |
| `user_data_dir` | Chrome profile，預設 `.chrome-profile` |
| `debugger_address` | 例如 `127.0.0.1:9222`，接上已開的 Chrome |
| `chrome_binary` | 指定 `chrome.exe` 路徑 |
| `prefer_windows_chrome` | WSL 時改開 Windows Chrome |
| `driver_path` | 自訂 chromedriver，通常留空 |

### `bot`

| 欄位 | 說明 |
|------|------|
| `refresh_interval` | 刷新間隔毫秒，最低 200 |
| `max_retries` | 主迴圈次數上限，預設 300 |
| `auto_agree` | 自動勾條款 |
| `wait_for_human` | 遇到 reCAPTCHA 暫停等你 |
| `parallel_windows` | 同時視窗 1–3 |
| `sound_notification` | 進付款頁時嗶一聲 |

日誌預設寫到 `logs/bot.log`。

---

## 本機模擬站

不必連正式遠大，也能把開賣判斷、更新票數、票區優先、剩餘張數、序號、排隊跑完。

```bash
python -m mock.server
# 或
python -m src.main mock
```

瀏覽器開：

`http://127.0.0.1:8765/activity/a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1`

或在 GUI 按「載入模擬站」。頁面上方可切場景。

| 場景 | 用途 |
|------|------|
| `happy` | 已開賣；VIP3 熱賣中，部分區剩餘 0 / 已售完 |
| `presale` | 未開賣（顯示開賣時間），點「更新票數」到達次數後開賣 |
| `priority-soldout` | VIP3 / VIP4 售完，搖滾 A 仍可買（測後備） |
| `stock-later` | VIP3 先剩餘 0，更新後才有票 |
| `low-stock` | VIP3 / VIP4 只剩 1 張（測改買剩餘 / 堅持指定張數） |
| `need-login` | 需先登入 |
| `need-serial` | 出現官方 `.exclusive-code`，要填序號才可下一步 |
| `queue` | 先出現排隊畫面 |
| `fail-once` | 第一次下一步跳出購票失敗 |
| `overlay` | 電腦配位轉圈較久 |

查詢參數例：`?scenario=presale&saleAfter=2`

模擬站的 `/checkout` 不是真的付款，只用來驗證「進付款頁就停」。

---

## 測試

```bash
python -m pytest tests -q
```

| 檔案 | 內容 |
|------|------|
| `test_helpers.py` | 網址分類、開賣文案、剩餘張數計算 |
| `test_bot_engine.py` | 瀏覽器關閉復原、登入暫停、序號欄、張數旗標 |
| `test_config_file.py` | example / 本機設定能否載入 |
| `test_event_api.py` | 打真實 getS3（離線會 skip） |
| `test_mock_site.py` | 模擬站靜態資源 |
| `test_mock_bot.py` | 對模擬站跑完整流程，需要本機 Chrome；沒有 Chrome 會 skip |

---

## 活動對照

| 用途 | 活動 | 網址 |
|------|------|------|
| 開發測試（已開賣） | 音田雅則 One Man Tour 2026 “Hiraeth” in Taipei | `https://ticketplus.com.tw/activity/4b47b5360d42451f65704664c40b1c72` |
| 正式目標 | 2026 INFINITE FANMEETING [INFINITE RALLY V] in TAIPEI | `https://ticketplus.com.tw/activity/af39103d211724c82069c4ab5e40e95c` |

INFINITE：

- 票區：**VIP3區、VIP4區**（NT$6,100）
- 場次：9/19 18:00、9/20 16:00（林口 / 國立體育大學綜合體育館）
- 遠傳優先購：9/19 為 2026/08/14 11:00；9/20 為 13:00。每組序號限 2 張、限 VIP、電腦配位
- 一般販售：9/19 為 2026/08/15 13:00；9/20 為 2026/08/16 13:00。每場次每會員限 4 張

正式場前請用 GUI「載入 INFINITE」核對場次是 `9/19` 或 `9/20`，票區為 VIP3 / VIP4。

---

## 常見問題

**按了開始搶票沒反應**  
先「啟動瀏覽器」並完成登入，右側狀態應是等待登入。瀏覽器被關掉要重新啟動。

**一直停在尚未開賣**  
購票頁票區若仍顯示開賣時間，程式會點「更新票數」。確認已進 `/order` 而不是停在活動頁。刷新間隔不要設太低。

**選不到票區**  
名稱要跟畫面上一致（可用「查看活動資料」對照）。預設不會在優先區沒票時改買別區。剩餘不足且勾了「一定要指定張數」也會略過該區。

**有填序號卻沒填上去**  
一般販售沒有 `.exclusive-code` 欄，程式刻意不填。優先購頁面應看得到「遠傳優先購序號」。

**出現驗證碼或排隊**  
這是正常暫停。在 **Chrome** 完成，不要關頁。程式偵測到畫面消失會繼續。

**進了確認頁還在按下一步**  
`/confirm`、`/confirmSeat` 還不是付款頁。到 `/checkout` 或銀行 3D 才會停。

**WSL 開出來的 Chrome 不對勁**  
改用 `run-windows.bat`，或 `open-chrome.bat` + `--attach 127.0.0.1:9222`。

**要換帳號**  
停止程式、關掉 Chrome，刪除 `.chrome-profile` 後重開。

**多視窗被擋**  
遠大可能限制同一帳號多開。把「同時視窗」設回 1。
