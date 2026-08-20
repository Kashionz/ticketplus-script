"""搶票流程引擎。"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, List, Optional

from ..models.ticket_config import TicketConfig
from ..pages.activity_page import ActivityPage
from ..pages.login_page import LoginPage
from ..pages.order_page import OrderPage
from ..utils.helpers import (
    clamp_parallel_windows,
    detect_platform,
    is_activity_url,
    is_confirm_url,
    is_login_url,
    is_connection_refused,
    is_mock_url,
    is_order_url,
    is_payment_url,
    navigation_refused_hint,
)
from .browser import BrowserManager

logger = logging.getLogger("ticketplus")

StatusCallback = Callable[["BotState"], None]
LogCallback = Callable[[str, str], None]


class BotStatus(Enum):
    IDLE = auto()
    STARTING = auto()
    WAITING_LOGIN = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    SUCCESS = auto()
    FAILED = auto()
    ERROR = auto()


class BotStep(Enum):
    INIT = "初始化"
    WAIT_LOGIN = "等待登入"
    WAIT_SALE = "等待開賣"
    NAVIGATE = "前往活動頁"
    SELECT_SESSION = "選擇場次"
    SELECT_AREA = "選擇票區"
    FILL_FORM = "填寫購票資料"
    WAIT_QUEUE = "排隊中"
    WAIT_HUMAN = "等待人工驗證"
    SUBMIT = "送出訂單"
    COMPLETE = "完成"


@dataclass
class BotState:
    status: BotStatus = BotStatus.IDLE
    step: BotStep = BotStep.INIT
    retry_count: int = 0
    start_time: Optional[float] = None
    elapsed_time: float = 0.0
    message: str = ""
    error: Optional[str] = None


class BotEngine:
    def __init__(
        self,
        config: TicketConfig,
        browser_headless: bool = False,
        refresh_interval: int = 500,
        max_retries: int = 300,
        auto_agree: bool = True,
        wait_for_human: bool = True,
        driver_path: str = "",
        user_data_dir: str = ".chrome-profile",
        window_size: tuple = (1280, 900),
        page_load_timeout: int = 30,
        debugger_address: str = "",
        chrome_binary: str = "",
        prefer_windows_chrome: bool = True,
        parallel_windows: int = 1,
        window_index: int = 1,
    ):
        self.config = config
        self.browser_headless = browser_headless
        self.refresh_interval = max(0.2, refresh_interval / 1000.0)
        self.max_retries = max_retries
        self.auto_agree = auto_agree
        self.wait_for_human = wait_for_human
        self.driver_path = driver_path
        self.user_data_dir = user_data_dir
        self.window_size = window_size
        self.page_load_timeout = page_load_timeout
        self.debugger_address = debugger_address
        self.chrome_binary = chrome_binary
        self.prefer_windows_chrome = prefer_windows_chrome
        self.parallel_windows = clamp_parallel_windows(parallel_windows)
        self.window_index = max(1, int(window_index))

        self._state = BotState()
        self._stop_flag = threading.Event()
        self._start_booking_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._browser: Optional[BrowserManager] = None
        self._activity: Optional[ActivityPage] = None
        self._order: Optional[OrderPage] = None
        self._login: Optional[LoginPage] = None
        self._last_login_at = 0.0
        self._status_callbacks: List[StatusCallback] = []
        self._log_callbacks: List[LogCallback] = []
        self._last_advance_url = ""
        self._last_advance_at = 0.0
        self._logged_keys: set[str] = set()
        self._extra_engines: List["BotEngine"] = []
        self._winner_lock = threading.Lock()
        self._winner: Optional[int] = None

    @property
    def state(self) -> BotState:
        return self._state

    @property
    def is_running(self) -> bool:
        thread_alive = bool(self._thread and self._thread.is_alive())
        return thread_alive and self._state.status in {
            BotStatus.RUNNING,
            BotStatus.STARTING,
            BotStatus.WAITING_LOGIN,
        }

    @property
    def has_browser(self) -> bool:
        return bool(self._browser and self._browser.is_running)

    def add_status_callback(self, callback: StatusCallback) -> None:
        if callback not in self._status_callbacks:
            self._status_callbacks.append(callback)

    def add_log_callback(self, callback: LogCallback) -> None:
        if callback not in self._log_callbacks:
            self._log_callbacks.append(callback)

    def _log_once(self, key: str, message: str, level: str = "INFO") -> None:
        if key in self._logged_keys:
            return
        self._logged_keys.add(key)
        self._log(message, level)

    def _log(self, message: str, level: str = "INFO") -> None:
        getattr(logger, level.lower(), logger.info)(message)
        for callback in self._log_callbacks:
            try:
                callback(message, level)
            except Exception:
                pass

    def _update_state(
        self,
        status: Optional[BotStatus] = None,
        step: Optional[BotStep] = None,
        message: str = "",
        error: Optional[str] = None,
    ) -> None:
        if status:
            self._state.status = status
        if step:
            self._state.step = step
        if message:
            self._state.message = message
        self._state.error = error
        if self._state.start_time:
            self._state.elapsed_time = time.time() - self._state.start_time
        for callback in self._status_callbacks:
            try:
                callback(self._state)
            except Exception:
                pass

    def start(self) -> bool:
        if self.is_running:
            if self.has_browser:
                self._log("已經在執行中", "WARNING")
                return False
            self.stop(close_browser=True)
        errors = self.config.validate()
        if errors:
            self._log("設定錯誤: " + "；".join(errors), "ERROR")
            return False
        self._stop_flag.clear()
        self._start_booking_flag.clear()
        self._state = BotState(start_time=time.time())
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def apply_settings(
        self,
        config: TicketConfig,
        refresh_interval: Optional[int] = None,
        auto_agree: Optional[bool] = None,
        parallel_windows: Optional[int] = None,
    ) -> None:
        self.config = config
        if refresh_interval is not None:
            self.refresh_interval = max(0.2, refresh_interval / 1000.0)
        if auto_agree is not None:
            self.auto_agree = auto_agree
        if parallel_windows is not None:
            self.parallel_windows = clamp_parallel_windows(parallel_windows)

    def stop(self, close_browser: bool = False) -> None:
        self._log("正在停止搶票...")
        self._update_state(status=BotStatus.STOPPING)
        self._stop_extras(close_browser=close_browser)
        self._stop_flag.set()
        self._start_booking_flag.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=6)
        self._thread = None
        self._start_booking_flag.clear()
        self._stop_flag.clear()
        self._logged_keys.clear()
        self._last_advance_url = ""
        self._last_advance_at = 0.0
        if close_browser or not self.has_browser:
            self._cleanup()
            self._update_state(status=BotStatus.STOPPED, message="已停止")
            return
        self._update_state(
            status=BotStatus.WAITING_LOGIN,
            step=BotStep.WAIT_LOGIN,
            message="已停止，可改設定後再按開始搶票",
        )
        self._log("瀏覽器保持開啟。改好設定後再按「開始搶票」。")

    def trigger_start_booking(self) -> None:
        self._log("開始執行購票流程")
        self._prepare_parallel_windows()
        self._start_booking_flag.set()

    def start_booking(self) -> bool:
        """瀏覽器已開著時，用目前設定再跑一次搶票。"""
        errors = self.config.validate()
        if errors:
            self._log("設定錯誤: " + "；".join(errors), "ERROR")
            return False
        if not self.has_browser:
            self._note_browser_closed()
            return False
        if self._thread and self._thread.is_alive():
            if self._state.status == BotStatus.WAITING_LOGIN:
                self.trigger_start_booking()
                return True
            self._log("已經在執行中", "WARNING")
            return False
        self._stop_flag.clear()
        self._start_booking_flag.set()
        self._logged_keys.clear()
        self._last_advance_url = ""
        self._last_advance_at = 0.0
        self._winner = None
        self._state = BotState(start_time=time.time(), status=BotStatus.RUNNING)
        self._prepare_parallel_windows()
        self._thread = threading.Thread(target=self._run_booking, daemon=True)
        self._thread.start()
        return True

    def is_waiting_for_start(self) -> bool:
        return self._state.status == BotStatus.WAITING_LOGIN

    def _should_stop(self) -> bool:
        return self._stop_flag.is_set()

    def _sleep(self, seconds: Optional[float] = None) -> None:
        end = time.time() + (self.refresh_interval if seconds is None else seconds)
        while time.time() < end and not self._should_stop():
            time.sleep(0.05)

    def _cleanup(self) -> None:
        if self._browser:
            self._browser.stop()
            self._browser = None
        self._activity = None
        self._order = None
        self._login = None

    def _extra_profile_dir(self, index: int) -> str:
        base = (self.user_data_dir or ".chrome-profile").rstrip("\\/")
        return f"{base}-w{index}"

    def _stop_extras(self, close_browser: bool = True) -> None:
        extras = list(self._extra_engines)
        self._extra_engines = []
        for extra in extras:
            try:
                extra.stop(close_browser=close_browser)
            except Exception:
                pass

    def _make_extra_engine(self, index: int) -> "BotEngine":
        extra = BotEngine(
            config=self.config,
            browser_headless=self.browser_headless,
            refresh_interval=int(self.refresh_interval * 1000),
            max_retries=self.max_retries,
            auto_agree=self.auto_agree,
            wait_for_human=self.wait_for_human,
            driver_path=self.driver_path,
            user_data_dir=self._extra_profile_dir(index),
            window_size=self.window_size,
            page_load_timeout=self.page_load_timeout,
            debugger_address="",
            chrome_binary=self.chrome_binary,
            prefer_windows_chrome=self.prefer_windows_chrome,
            parallel_windows=1,
            window_index=index,
        )
        extra.add_log_callback(lambda message, level, n=index: self._log(f"[視窗{n}] {message}", level))
        extra.add_status_callback(lambda state, n=index: self._on_extra_status(state, n))
        return extra

    def _on_extra_status(self, state: BotState, index: int) -> None:
        if state.status == BotStatus.SUCCESS:
            self._declare_winner(index)

    def _declare_winner(self, index: int) -> None:
        with self._winner_lock:
            if self._winner is not None:
                return
            self._winner = index
        if index != self.window_index:
            self._log(f"視窗 {index} 已進入付款頁，關閉其他視窗")
            self._update_state(
                status=BotStatus.SUCCESS,
                step=BotStep.COMPLETE,
                message=f"視窗 {index} 已進入付款頁，請手動完成付款",
            )
            self._stop_flag.set()
        else:
            self._log("這個視窗已進入付款頁，關閉其他視窗")
        extras = list(self._extra_engines)
        kept: List["BotEngine"] = []
        for extra in extras:
            if extra.window_index == index:
                kept.append(extra)
                continue
            try:
                extra.stop(close_browser=True)
            except Exception:
                pass
        self._extra_engines = kept

    def _is_kktix(self) -> bool:
        return detect_platform(self.config.activity_url) == "kktix"

    def _open_login_wait_page(self) -> None:
        assert self._browser and self._browser.driver
        url = self.config.activity_url
        try:
            if self._is_kktix():
                target = url if is_mock_url(url) else "https://kktix.com/"
                self._browser.driver.get(target)
                return
            if is_mock_url(url):
                assert self._activity
                self._activity.open(url)
                return
            self._browser.open_home()
        except Exception as exc:
            if is_connection_refused(exc):
                target = url if is_mock_url(url) else ("https://kktix.com/" if self._is_kktix() else url)
                self._log(navigation_refused_hint(target), "ERROR")
                return
            raise

    def _prepare_parallel_windows(self) -> None:
        if self._is_kktix():
            self._log("KKTIX 不支援同時多視窗，只使用目前這個視窗")
            return
        count = clamp_parallel_windows(self.parallel_windows)
        if count <= 1 or self.window_index != 1:
            return
        if not self.has_browser or not self._browser:
            return
        self._winner = None
        self._stop_extras(close_browser=True)
        cookies = self._browser.export_cookies()
        if not cookies:
            self._log("沒有可複製的登入狀態，只開原本的視窗", "WARNING")
            return
        self._log(
            f"再開 {count - 1} 個獨立視窗搶同一場。遠大可能擋同一帳號多開；一個進付款會關掉其他視窗。",
            "WARNING",
        )
        for index in range(2, count + 1):
            extra = self._make_extra_engine(index)
            if extra.bootstrap_session(cookies, self.config.activity_url):
                extra.start_booking()
                self._extra_engines.append(extra)
                self._log(f"視窗 {index} 已開啟")
            else:
                extra.stop(close_browser=True)
                self._log(f"視窗 {index} 啟動失敗", "WARNING")

    def bootstrap_session(self, cookies: list, url: str) -> bool:
        """給多開視窗用：開新 Chrome、寫入主視窗的 cookie。"""
        if not self._initialize():
            return False
        assert self._browser
        if not self._browser.import_cookies(cookies, url or "https://ticketplus.com.tw/"):
            self._log("複製登入 cookie 失敗", "WARNING")
            return False
        return True

    def _note_browser_closed(self) -> None:
        self._log("瀏覽器已關閉，請重新按「啟動瀏覽器」", "WARNING")
        self._cleanup()
        self._update_state(
            status=BotStatus.STOPPED,
            step=BotStep.INIT,
            message="瀏覽器已關閉，請重新啟動瀏覽器",
        )

    def _browser_still_open(self) -> bool:
        if self.has_browser:
            return True
        self._note_browser_closed()
        return False

    def _wait_while_idle(self, seconds: float) -> bool:
        """Sleep, but abort if the user closed Chrome. Return False if browser is gone."""
        end = time.time() + max(0.0, seconds)
        while time.time() < end and not self._should_stop():
            if not self.has_browser:
                self._note_browser_closed()
                return False
            time.sleep(min(0.25, end - time.time()))
        return self.has_browser or self._should_stop()

    def _finish_after_execute(self, success: bool) -> None:
        if self._state.status == BotStatus.STOPPED and not self.has_browser:
            return
        if self._winner and self._winner != self.window_index:
            return
        if success:
            self._declare_winner(self.window_index)
            self._update_state(
                status=BotStatus.SUCCESS,
                step=BotStep.COMPLETE,
                message="已進入付款頁，請手動完成付款",
            )
            self._log("已進入付款頁。瀏覽器會保持開啟，請自行完成付款與 3D 驗證。")
            self._beep()
            while not self._should_stop():
                if not self._wait_while_idle(1.0):
                    return
            if self.has_browser:
                self._update_state(
                    status=BotStatus.WAITING_LOGIN,
                    step=BotStep.WAIT_LOGIN,
                    message="可改設定後再按開始搶票",
                )
            return
        if self._state.status == BotStatus.STOPPED:
            return
        if not self._should_stop():
            self._update_state(status=BotStatus.FAILED, message="未能完成購票")
        elif self.has_browser:
            self._update_state(
                status=BotStatus.WAITING_LOGIN,
                step=BotStep.WAIT_LOGIN,
                message="已停止，可改設定後再按開始搶票",
            )

    def _looks_like_dead_browser(self, exc: Exception) -> bool:
        text = str(exc).lower()
        needles = (
            "invalid session",
            "no such window",
            "chrome not reachable",
            "disconnected",
            "target window already closed",
            "web view not found",
            "session deleted",
        )
        return any(n in text for n in needles)

    def _run(self) -> None:
        try:
            self._update_state(status=BotStatus.STARTING, step=BotStep.INIT, message="初始化中")
            if not self._initialize():
                self._cleanup()
                self._update_state(status=BotStatus.ERROR, error="初始化失敗")
                return

            self._update_state(
                status=BotStatus.WAITING_LOGIN,
                step=BotStep.WAIT_LOGIN,
                message="請在瀏覽器登入，完成後點「開始搶票」",
            )
            self._open_login_wait_page()
            if self._is_kktix():
                if self.config.account and self.config.password:
                    self._log("尚未登入，啟動後將自動登入")
                else:
                    self._log("請先在瀏覽器登入 KKTIX，或在設定填入 Email 與密碼以啟用自動登入")
            elif self._login and self._login.is_logged_in():
                self._log("已登入，略過自動登入")
            elif self.config.account and self.config.password:
                self._log("尚未登入，啟動後將自動登入")
            else:
                self._log("請先在瀏覽器登入 TicketPlus，或在設定填入手機與密碼以啟用自動登入")
            self._log("準備好後點「開始搶票」")

            while not self._start_booking_flag.is_set() and not self._should_stop():
                if not self._browser_still_open():
                    return
                time.sleep(0.25)
            if self._should_stop():
                return
            if not self._browser_still_open():
                return

            if not self._is_kktix():
                self._ensure_login(force_navigate_back=False)
            self._update_state(status=BotStatus.RUNNING)
            self._finish_after_execute(self._execute())
        except Exception as exc:
            if self._looks_like_dead_browser(exc):
                self._note_browser_closed()
                return
            self._log(f"執行錯誤: {exc}", "ERROR")
            self._update_state(status=BotStatus.ERROR, error=str(exc))

    def _run_booking(self) -> None:
        try:
            if not self._browser_still_open():
                return
            self._log("開始執行購票流程")
            self._update_state(status=BotStatus.RUNNING, step=BotStep.NAVIGATE, message="開始搶票")
            if not self._is_kktix():
                self._ensure_login(force_navigate_back=False)
            self._finish_after_execute(self._execute())
        except Exception as exc:
            if self._looks_like_dead_browser(exc):
                self._note_browser_closed()
                return
            self._log(f"執行錯誤: {exc}", "ERROR")
            self._update_state(status=BotStatus.ERROR, error=str(exc))

    def _initialize(self) -> bool:
        try:
            self._browser = BrowserManager(
                driver_path=self.driver_path or None,
                headless=self.browser_headless,
                window_size=self.window_size,
                page_load_timeout=self.page_load_timeout,
                user_data_dir=self.user_data_dir or None,
                debugger_address=self.debugger_address or None,
                chrome_binary=self.chrome_binary or None,
                prefer_windows_chrome=self.prefer_windows_chrome,
                window_position=(40 + 80 * (self.window_index - 1), 40 + 40 * (self.window_index - 1)),
            )
            driver = self._browser.start()
            self._activity = ActivityPage(driver)
            self._order = OrderPage(driver)
            self._login = LoginPage(driver)
            return True
        except Exception as exc:
            self._log(f"啟動瀏覽器失敗: {exc}", "ERROR")
            return False

    def _execute(self) -> bool:
        if detect_platform(self.config.activity_url) == "kktix":
            from .kktix_flow import KktixFlow

            return KktixFlow(self).run()

        assert self._activity and self._order
        event_id = self.config.get_event_id()
        if not event_id:
            self._log("無法解析 eventId", "ERROR")
            return False

        self._update_state(step=BotStep.NAVIGATE, message="開啟活動頁")
        self._activity.open(self.config.activity_url)
        self._activity.wait_vue_ready()
        self._activity.dismiss_popups()

        retries = 0
        while not self._should_stop() and retries < self.max_retries:
            if not self._browser_still_open():
                return False
            self._state.retry_count = retries
            url = self._activity.current_url

            if self._ensure_login(force_navigate_back=True):
                if not self._login.is_logged_in():
                    self._sleep(1.0)
                    continue
                retries += 1
                continue
            if self._handle_human_gate():
                continue
            if self._handle_queue():
                continue
            if self._activity.has_loading_overlay():
                self._log("電腦配位 / 處理中，等待轉圈結束")
                self._activity.wait_loading_overlay(timeout=25)
                continue

            if is_payment_url(url):
                self._log(f"已到達付款頁: {url}")
                return True

            if is_activity_url(url):
                self._update_state(step=BotStep.SELECT_SESSION, message="選擇場次")
                self._activity.wait_vue_ready(timeout=4)
                self._activity.dismiss_popups()
                opened = self._activity.try_open_session(
                    event_id=event_id,
                    target_session=self.config.target_session,
                    exclude_keywords=self.config.session_exclude_keywords,
                )
                if not opened:
                    if self._activity.has_sold_out_only():
                        self._log("目前可見場次皆售完，稍後重試")
                    elif self._activity.has_not_on_sale():
                        self._update_state(step=BotStep.WAIT_SALE, message="尚未開賣，刷新等待")
                    else:
                        self._log("還沒找到可點的立即購，刷新後再試")
                    self._activity.refresh_for_sale(full_reload=(retries % 8 == 7))
                    self._sleep()
                    retries += 1
                    continue
                self._sleep(0.4)
                retries += 1
                continue

            if is_order_url(url) or is_confirm_url(url):
                if self._order.looks_like_area_picker() and not self._order.has_hold():
                    self._log("網址已是購票頁但畫面還在活動頁，強制重整購票頁")
                    self._order.navigate_to(url.split("#")[0])
                    self._sleep(1.0)
                    retries += 1
                    continue

                if is_confirm_url(url) and not self._order.has_hold():
                    self._update_state(step=BotStep.FILL_FORM, message="等待電腦配位結果")
                    self._log_once("wait-seat", "已在確認座位頁，等待配位")
                    self._order.wait_loading_overlay(timeout=12)
                    self._sleep(0.6)
                    retries += 1
                    continue

                if self._order.has_hold():
                    hold = self._order.reservation_info()
                    self._log_once(
                        "hold",
                        f"已有鎖票結果（{hold.get('qty')} 張 / 座位 {hold.get('seats')}），不再重選票區",
                    )
                    self._update_state(step=BotStep.SUBMIT, message="已選位，往下一步")
                    self._advance_after_hold(url)
                    self._sleep(0.8)
                    retries += 1
                    continue

                if is_order_url(url):
                    self._order.wait_vue_ready(timeout=4)
                    sale = self._order.detect_sale_state()
                    if sale.get("state") != "on_sale":
                        self._refresh_order_tickets("尚未開賣" if sale.get("state") == "not_on_sale" else "票區狀態未明")
                    if sale.get("state") == "not_on_sale":
                        sample = (sale.get("samples") or [""])[0]
                        hint = f"（例：{sample}）" if sample else ""
                        self._update_state(step=BotStep.WAIT_SALE, message="尚未開賣，持續更新票數")
                        self._log_once("wait-sale-ui", f"購票頁尚未開賣，票區顯示開賣時間{hint}，持續點「更新票數」")
                        self._sleep()
                        retries += 1
                        continue
                    if sale.get("state") == "on_sale":
                        self._log_once("sale-open", "購票頁已開賣（票區可選數量或已售完）")
                    if self._process_order():
                        self._sleep(0.8)
                        retries += 1
                        continue
                    if self._order.dismiss_failure_dialog():
                        self._log("購票失敗視窗已關閉，稍後再選一次")
                        self._sleep()
                        retries += 1
                        continue
                    self._refresh_order_tickets("沒有可選票區")
                    self._sleep()
                    retries += 1
                    continue

            if is_login_url(url) or "signin" in url.lower():
                if self._ensure_login(force_navigate_back=True):
                    if not self._login.is_logged_in():
                        self._sleep(1.0)
                    retries += 1
                    continue
                self._sleep(1.0)
                continue

            if self._order.has_hold():
                self._log(f"已鎖票，忽略未預期頁面並嘗試下一步: {url}")
                self._order.click_advance()
                self._sleep(0.8)
                retries += 1
                continue

            self._log(f"未預期的頁面: {url}，回到活動頁")
            self._activity.open(self.config.activity_url)
            self._sleep()
            retries += 1

        return is_payment_url(self._activity.current_url)

    def _refresh_order_tickets(self, reason: str) -> bool:
        """未開賣或沒票時都按購票頁「更新票數」。"""
        assert self._order
        if self._order.click_update_ticket_count():
            self._log_once("refresh-stock", f"{reason}，已點「更新票數」")
            return True
        self._log_once("refresh-stock-miss", f"{reason}，但找不到「更新票數」按鈕")
        return False

    def _process_order(self) -> bool:
        assert self._order
        self._update_state(step=BotStep.SELECT_AREA, message="選擇票區 / 票種")
        self._order.wait_vue_ready(timeout=6)
        if self._order.dismiss_failure_dialog():
            return False
        if self._handle_human_gate() or self._handle_queue():
            return False

        if self._order.has_hold():
            self._log("購票頁已有鎖票，改按下一步")
            return self._order.click_advance()

        if not self._order.wait_for_area_widgets(timeout=5):
            return False
        if self._order.is_not_on_sale():
            return False

        priorities = [p for p in self.config.area_priorities if p and str(p).strip()]
        allow_fallback = bool(self.config.fallback_first_available) or not priorities
        if not priorities:
            self._log_once("auto-area", "未指定票區優先級，改選畫面上第一個可購票區")
        elif allow_fallback:
            self._log_once("auto-area-fallback", "優先票區沒票時，改選畫面上第一個可購票區")
        selected = self._order.select_area_and_quantity(
            area_priorities=priorities,
            quantity=self.config.quantity,
            allow_fallback=allow_fallback,
            require_exact_quantity=bool(self.config.require_exact_quantity),
        )
        if not selected:
            names = self._order.list_area_names()
            self._log_once(
                "miss-area",
                f"尚未選到票區（設定：{self.config.area_priorities}；畫面：{names or '尚未出現'}）",
            )
            return False

        self._update_state(step=BotStep.FILL_FORM, message="填序號與條款")
        if self._order.has_exclusive_code_field():
            code = (self.config.exclusive_code or "").strip()
            if not code:
                self._log_once("need-code", "購票頁出現遠傳優先購序號欄，但設定未填序號")
                return False
            if not self._order.fill_exclusive_code(code):
                self._log_once("fill-code-fail", "找到遠傳優先購序號欄但填入失敗")
                return False
        if self.auto_agree:
            self._order.agree_terms()

        if not self._order.next_enabled():
            self._log("下一步按鈕尚未可按，可能張數未生效或還在驗證")
            return False

        self._update_state(step=BotStep.SUBMIT, message="送出下一步")
        return self._order.click_next()

    def _advance_after_hold(self, url: str) -> bool:
        """選位 / 鎖票後只往前走，不重選、不清空、不重整。"""
        assert self._order
        now = time.time()
        if url == self._last_advance_url and now - self._last_advance_at < 2.5:
            return False
        self._order.wait_vue_ready(timeout=4)
        if self._order.dismiss_failure_dialog():
            return False
        if self._handle_human_gate() or self._handle_queue():
            return False
        # /confirm 才勾條款與取票方式；confirmSeat 動 radio 會跳出電腦配位
        path = (url or "").lower()
        if "/confirm/" in path and "confirmseat" not in path:
            if self.auto_agree:
                self._order.agree_terms()
            picked = self._order.select_pickup_radios()
            if picked:
                self._log(f"已選取票 / 付款方式 {picked} 組")
        if not self._order.next_enabled():
            return False
        clicked = self._order.click_advance()
        if clicked:
            self._last_advance_url = url
            self._last_advance_at = now
        return clicked

    def _process_confirm(self) -> bool:
        return self._advance_after_hold(self._order.current_url)

    def _ensure_login(self, force_navigate_back: bool = True) -> bool:
        """未登入就停在登入，不要去刷新活動 / 購票頁。

        回傳 True：還沒準備好搶票（等登入，或剛登入完要回到活動頁）。
        回傳 False：已登入，可以繼續。
        """
        assert self._login
        if self._login.is_logged_in() and not self._login.has_login_form():
            return False

        self._update_state(step=BotStep.WAIT_LOGIN, message="尚未登入，先完成登入")
        mobile = (self.config.account or "").strip()
        password = self.config.password or ""
        if not mobile or not password:
            self._log_once("need-login", "尚未登入。請在瀏覽器登入，登入完成後會繼續，不會重刷頁面")
            return True

        now = time.time()
        if now - self._last_login_at >= 5:
            self._last_login_at = now
            self._try_auto_login(mobile, password)

        if self._login.is_logged_in() and not self._login.has_login_form():
            self._log("自動登入成功")
            if force_navigate_back and self.config.activity_url:
                self._activity.open(self.config.activity_url)
                self._sleep(0.8)
            return True

        if self._login.has_login_form() or is_login_url(self._login.current_url):
            self._log_once("wait-login-form", "停在登入頁等待登入完成，先不刷新活動頁")
        return True

    def _try_auto_login(self, mobile: str, password: str) -> None:
        self._log("偵測到未登入，正在自動登入")
        if not self._login.has_login_form():
            if not self._login.open_login_form():
                self._log("打不開登入表單，稍後再試", "WARNING")
                return
        if self._login.has_recaptcha() and self.wait_for_human:
            self._log("登入出現驗證碼，請在瀏覽器完成")
            while not self._should_stop() and self._login.has_recaptcha():
                self._sleep(0.5)
        if not self._login.fill_and_submit(mobile, password, self.config.country_code or "+886"):
            self._log("自動填寫登入失敗，稍後再試或改手動登入", "WARNING")
            return
        if self._login.wait_until_logged_in(timeout=12):
            return
        if self._login.has_recaptcha() and self.wait_for_human:
            self._log("登入需要驗證碼，請在瀏覽器完成後會繼續")
            while not self._should_stop() and not self._login.is_logged_in():
                self._sleep(0.5)
            return
        err = self._login.login_error_text()
        if err:
            self._log(f"登入沒過：頁面顯示「{err}」。帳密若正確，可能是驗證碼或門號格式", "WARNING")
        else:
            self._log("自動登入尚未成功，停在登入頁等你完成，不會重刷", "WARNING")

    def _handle_queue(self) -> bool:
        assert self._activity
        if not self._activity.is_in_queue():
            return False
        self._update_state(step=BotStep.WAIT_QUEUE, message="官方排隊中，請勿關頁")
        self._log("偵測到排隊畫面，停留等待官方放行")
        while not self._should_stop() and self._activity.is_in_queue():
            if is_payment_url(self._activity.current_url):
                return False
            self._sleep(1.0)
        return True

    def _handle_human_gate(self) -> bool:
        assert self._activity
        cloudflare = self._activity.is_cloudflare_challenge() is True
        if cloudflare:
            self._update_state(step=BotStep.WAIT_HUMAN, message="請在瀏覽器完成 Cloudflare 人機驗證")
            self._log_once(
                "cf-challenge",
                "出現 Cloudflare「正在驗證您是否是人類」。請在這個 Chrome 視窗完成，完成前不會重整。",
            )
            while not self._should_stop() and self._activity.is_cloudflare_challenge():
                self._sleep(0.5)
            return True
        if not self._activity.has_recaptcha():
            return False
        if not self.wait_for_human:
            self._log("出現 reCAPTCHA，但 wait_for_human=false，稍後重試", "WARNING")
            self._sleep(1.0)
            return True
        self._update_state(step=BotStep.WAIT_HUMAN, message="請在瀏覽器完成驗證碼")
        self._log("出現 reCAPTCHA，請在瀏覽器手動完成，完成後程式會繼續")
        while not self._should_stop() and self._activity.has_recaptcha():
            self._sleep(0.5)
        return True

    def _beep(self) -> None:
        try:
            print("\a", end="", flush=True)
        except Exception:
            pass
