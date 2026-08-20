# 購票助手

用官方網站畫面操作的購票輔助程式（ticket-helper）。Python + Selenium 操作你看得到的 Chrome，PyQt6 提供圖形介面。只點頁面上的按鈕與輸入框，不打隱藏訂票 API、不繞過排隊或驗證碼。

**支援：** TicketPlus（遠大）與 KKTIX（電腦配位）。依網址自動判斷。KKTIX 不支援自行選位。

進入付款頁後自動化停止，由你在瀏覽器完成付款與 3D。請遵守 [TicketPlus](https://ticketplus.com.tw)、[KKTIX](https://kktix.com) 使用條款與活動注意事項。票券僅供自用。

## 能做 / 不做

**會做：** 開或接上 Chrome、依票區／票種優先級選張數、剩餘不足可改買剩餘、畫面有優先購／邀請碼欄才填、勾條款並按下一步、排隊或驗證碼時停住等你、鎖票後只往前不重選。TicketPlus 可選 1–3 個視窗；KKTIX 固定 1。

**不會做：** 不繞過排隊／驗證碼、不下隱藏 API、不代填 KKTIX 報名人資料、不完成付款。

## 安裝

需要 Python 3.10+ 與 Google Chrome。建議在 Windows 執行；WSL 請用 `run-windows.bat` 或接上 Windows Chrome。

```bash
cd ticket-helper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config\config.example.yaml config\config.yaml
```

沒有 `config.yaml` 時，第一次啟動會從 example 複製一份。ChromeDriver 由 Selenium 自動處理。

## 使用

Windows 雙擊 `run-windows.bat`，或：

```bash
python -m src.main
```

1. 貼上活動網址（TicketPlus 活動頁，或 KKTIX `/events/{slug}/registrations/new`）
2. 填場次（僅 TicketPlus）、張數、票區／票種優先級
3. **儲存設定** → **啟動瀏覽器** → 在 Chrome 登入
4. 開賣前約一分鐘按 **開始搶票**
5. 進付款頁後，在瀏覽器完成付款，不要關那個視窗

**查看活動資料** 只讀公開資料，不開瀏覽器。**停止** 會停下流程，瀏覽器預設保持開啟。

KKTIX 請事先到 [報名預填資料](https://kktix.com/account/prefills) 填好會員資料；程式鎖票後不代填身分證等欄位。

### 欄位

| 項目 | 說明 |
|------|------|
| 網址 | 依網址切 TicketPlus / KKTIX / 本機模擬站 |
| 場次 | TicketPlus 關鍵字；空白＝第一個可購場次。KKTIX 不使用 |
| 張數 | 1–4 |
| 一定要買到指定張數 | 勾了：剩餘不夠就不買這區。沒勾：改買剩餘 |
| 購票序號 | 僅畫面出現優先購／邀請碼欄才填 |
| 票區優先級 | 上到下嘗試。留空＝第一個可購（KKTIX 會跳過愛心／身障） |
| 優先票區沒票時改買第一個可購 | 沒勾就繼續刷優先區；勾了才改買別區 |
| 刷新間隔 | 未開賣／沒票時的間隔，最低 200 ms |
| 同時視窗 | TicketPlus 1–3。KKTIX 鎖 1 |
| 帳號 | 被登出才自動重登。TicketPlus 填手機，KKTIX 填 Email |

## 行為

- **開賣：** 看購票頁票區／票種，不看活動頁倒數。顯示開賣時間＝未開賣；有加減鈕、剩餘、熱賣中或已售完＝已開賣。
- **TicketPlus：** 未開賣會點「更新票數」。鎖票後（`/confirmSeat`、`/confirm`）只按下一步；到 `/checkout` 或 3D 才停。
- **KKTIX：** 開賣時刻整點 F5 一次。有「電腦配位」就按它，否則按「下一步」，不按「自行選位」。愛心／身障票一律不買。「查詢空位中」不重整。
- **取消購票：** 若跳出「重新選票」確認，程式會等你選：確定＝取消訂單；取消＝保留座位。

## Chrome

登入狀態存在 `.chrome-profile`。要換帳號：停止程式、關掉 Chrome，刪掉這個資料夾。

若要接上已開的 Chrome：先關其他 Chrome，雙擊 `open-chrome.bat`，再把 `debugger_address` 設成 `127.0.0.1:9222`，或：

```bash
python -m src.main --cli --attach 127.0.0.1:9222
```

## 設定檔

`config/config.yaml`。GUI「儲存設定」會寫入。欄位說明見 `config/config.example.yaml`。

## 模擬站與測試

```bash
python -m src.main mock
python -m pytest tests -q
```

模擬站同時提供遠大與 KKTIX 假頁面，用來走流程，不是真的付款。

## 常見問題

**開始搶票沒反應** — 先啟動瀏覽器並登入。瀏覽器被關掉要重新啟動。

**選不到票區** — 名稱或價格要跟畫面上一致。可用「查看活動資料」對照。

**有填序號卻沒填** — 一般販售沒有序號欄，程式不會亂填。

**驗證碼或排隊** — 在 Chrome 完成，不要關頁。

**KKTIX 下一步按不了** — 到 [報名預填資料](https://kktix.com/account/prefills) 補齊，或在當頁手動填。

**KKTIX 查看活動資料沒有票種表** — `kktix.com` 可能被 Cloudflare 擋住，改貼主辦單位 `*.kktix.cc` 網址。
