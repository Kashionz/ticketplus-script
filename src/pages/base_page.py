"""頁面基礎類別。"""

from __future__ import annotations

import logging
import time
from typing import Any, List, Optional, Tuple

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger("ticketplus")
Locator = Tuple[str, str]


class BasePage:
    DEFAULT_TIMEOUT = 8
    BASE_URL = "https://ticketplus.com.tw"

    def __init__(self, driver: WebDriver, timeout: int = DEFAULT_TIMEOUT):
        self.driver = driver
        self.timeout = timeout

    @property
    def current_url(self) -> str:
        return self.driver.current_url

    def navigate_to(self, url: str) -> bool:
        try:
            self.driver.get(url)
            return True
        except Exception as exc:
            logger.debug("導航失敗: %s", exc)
            return False

    def refresh(self) -> None:
        try:
            self.driver.refresh()
        except Exception as exc:
            logger.debug("重新整理失敗: %s", exc)

    def wait_seconds(self, seconds: float) -> None:
        time.sleep(max(0.0, seconds))

    def find_element(self, locator: Locator, timeout: Optional[int] = None) -> Optional[WebElement]:
        try:
            wait = WebDriverWait(self.driver, timeout if timeout is not None else self.timeout)
            return wait.until(EC.presence_of_element_located(locator))
        except TimeoutException:
            return None

    def find_elements(self, locator: Locator, timeout: Optional[int] = None) -> List[WebElement]:
        element = self.find_element(locator, timeout=timeout)
        if not element:
            return []
        return self.driver.find_elements(*locator)

    def find_clickable(self, locator: Locator, timeout: Optional[int] = None) -> Optional[WebElement]:
        try:
            wait = WebDriverWait(self.driver, timeout if timeout is not None else self.timeout)
            return wait.until(EC.element_to_be_clickable(locator))
        except TimeoutException:
            return None

    def click(self, locator: Locator, timeout: Optional[int] = None) -> bool:
        element = self.find_clickable(locator, timeout=timeout)
        if not element:
            return False
        return self.click_element(element)

    def click_element(self, element: WebElement) -> bool:
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
            element.click()
            return True
        except (ElementClickInterceptedException, StaleElementReferenceException):
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return True
            except Exception as exc:
                logger.debug("點擊失敗: %s", exc)
                return False
        except Exception as exc:
            logger.debug("點擊失敗: %s", exc)
            return False

    def execute_js(self, script: str, *args: Any) -> Any:
        return self.driver.execute_script(script, *args)

    def page_text(self) -> str:
        try:
            return self.driver.find_element("tag name", "body").text or ""
        except Exception:
            return ""

    def is_logged_in(self) -> bool:
        try:
            cookies = self.driver.get_cookies()
        except Exception:
            return False
        for cookie in cookies:
            if cookie.get("name") == "user" and "account" in (cookie.get("value") or ""):
                return True
        return False

    def has_recaptcha(self) -> bool:
        return bool(
            self.execute_js(
                """
                return Boolean(
                    document.querySelector('iframe[src*="recaptcha"]') ||
                    document.querySelector('.g-recaptcha') ||
                    document.querySelector('#rc-anchor-container')
                );
                """
            )
        )

    def has_loading_overlay(self) -> bool:
        return bool(
            self.execute_js(
                "return Boolean(document.querySelector('.v-overlay--active .v-progress-circular'));"
            )
        )

    def wait_loading_overlay(self, timeout: float = 20.0) -> bool:
        """等電腦配位轉圈結束。回傳是否已消失。"""
        elapsed = 0.0
        while elapsed < timeout:
            if not self.has_loading_overlay():
                return True
            self.wait_seconds(0.25)
            elapsed += 0.25
        return not self.has_loading_overlay()

    def is_in_queue(self) -> bool:
        return bool(
            self.execute_js(
                """
                const keywords = ['排隊購票中', '請別離開頁面', '請勿關閉網頁',
                                  '同時使用多個裝置', '視窗購票'];
                const body = document.body ? (document.body.innerText || '') : '';
                const dialog = document.querySelector('.v-dialog');
                const dialogText = dialog ? (dialog.innerText || '') : '';
                return keywords.some(k => body.includes(k) || dialogText.includes(k));
                """
            )
        )
