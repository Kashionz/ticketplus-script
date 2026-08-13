"""日誌顯示元件。"""

from datetime import datetime
from typing import Optional

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogWidget(QWidget):
    log_received = pyqtSignal(str, str)

    LOG_COLORS = {
        "DEBUG": "#808080",
        "INFO": "#000000",
        "WARNING": "#FF8C00",
        "ERROR": "#FF0000",
        "CRITICAL": "#8B0000",
        "SUCCESS": "#228B22",
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._all_logs = []
        self._current_level = "INFO"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        title = QLabel("執行日誌")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)
        header.addStretch()
        self.level_combo = QComboBox()
        self.level_combo.addItems(["全部", "DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_combo.setCurrentText("INFO")
        self.level_combo.currentTextChanged.connect(self._on_level_changed)
        header.addWidget(QLabel("篩選:"))
        header.addWidget(self.level_combo)
        clear_btn = QPushButton("清除")
        clear_btn.clicked.connect(self.clear)
        header.addWidget(clear_btn)
        layout.addLayout(header)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet(
            "QTextEdit { background-color: #FAFAFA; border: 1px solid #CCC; border-radius: 4px; }"
        )
        layout.addWidget(self.log_text)
        self.log_received.connect(self._append_log_slot)

    @pyqtSlot(str, str)
    def _append_log_slot(self, message: str, level: str) -> None:
        self._all_logs.append((message, level))
        if not self._should_show(level):
            return
        color = self.LOG_COLORS.get(level.upper(), "#000000")
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)
        self.log_text.insertHtml(
            f'<span style="color:{color};">{self._escape(message)}</span><br>'
        )
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def _escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )

    def _should_show(self, level: str) -> bool:
        if self._current_level == "全部":
            return True
        order = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        try:
            return order.index(level.upper()) >= order.index(self._current_level)
        except ValueError:
            return True

    def _on_level_changed(self, level: str) -> None:
        self._current_level = level
        self.log_text.clear()
        for message, lvl in self._all_logs:
            if self._should_show(lvl):
                color = self.LOG_COLORS.get(lvl.upper(), "#000000")
                self.log_text.insertHtml(
                    f'<span style="color:{color};">{self._escape(message)}</span><br>'
                )

    def append_log(self, message: str, level: str = "INFO") -> None:
        self.log_received.emit(message, level)

    def info(self, message: str) -> None:
        self.append_log(f"[{datetime.now():%H:%M:%S}] {message}", "INFO")

    def warning(self, message: str) -> None:
        self.append_log(f"[{datetime.now():%H:%M:%S}] {message}", "WARNING")

    def error(self, message: str) -> None:
        self.append_log(f"[{datetime.now():%H:%M:%S}] {message}", "ERROR")

    def success(self, message: str) -> None:
        self.append_log(f"[{datetime.now():%H:%M:%S}] {message}", "SUCCESS")

    def clear(self) -> None:
        self._all_logs.clear()
        self.log_text.clear()
