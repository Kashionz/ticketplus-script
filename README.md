# TicketPlus 購票助手

用官方網站畫面操作的 TicketPlus（遠大）購票輔助程式。架構對齊既有的拓元專案：Python + Selenium + PyQt6。

**預設用已開賣的測試活動開發**（目前是音田雅則）。正式搶 INFINITE 前，把活動網址、場次與 VIP 區改成目標場次。

## 能做什麼

- 讀取公開活動資料（場次、票區、票價）
- 開啟 Chrome，由你手動登入（登入狀態可保存在 `.chrome-profile`）
- 進入官方購票頁後，依票區欄位判斷是否開賣（顯示開賣時間則等待；可選數量或已售完則開始選票）
- 支援遠傳 / friDay **購票序號**
- 自動勾選同意條款並按「下一步」
- 遇到官方排隊或 reCAPTCHA / 3D 驗證時停下，等你在瀏覽器完成
- 進入確認或付款頁後停止自動化，由你完成付款

## 不會做的事

- 不繞過排隊、reCAPTCHA 或流量控管
- 不直接打隱藏訂票 API、不破解簽名
- 不一次開多帳號、不自動解驗證碼
- 不代你完成付款

請遵守 [TicketPlus 使用條款](https://ticketplus.com.tw) 與活動注意事項。票券僅供自用，加價轉售可能涉及《社會秩序維護法》。使用本工具的後果由使用者自行承擔。

## 活動對照

| 用途 | 活動 | 網址 |
|------|------|------|
| 開發測試（已開賣） | 音田雅則 One Man Tour 2026 “Hiraeth” in Taipei | `https://ticketplus.com.tw/activity/4b47b5360d42451f65704664c40b1c72` |
| 正式目標 | 2026 INFINITE FANMEETING [INFINITE RALLY V] in TAIPEI | `https://ticketplus.com.tw/activity/af39103d211724c82069c4ab5e40e95c` |

INFINITE 重點：

- 目標票區：**VIP3區、VIP4區**（NT$6,100）
- 場次：9/19 18:00、9/20 16:00（林口 / 國立體育大學綜合體育館）
- 遠傳優先購：9/19 為 2026/08/14 11:00；9/20 為 13:00。每組序號限 2 張、限 VIP、電腦配位
- 一般販售：9/19 為 2026/08/15 13:00；9/20 為 2026/08/16 13:00。每場次每會員限 4 張

## 環境

- Python 3.10+
- 已安裝 Google Chrome
- 建議在 Windows 執行（與現有拓元專案相同）。WSL 需另外處理 Chrome

```bash
cd ticketplus-script
python -m venv .venv
.venv\Scripts\activate          # Linux / macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## 使用

先查公開資料，不必開瀏覽器：

```bash
python -m src.main inspect
python -m src.main inspect --url https://ticketplus.com.tw/activity/af39103d211724c82069c4ab5e40e95c
```

## 用 Windows Chrome（不要用 Linux 內建瀏覽器）

在 WSL 裡跑 Selenium 會開到 `/usr/bin/google-chrome`（Linux 無頭 / 內建），**不是**你桌面上看得到的 Chrome。這次誤判付款頁，就是在那種環境測到的。

最穩：在 Windows 雙擊 `run-windows.bat`。它會用 Windows 的 Python 開你看得到的 Chrome。

若要讓我從 WSL 遠端點你桌面的 Chrome：

1. 關掉所有 Chrome
2. 雙擊 `open-chrome.bat`（會開獨立設定檔，監聽 `127.0.0.1:9222`）
3. 在那個視窗登入 TicketPlus
4. 跟我說「Chrome 已開好，請 attach 9222」

若 WSL 連不到 9222，在 PowerShell 執行後重開 WSL：

```powershell
# 需要 Windows 管理員
# 讓 WSL 與 Windows 共用 localhost
```

或直接用 `run-windows.bat`，不要走 WSL。

圖形介面（建議）：

```bash
python -m src.main
```

1. 開發時按「載入測試活動」，走完整流程
2. 正式場按「載入 INFINITE」，確認場次是 `9/19` 或 `9/20`，票區為 `VIP3區`、`VIP4區`
3. 遠傳優先購把序號貼進「購票序號」
4. 「啟動瀏覽器」後在 Chrome 登入並完成手機 / Email 驗證
5. 登入完成後按「開始搶票」
6. 進到 `/checkout` 付款頁後，在瀏覽器完成取票方式與付款。`/confirm` 還不是付款頁，程式會繼續按下一步。

命令列：

```bash
python -m src.main --cli
python -m src.main --cli --url https://ticketplus.com.tw/activity/af39103d211724c82069c4ab5e40e95c --session 9/19 --quantity 2
```

## 本機模擬站

不必連正式遠大網站，也能把搶票流程跑完，用來驗證開賣判斷、更新票數、票區優先級與售完後備。

```bash
python -m mock.server
# 或
python -m src.main mock
```

瀏覽器打開 `http://127.0.0.1:8765/activity/a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1`，或在 GUI 按「載入模擬站」。頁面上方可切場景：

| 場景 | 用途 |
|------|------|
| `happy` | 已開賣，VIP3 熱賣中、部分票區剩餘 0 / 已售完 |
| `presale` | 未開賣（顯示開賣時間），點「更新票數」到達次數後開賣 |
| `priority-soldout` | VIP3/VIP4 售完，搖滾A 仍可買（測後備） |
| `stock-later` | VIP3 先剩餘 0，更新後才有票 |
| `need-login` | 需先登入 |
| `need-serial` | 要填購票序號才可下一步 |
| `queue` | 先出現排隊畫面 |
| `fail-once` | 第一次下一步跳出購票失敗 |
| `overlay` | 電腦配位轉圈較久 |

查詢參數例：`?scenario=presale&saleAfter=2`

## 設定檔

複製 `config/config.example.yaml` 為 `config/config.yaml`。重點欄位：

| 欄位 | 說明 |
|------|------|
| `ticket.activity_url` | 活動頁完整網址 |
| `ticket.target_session` | 場次關鍵字，例如 `9/19` |
| `ticket.quantity` | 張數（優先購 2、一般販售最多 4） |
| `ticket.area_priorities` | 票區 / 票種優先順序 |
| `ticket.exclusive_code` | 購票序號 |
| `bot.refresh_interval` | 刷新間隔毫秒，最低 200 |

登入狀態存在 `.chrome-profile`。要重登就刪掉這個資料夾。

## 購票流程（官方頁面）

1. 活動頁選擇場次，按立即購買
2. 進入 `/order/{eventId}/{sessionId}`
3. 選擇票區（電腦配位，不必自己點座位）
4. 需要時輸入購票序號
5. 同意條款 → 下一步
6. 選擇取票 / 付款方式，完成 3D 驗證

遠大提醒：不要同時開多個視窗或裝置購票。

## 測試

```bash
python -m pytest tests -q
```
