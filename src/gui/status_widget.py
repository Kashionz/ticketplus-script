"""狀態顯示。"""

from typing import Optional

from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from ..core.bot_engine import BotState, BotStatus


class StatusWidget(QWidget):
    STATUS_TEXT = {
        BotStatus.IDLE: "待命中",
        BotStatus.STARTING: "啟動中",
        BotStatus.WAITING_LOGIN: "等待登入",
        BotStatus.RUNNING: "執行中",
        BotStatus.PAUSED: "已暫停",
        BotStatus.STOPPING: "停止中",
        BotStatus.STOPPED: "已停止",
        BotStatus.SUCCESS: "已進入付款",
        BotStatus.FAILED: "未完成",
        BotStatus.ERROR: "發生錯誤",
    }
    STATUS_COLORS = {
        BotStatus.IDLE: "#808080",
        BotStatus.STARTING: "#FFA500",
        BotStatus.WAITING_LOGIN: "#FF8C00",
        BotStatus.RUNNING: "#1E90FF",
        BotStatus.PAUSED: "#FFD700",
        BotStatus.STOPPING: "#FFA500",
        BotStatus.STOPPED: "#808080",
        BotStatus.SUCCESS: "#228B22",
        BotStatus.FAILED: "#FF0000",
        BotStatus.ERROR: "#8B0000",
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("狀態監控")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        frame = QFrame()
        grid = QGridLayout(frame)
        grid.addWidget(QLabel("狀態:"), 0, 0)
        self.status_label = QLabel("待命中")
        grid.addWidget(self.status_label, 0, 1)
        grid.addWidget(QLabel("步驟:"), 1, 0)
        self.step_label = QLabel("-")
        grid.addWidget(self.step_label, 1, 1)
        grid.addWidget(QLabel("重試:"), 2, 0)
        self.retry_label = QLabel("0")
        grid.addWidget(self.retry_label, 2, 1)
        grid.addWidget(QLabel("訊息:"), 3, 0)
        self.message_label = QLabel("-")
        self.message_label.setWordWrap(True)
        grid.addWidget(self.message_label, 3, 1)
        layout.addWidget(frame)

    def update_state(self, state: BotState) -> None:
        text = self.STATUS_TEXT.get(state.status, state.status.name)
        color = self.STATUS_COLORS.get(state.status, "#000000")
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.step_label.setText(state.step.value)
        self.retry_label.setText(str(state.retry_count))
        self.message_label.setText(state.message or "-")
