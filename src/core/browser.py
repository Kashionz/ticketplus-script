"""Chrome WebDriver 管理。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webdriver import WebDriver

from ..utils.windows_chrome import find_open_debugger, is_wsl

logger = logging.getLogger("ticketplus")

HOME_URL = "https://ticketplus.com.tw/"


def chrome_launch_hint(exc: BaseException, user_data_dir: Optional[str] = None) -> str:
    text = str(exc)
    blob = text.lower()
    profile = user_data_dir or ".chrome-profile"
    if "session not created" in blob or "chrome instance exited" in blob or "user data directory is already in use" in blob:
        return (
            "Chrome 啟動後立刻結束（session not created）。常見原因：\n"
            f"1) 另一個 Chrome 佔用同一個設定檔「{profile}」，請先關掉所有 Chrome 再試\n"
            f"2) 刪除專案裡的「{profile}」資料夾後重開（會清掉該檔的登入狀態）\n"
            "3) 或雙擊 open-chrome.bat，在那個視窗登入後再按啟動瀏覽器"
        )
    return f"啟動 Chrome 失敗: {text}"


class BrowserManager:
    def __init__(
        self,
        driver_path: Optional[str] = None,
        headless: bool = False,
        window_size: Tuple[int, int] = (1280, 900),
        page_load_timeout: int = 30,
        user_data_dir: Optional[str] = None,
        debugger_address: Optional[str] = None,
        chrome_binary: Optional[str] = None,
        prefer_windows_chrome: bool = True,
        window_position: Optional[Tuple[int, int]] = None,
    ):
        self.driver_path = driver_path or ""
        self.headless = headless
        self.window_size = window_size
        self.page_load_timeout = page_load_timeout
        self.user_data_dir = user_data_dir
        self.debugger_address = (debugger_address or "").strip()
        self.chrome_binary = chrome_binary or ""
        self.prefer_windows_chrome = prefer_windows_chrome
        self.window_position = window_position
        self._driver: Optional[WebDriver] = None
        self._attached = False

    @property
    def driver(self) -> Optional[WebDriver]:
        return self._driver

    @property
    def is_running(self) -> bool:
        if self._driver is None:
            return False
        try:
            _ = self._driver.current_window_handle
            return True
        except WebDriverException:
            return False

    def _attach_options(self, address: str) -> Options:
        options = Options()
        options.add_experimental_option("debuggerAddress", address)
        return options

    def _launch_options(self) -> Options:
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--window-size={self.window_size[0]},{self.window_size[1]}")
        if self.window_position:
            options.add_argument(
                f"--window-position={int(self.window_position[0])},{int(self.window_position[1])}"
            )
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--lang=zh-TW")
        if self.headless:
            options.add_argument("--headless=new")
        if self.user_data_dir:
            profile = Path(self.user_data_dir).expanduser().resolve()
            profile.mkdir(parents=True, exist_ok=True)
            options.add_argument(f"--user-data-dir={str(profile)}")
        if self.chrome_binary:
            options.binary_location = self.chrome_binary
        # Chrome 151+ 加上 enable-automation / AutomationControlled 會直接閃退
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        return options

    def _service(self) -> Service:
        if self.driver_path:
            return Service(executable_path=self.driver_path)
        return Service()

    def _connect(self, options: Options) -> WebDriver:
        driver = webdriver.Chrome(service=self._service(), options=options)
        driver.set_page_load_timeout(self.page_load_timeout)
        driver.implicitly_wait(0.2)
        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"},
            )
        except Exception:
            pass
        return driver

    def start(self) -> WebDriver:
        if self.is_running:
            return self._driver
        if self._driver is not None:
            self.stop()

        address = self.debugger_address
        if not address and self.prefer_windows_chrome and is_wsl() and not self.headless:
            address = find_open_debugger()
            if not address:
                raise RuntimeError(
                    "目前在 WSL，不會使用 Linux 內建 Chrome。\n"
                    "請擇一：\n"
                    "1) 在 Windows 雙擊 open-chrome.bat，登入後再按啟動瀏覽器\n"
                    "2) 用 Windows 的 Python 執行：py -3 -m src.main\n"
                    "3) 設定 browser.debugger_address: 127.0.0.1:9222"
                )

        if address:
            logger.info("接上已開啟的 Chrome: %s", address)
            self._driver = self._connect(self._attach_options(address))
            self._attached = True
            logger.info("已接上 Windows Chrome，目前頁面: %s", self._driver.current_url)
            return self._driver

        logger.info("啟動 Chrome...")
        try:
            self._driver = self._connect(self._launch_options())
        except WebDriverException as exc:
            hint = chrome_launch_hint(exc, self.user_data_dir)
            raise RuntimeError(hint) from exc
        self._attached = False
        logger.info("Chrome 已啟動")
        return self._driver

    def open_home(self) -> None:
        if not self._driver:
            raise RuntimeError("瀏覽器尚未啟動")
        self._driver.get(HOME_URL)

    def export_cookies(self) -> List[Dict[str, Any]]:
        if not self._driver:
            return []
        try:
            return list(self._driver.get_cookies() or [])
        except WebDriverException:
            return []

    def import_cookies(self, cookies: List[Dict[str, Any]], url: str) -> bool:
        """先開同網域再寫 cookie，用來把已登入狀態複製到另一個 Chrome。"""
        if not self._driver or not cookies:
            return False
        parsed = urlparse(url or HOME_URL)
        origin = f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else HOME_URL
        self._driver.get(origin)
        imported = 0
        for raw in cookies:
            cookie = {k: raw[k] for k in ("name", "value", "path", "secure") if k in raw}
            if not cookie.get("name"):
                continue
            if "domain" in raw and raw["domain"]:
                cookie["domain"] = raw["domain"]
            if "expiry" in raw:
                try:
                    cookie["expiry"] = int(raw["expiry"])
                except (TypeError, ValueError):
                    pass
            try:
                self._driver.add_cookie(cookie)
                imported += 1
            except Exception:
                cookie.pop("domain", None)
                try:
                    self._driver.add_cookie(cookie)
                    imported += 1
                except Exception:
                    continue
        target = url or origin
        try:
            self._driver.get(target)
        except Exception:
            self._driver.refresh()
        return imported > 0

    def stop(self) -> None:
        if not self._driver:
            return
        try:
            if self._attached:
                # 只斷開控制，不要關掉使用者的 Windows Chrome
                try:
                    self._driver.service.stop()
                except Exception:
                    pass
            else:
                self._driver.quit()
        except Exception as exc:
            logger.debug("關閉瀏覽器失敗: %s", exc)
        finally:
            self._driver = None
