"""日誌管理。"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, List, Optional

try:
    import colorlog

    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False


LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
COLOR_FORMAT = "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s"
COLOR_LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
}

LOGGER_NAME = "ticket-helper"
_gui_handlers: List[Callable[[str, str], None]] = []


class GUILogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            for handler in _gui_handlers:
                try:
                    handler(msg, record.levelname)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)


def register_gui_handler(handler: Callable[[str, str], None]) -> None:
    if handler not in _gui_handlers:
        _gui_handlers.append(handler)


def unregister_gui_handler(handler: Callable[[str, str], None]) -> None:
    if handler in _gui_handlers:
        _gui_handlers.remove(handler)


def setup_logger(
    name: str = LOGGER_NAME,
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_output: bool = True,
    max_file_size: int = 10,
    backup_count: int = 5,
    enable_gui_handler: bool = False,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    logger.setLevel(log_level)
    formatter = logging.Formatter(DEFAULT_FORMAT, DEFAULT_DATE_FORMAT)

    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        if HAS_COLORLOG:
            console_handler.setFormatter(
                colorlog.ColoredFormatter(
                    COLOR_FORMAT,
                    datefmt=DEFAULT_DATE_FORMAT,
                    log_colors=COLOR_LOG_COLORS,
                )
            )
        else:
            console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_file_size * 1024 * 1024,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if enable_gui_handler:
        gui_handler = GUILogHandler()
        gui_handler.setLevel(log_level)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)

    logger.propagate = False
    return logger


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    return logging.getLogger(name)


_default_logger: Optional[logging.Logger] = None


def init_default_logger(
    level: str = "INFO",
    log_file: Optional[str] = "logs/bot.log",
    console_output: bool = True,
) -> logging.Logger:
    global _default_logger
    _default_logger = setup_logger(
        name=LOGGER_NAME,
        level=level,
        log_file=log_file,
        console_output=console_output,
        enable_gui_handler=True,
    )
    return _default_logger
