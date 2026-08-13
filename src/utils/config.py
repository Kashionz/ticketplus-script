"""設定管理。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ..models.ticket_config import TicketConfig


def get_app_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


class Config:
    DEFAULT_CONFIG_PATH = "config/config.yaml"
    EXAMPLE_CONFIG_PATH = "config/config.example.yaml"

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _resolve(self, relative: str) -> Path:
        path = Path(relative)
        if path.is_absolute():
            return path
        return get_app_path() / relative

    def _load_config(self) -> None:
        config_file = self._resolve(self.config_path)
        if not config_file.exists():
            example = self._resolve(self.EXAMPLE_CONFIG_PATH)
            if example.exists():
                config_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(example, config_file)
            else:
                raise FileNotFoundError(
                    f"找不到設定檔: {config_file}\n"
                    f"請複製 {self.EXAMPLE_CONFIG_PATH} 為 {self.config_path}"
                )
        with open(config_file, "r", encoding="utf-8") as fh:
            self._config = yaml.safe_load(fh) or {}

    def reload(self) -> None:
        self._load_config()

    def save(self) -> None:
        config_file = self._resolve(self.config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as fh:
            yaml.dump(self._config, fh, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def get(self, key: str, default: Any = None) -> Any:
        value: Any = self._config
        for part in key.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        node = self._config
        parts = key.split(".")
        for part in parts[:-1]:
            if part not in node or not isinstance(node[part], dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value

    def get_ticket_config(self) -> TicketConfig:
        return TicketConfig(
            activity_url=self.get("ticket.activity_url", ""),
            target_session=self.get("ticket.target_session", ""),
            quantity=int(self.get("ticket.quantity", 2)),
            area_priorities=list(self.get("ticket.area_priorities", []) or []),
            session_exclude_keywords=list(self.get("ticket.session_exclude_keywords", []) or []),
            exclusive_code=self.get("ticket.exclusive_code", "") or "",
            fallback_first_available=bool(self.get("ticket.fallback_first_available", False)),
            account=self.get("account.mobile", "") or self.get("account.account", "") or "",
            password=self.get("account.password", "") or "",
            country_code=self.get("account.country_code", "+886") or "+886",
        )

    def set_ticket_config(self, ticket_config: TicketConfig) -> None:
        self.set("ticket.activity_url", ticket_config.activity_url)
        self.set("ticket.target_session", ticket_config.target_session)
        self.set("ticket.quantity", ticket_config.quantity)
        self.set("ticket.area_priorities", ticket_config.area_priorities)
        self.set("ticket.session_exclude_keywords", ticket_config.session_exclude_keywords)
        self.set("ticket.exclusive_code", ticket_config.exclusive_code)
        self.set("ticket.fallback_first_available", ticket_config.fallback_first_available)
        self.set("account.mobile", ticket_config.account)
        self.set("account.password", ticket_config.password)
        self.set("account.country_code", ticket_config.country_code or "+886")

    @property
    def browser_driver_path(self) -> str:
        return self.get("browser.driver_path", "") or ""

    @property
    def browser_headless(self) -> bool:
        return bool(self.get("browser.headless", False))

    @property
    def browser_page_load_timeout(self) -> int:
        return int(self.get("browser.page_load_timeout", 30))

    @property
    def browser_element_timeout(self) -> int:
        return int(self.get("browser.element_timeout", 8))

    @property
    def browser_window_size(self) -> tuple:
        return (
            int(self.get("browser.window_width", 1280)),
            int(self.get("browser.window_height", 900)),
        )

    @property
    def browser_user_data_dir(self) -> str:
        return self.get("browser.user_data_dir", ".chrome-profile") or ""

    @property
    def browser_debugger_address(self) -> str:
        return self.get("browser.debugger_address", "") or ""

    @property
    def browser_chrome_binary(self) -> str:
        return self.get("browser.chrome_binary", "") or ""

    @property
    def browser_prefer_windows_chrome(self) -> bool:
        return bool(self.get("browser.prefer_windows_chrome", True))

    @property
    def bot_refresh_interval(self) -> int:
        return max(200, int(self.get("bot.refresh_interval", 500)))

    @property
    def bot_max_retries(self) -> int:
        return int(self.get("bot.max_retries", 300))

    @property
    def bot_auto_agree(self) -> bool:
        return bool(self.get("bot.auto_agree", True))

    @property
    def bot_sound_notification(self) -> bool:
        return bool(self.get("bot.sound_notification", True))

    @property
    def bot_wait_for_human(self) -> bool:
        return bool(self.get("bot.wait_for_human", True))

    @property
    def logging_level(self) -> str:
        return self.get("logging.level", "INFO")

    @property
    def logging_file_path(self) -> str:
        return self.get("logging.file_path", "logs/bot.log")


_global_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    global _global_config
    if _global_config is None:
        _global_config = Config(config_path)
    return _global_config
