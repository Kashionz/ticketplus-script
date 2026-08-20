"""主視窗。"""

from __future__ import annotations

import sys
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core.bot_engine import BotEngine, BotState, BotStatus
from ..models.ticket_config import TicketConfig
from ..utils.config import Config, get_config
from ..utils.helpers import detect_platform
from .log_widget import LogWidget
from .status_widget import StatusWidget

TEST_EVENT = "https://ticketplus.com.tw/activity/4b47b5360d42451f65704664c40b1c72"
TARGET_EVENT = "https://ticketplus.com.tw/activity/af39103d211724c82069c4ab5e40e95c"
MOCK_EVENT = "http://127.0.0.1:8765/activity/a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1"
KKTIX_ATARAYO = "https://kktix.com/events/sbgr01/registrations/new"
KKTIX_MOCK = "http://127.0.0.1:8765/events/mock-kktix/registrations/new"

_SESSION_PLACEHOLDER_TP = "例如 9/19；空白=第一個可購場次"
_SESSION_PLACEHOLDER_KKTIX = "KKTIX 不使用場次關鍵字"
_CODE_PLACEHOLDER_TP = "遠傳優先購序號，沒有就留空"
_CODE_PLACEHOLDER_KKTIX = "KKTIX 邀請碼，沒有就留空"
_ACCOUNT_PLACEHOLDER_TP = "09xxxxxxxx"
_ACCOUNT_PLACEHOLDER_KKTIX = "Email"
_WINDOWS_TIP_TP = (
    "1=只開目前這個 Chrome。2–3=開始搶票時再開獨立視窗，沿用現在的登入。"
    "遠大可能擋同一帳號多開；其中一個進付款就會關掉其他視窗。"
)
_WINDOWS_TIP_KKTIX = "KKTIX 不支援同時多視窗，固定為 1"


class BotWorker(QThread):
    status_changed = pyqtSignal(object)
    log_message = pyqtSignal(str, str)
    finished_ok = pyqtSignal(bool)

    def __init__(self, bot_engine: BotEngine):
        super().__init__()
        self.bot_engine = bot_engine
        self.bot_engine.add_status_callback(self.status_changed.emit)
        self.bot_engine.add_log_callback(self.log_message.emit)

    def run(self) -> None:
        self.bot_engine.start()
        while self.bot_engine.is_running:
            self.msleep(100)
        self.finished_ok.emit(self.bot_engine.state.status == BotStatus.SUCCESS)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._config: Optional[Config] = None
        self._bot_engine: Optional[BotEngine] = None
        self._worker: Optional[BotWorker] = None
        self._ui_editable = True
        self._saved_parallel_windows = 1
        self.setWindowTitle("購票助手")
        self.setMinimumSize(1100, 720)
        self.resize(1200, 800)
        self._init_ui()
        self._load_config()

    def _line(self, placeholder: str = "") -> QLineEdit:
        box = QLineEdit()
        box.setPlaceholderText(placeholder)
        box.setMinimumHeight(28)
        box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return box

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._left_panel())
        splitter.addWidget(self._right_panel())
        splitter.setSizes([440, 740])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, stretch=1)
        root.addWidget(self._buttons())
        self.activity_url_input.textChanged.connect(self._apply_platform_ui)

    def _left_panel(self) -> QWidget:
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        activity = QGroupBox("活動")
        form = QFormLayout(activity)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.activity_url_input = self._line("https://ticketplus.com.tw/activity/...")
        form.addRow("網址", self.activity_url_input)
        preset_box = QWidget()
        preset = QHBoxLayout(preset_box)
        preset.setContentsMargins(0, 0, 0, 0)
        test_btn = QPushButton("載入測試活動")
        test_btn.clicked.connect(self._load_test_event)
        target_btn = QPushButton("載入 INFINITE")
        target_btn.clicked.connect(self._load_target_event)
        mock_btn = QPushButton("載入模擬站")
        mock_btn.clicked.connect(self._load_mock_event)
        preset.addWidget(test_btn)
        preset.addWidget(target_btn)
        preset.addWidget(mock_btn)
        form.addRow("", preset_box)
        kktix_box = QWidget()
        kktix_row = QHBoxLayout(kktix_box)
        kktix_row.setContentsMargins(0, 0, 0, 0)
        atarayo_btn = QPushButton("載入 Atarayo")
        atarayo_btn.clicked.connect(self._load_atarayo)
        kktix_mock_btn = QPushButton("載入 KKTIX 模擬")
        kktix_mock_btn.clicked.connect(self._load_kktix_mock)
        kktix_row.addWidget(atarayo_btn)
        kktix_row.addWidget(kktix_mock_btn)
        kktix_row.addStretch(1)
        form.addRow("", kktix_box)
        self.target_session_input = self._line(_SESSION_PLACEHOLDER_TP)
        form.addRow("場次", self.target_session_input)
        self.quantity_spin = QSpinBox()
        self.quantity_spin.setRange(1, 4)
        self.quantity_spin.setValue(2)
        self.quantity_spin.setMinimumHeight(28)
        form.addRow("張數", self.quantity_spin)
        self.exact_qty_check = QCheckBox("一定要買到指定張數（剩餘不足就繼續刷）")
        self.exact_qty_check.setChecked(False)
        self.exact_qty_check.setToolTip(
            "不勾選：指定 2 張但票區只剩 1 張時，改買 1 張。\n"
            "勾選：剩餘少於指定張數就不買，持續更新票數。"
        )
        form.addRow("", self.exact_qty_check)
        self.exclusive_code_input = self._line(_CODE_PLACEHOLDER_TP)
        form.addRow("購票序號", self.exclusive_code_input)
        layout.addWidget(activity)

        account = QGroupBox("帳號（被登出才自動重登）")
        acc = QFormLayout(account)
        acc.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        acc.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.account_input = self._line(_ACCOUNT_PLACEHOLDER_TP)
        self.account_label = QLabel("手機")
        acc.addRow(self.account_label, self.account_input)
        self.password_input = self._line("已登入可留空")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        acc.addRow("密碼", self.password_input)
        layout.addWidget(account)

        area = QGroupBox("票區優先級（上到下；留空=第一個可購）")
        area_layout = QVBoxLayout(area)
        self.priority_list = QListWidget()
        self.priority_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.priority_list.setMinimumHeight(90)
        self.priority_list.setMaximumHeight(160)
        area_layout.addWidget(self.priority_list)
        self.new_priority_input = self._line("例如 特B3區")
        self.new_priority_input.returnPressed.connect(self._add_priority)
        area_layout.addWidget(self.new_priority_input)
        btn_row = QHBoxLayout()
        self.add_priority_btn = QPushButton("新增")
        self.add_priority_btn.clicked.connect(self._add_priority)
        self.remove_priority_btn = QPushButton("移除")
        self.remove_priority_btn.clicked.connect(self._remove_priority)
        self.move_up_btn = QPushButton("上移")
        self.move_up_btn.clicked.connect(self._move_priority_up)
        self.move_down_btn = QPushButton("下移")
        self.move_down_btn.clicked.connect(self._move_priority_down)
        btn_row.addWidget(self.add_priority_btn)
        btn_row.addWidget(self.remove_priority_btn)
        btn_row.addWidget(self.move_up_btn)
        btn_row.addWidget(self.move_down_btn)
        area_layout.addLayout(btn_row)
        self.fallback_first_check = QCheckBox("優先票區沒票時，改買畫面上第一個可購")
        self.fallback_first_check.setChecked(False)  # 預設持續刷優先票區
        self.fallback_first_check.setToolTip("不勾選則持續更新票數，直到優先票區有票")
        area_layout.addWidget(self.fallback_first_check)
        layout.addWidget(area)

        system = QGroupBox("執行")
        sys_form = QFormLayout(system)
        self.refresh_interval_spin = QSpinBox()
        self.refresh_interval_spin.setRange(200, 5000)
        self.refresh_interval_spin.setValue(500)
        self.refresh_interval_spin.setMinimumHeight(28)
        sys_form.addRow("刷新間隔 ms", self.refresh_interval_spin)
        self.auto_agree_check = QCheckBox("自動勾選同意條款")
        self.auto_agree_check.setChecked(True)
        sys_form.addRow("", self.auto_agree_check)
        self.headless_check = QCheckBox("隱藏瀏覽器視窗")
        sys_form.addRow("", self.headless_check)
        self.windows_spin = QSpinBox()
        self.windows_spin.setRange(1, 3)
        self.windows_spin.setValue(1)
        self.windows_spin.setMinimumHeight(28)
        self.windows_spin.setToolTip(_WINDOWS_TIP_TP)
        sys_form.addRow("同時視窗", self.windows_spin)
        layout.addWidget(system)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(380)
        scroll.setWidget(inner)
        return scroll

    def _right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.status_widget = StatusWidget()
        layout.addWidget(self.status_widget)
        self.log_widget = LogWidget()
        layout.addWidget(self.log_widget, stretch=1)
        return panel

    def _buttons(self) -> QWidget:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 8, 0, 0)
        self.inspect_btn = QPushButton("查看活動資料")
        self.inspect_btn.clicked.connect(self._on_inspect)
        row.addWidget(self.inspect_btn)
        self.launch_btn = QPushButton("啟動瀏覽器")
        self.launch_btn.setMinimumHeight(40)
        self.launch_btn.setStyleSheet(self._btn_css("#2196F3", "#1976D2"))
        self.launch_btn.clicked.connect(self._on_launch)
        row.addWidget(self.launch_btn)
        self.start_btn = QPushButton("開始搶票")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet(self._btn_css("#4CAF50", "#45a049"))
        self.start_btn.clicked.connect(self._on_start)
        row.addWidget(self.start_btn)
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(self._btn_css("#f44336", "#da190b"))
        self.stop_btn.clicked.connect(self._on_stop)
        row.addWidget(self.stop_btn)
        save_btn = QPushButton("儲存設定")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self._save_config)
        row.addWidget(save_btn)
        return box

    def _btn_css(self, color: str, hover: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color}; color: white; font-weight: bold;
                font-size: 14px; border-radius: 5px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:disabled {{ background-color: #CCCCCC; }}
        """

    def _load_test_event(self) -> None:
        self.activity_url_input.setText(TEST_EVENT)
        self.target_session_input.clear()
        self.quantity_spin.setValue(1)
        self.exclusive_code_input.clear()
        self.priority_list.clear()
        self.priority_list.addItem("全區")
        self.priority_list.addItem("預售票")
        self.log_widget.info("已載入測試活動 音田雅則（已開賣、全區）")

    def _load_target_event(self) -> None:
        self.activity_url_input.setText(TARGET_EVENT)
        self.target_session_input.setText("9/19")
        self.quantity_spin.setValue(2)
        self.priority_list.clear()
        self.priority_list.addItem("VIP3區")
        self.priority_list.addItem("VIP4區")
        self.log_widget.info("已載入 INFINITE：9/19、VIP3/VIP4。優先購請填序號。開賣與否改看購票頁票區欄位。")

    def _load_mock_event(self) -> None:
        self.activity_url_input.setText(MOCK_EVENT)
        self.target_session_input.setText("9/19")
        self.quantity_spin.setValue(2)
        self.exclusive_code_input.clear()
        self.priority_list.clear()
        self.priority_list.addItem("VIP3區")
        self.priority_list.addItem("VIP4區")
        self.log_widget.info("已載入本機模擬站。請先另開終端機執行：python -m mock.server")

    def _load_atarayo(self) -> None:
        self.activity_url_input.setText(KKTIX_ATARAYO)
        self.target_session_input.clear()
        self.quantity_spin.setValue(2)
        self.exclusive_code_input.clear()
        self.priority_list.clear()
        self.priority_list.addItem("3800")
        self.priority_list.addItem("3600")
        self.priority_list.addItem("3200")
        self.log_widget.info("已載入 Atarayo：張數 2、優先 3800/3600/3200。KKTIX 同時視窗固定 1。")

    def _load_kktix_mock(self) -> None:
        self.activity_url_input.setText(KKTIX_MOCK)
        self.target_session_input.clear()
        self.quantity_spin.setValue(2)
        self.exclusive_code_input.clear()
        self.priority_list.clear()
        self.priority_list.addItem("3800")
        self.priority_list.addItem("3600")
        self.priority_list.addItem("3200")
        self.log_widget.info("已載入 KKTIX 模擬站。請先另開終端機執行：python -m mock.server")

    def _parallel_windows_for_config(self) -> int:
        url = self.activity_url_input.text().strip()
        if detect_platform(url) == "kktix":
            return max(1, int(self._saved_parallel_windows or 1))
        return self.windows_spin.value()

    def _apply_platform_ui(self) -> None:
        url = self.activity_url_input.text().strip()
        was_locked = not self.windows_spin.isEnabled()
        if detect_platform(url) == "kktix":
            self.account_label.setText("Email")
            self.account_input.setPlaceholderText(_ACCOUNT_PLACEHOLDER_KKTIX)
            self.target_session_input.setPlaceholderText(_SESSION_PLACEHOLDER_KKTIX)
            self.exclusive_code_input.setPlaceholderText(_CODE_PLACEHOLDER_KKTIX)
            if not was_locked:
                self._saved_parallel_windows = max(1, self.windows_spin.value())
            self.windows_spin.setValue(1)
            self.windows_spin.setEnabled(False)
            self.windows_spin.setToolTip(_WINDOWS_TIP_KKTIX)
            return
        self.account_label.setText("手機")
        self.account_input.setPlaceholderText(_ACCOUNT_PLACEHOLDER_TP)
        self.target_session_input.setPlaceholderText(_SESSION_PLACEHOLDER_TP)
        self.exclusive_code_input.setPlaceholderText(_CODE_PLACEHOLDER_TP)
        self.windows_spin.setToolTip(_WINDOWS_TIP_TP)
        self.windows_spin.setEnabled(self._ui_editable)
        if was_locked and self._ui_editable:
            self.windows_spin.setValue(max(1, int(self._saved_parallel_windows or 1)))

    def _add_priority(self) -> None:
        text = self.new_priority_input.text().strip()
        if text:
            self.priority_list.addItem(text)
            self.new_priority_input.clear()

    def _remove_priority(self) -> None:
        row = self.priority_list.currentRow()
        if row >= 0:
            self.priority_list.takeItem(row)

    def _move_priority_up(self) -> None:
        row = self.priority_list.currentRow()
        if row <= 0:
            return
        item = self.priority_list.takeItem(row)
        self.priority_list.insertItem(row - 1, item)
        self.priority_list.setCurrentRow(row - 1)

    def _move_priority_down(self) -> None:
        row = self.priority_list.currentRow()
        if row < 0 or row >= self.priority_list.count() - 1:
            return
        item = self.priority_list.takeItem(row)
        self.priority_list.insertItem(row + 1, item)
        self.priority_list.setCurrentRow(row + 1)

    def _priorities(self) -> list:
        return [self.priority_list.item(i).text() for i in range(self.priority_list.count())]

    def _ticket_config(self) -> TicketConfig:
        return TicketConfig(
            activity_url=self.activity_url_input.text().strip(),
            target_session=self.target_session_input.text().strip(),
            quantity=self.quantity_spin.value(),
            area_priorities=self._priorities(),
            exclusive_code=self.exclusive_code_input.text().strip(),
            fallback_first_available=self.fallback_first_check.isChecked(),
            require_exact_quantity=self.exact_qty_check.isChecked(),
            account=self.account_input.text().strip(),
            password=self.password_input.text(),
            country_code="+886",
        )

    def _load_config(self) -> None:
        try:
            self._config = get_config()
            ticket = self._config.get_ticket_config()
            self.activity_url_input.setText(ticket.activity_url)
            self.target_session_input.setText(ticket.target_session)
            self.quantity_spin.setValue(ticket.quantity)
            self.exclusive_code_input.setText(ticket.exclusive_code)
            self.fallback_first_check.setChecked(ticket.fallback_first_available)
            self.exact_qty_check.setChecked(ticket.require_exact_quantity)
            self.account_input.setText(ticket.account)
            self.password_input.setText(ticket.password)
            self.priority_list.clear()
            for item in ticket.area_priorities:
                self.priority_list.addItem(item)
            self.refresh_interval_spin.setValue(self._config.bot_refresh_interval)
            self.auto_agree_check.setChecked(self._config.bot_auto_agree)
            self.headless_check.setChecked(self._config.browser_headless)
            self._saved_parallel_windows = max(1, int(self._config.bot_parallel_windows or 1))
            self.windows_spin.setValue(self._saved_parallel_windows)
            self._apply_platform_ui()
            self.log_widget.info("設定載入完成")
        except Exception as exc:
            self.log_widget.warning(f"載入設定失敗: {exc}")
            self._apply_platform_ui()

    def _save_config(self) -> None:
        try:
            if not self._config:
                self._config = get_config()
            self._config.set_ticket_config(self._ticket_config())
            self._config.set("bot.refresh_interval", self.refresh_interval_spin.value())
            self._config.set("bot.auto_agree", self.auto_agree_check.isChecked())
            self._config.set("bot.parallel_windows", self._parallel_windows_for_config())
            self._config.set("browser.headless", self.headless_check.isChecked())
            self._config.save()
            self.log_widget.success("設定已儲存")
        except Exception as exc:
            QMessageBox.warning(self, "錯誤", f"儲存失敗: {exc}")

    def _on_inspect(self) -> None:
        from ..api.event_api import fetch_event_catalog, format_catalog
        from ..utils.helpers import extract_event_id

        url = self.activity_url_input.text().strip()
        if detect_platform(url) == "kktix":
            from ..api.kktix_api import fetch_kktix_catalog

            try:
                text = fetch_kktix_catalog(url)
                self.log_widget.info(text)
                QMessageBox.information(self, "KKTIX 活動資料", text[:2000])
            except Exception as exc:
                QMessageBox.warning(self, "錯誤", f"讀取活動資料失敗: {exc}")
            return
        event_id = extract_event_id(url)
        if not event_id:
            QMessageBox.warning(self, "錯誤", "請先填入有效的活動網址")
            return
        try:
            catalog = fetch_event_catalog(event_id)
            text = format_catalog(catalog)
            self.log_widget.info(text)
            QMessageBox.information(self, catalog.title or "活動資料", text[:2000])
        except Exception as exc:
            QMessageBox.warning(self, "錯誤", f"讀取活動資料失敗: {exc}")

    def _shutdown_engine(self, close_browser: bool = True) -> None:
        worker = self._worker
        engine = self._bot_engine
        self._worker = None
        if worker:
            for signal, slot in (
                (worker.status_changed, self._on_status),
                (worker.log_message, self._on_log),
                (worker.finished_ok, self._on_finished),
            ):
                try:
                    signal.disconnect(slot)
                except TypeError:
                    pass
        if engine:
            engine.stop(close_browser=close_browser)
        if worker:
            worker.wait(4000)
        if close_browser:
            self._bot_engine = None

    def _on_launch(self) -> None:
        config = self._ticket_config()
        errors = config.validate()
        if errors:
            QMessageBox.warning(self, "設定錯誤", "\n".join(errors))
            return
        self.log_widget.info("啟動瀏覽器...")
        self._set_ui("launching")
        try:
            self._shutdown_engine(close_browser=True)
            cfg = self._config or get_config()
            self._bot_engine = BotEngine(
                config=config,
                browser_headless=self.headless_check.isChecked(),
                refresh_interval=self.refresh_interval_spin.value(),
                auto_agree=self.auto_agree_check.isChecked(),
                wait_for_human=cfg.bot_wait_for_human,
                driver_path=cfg.browser_driver_path,
                user_data_dir=cfg.browser_user_data_dir,
                window_size=cfg.browser_window_size,
                page_load_timeout=cfg.browser_page_load_timeout,
                debugger_address=cfg.browser_debugger_address,
                chrome_binary=cfg.browser_chrome_binary,
                prefer_windows_chrome=cfg.browser_prefer_windows_chrome,
                parallel_windows=self.windows_spin.value(),
            )
            self._worker = BotWorker(self._bot_engine)
            self._worker.status_changed.connect(self._on_status)
            self._worker.log_message.connect(self._on_log)
            self._worker.finished_ok.connect(self._on_finished)
            self._worker.start()
        except Exception as exc:
            self.log_widget.error(f"啟動失敗: {exc}")
            self._set_ui("idle")

    def _apply_ui_settings(self) -> bool:
        config = self._ticket_config()
        errors = config.validate()
        if errors:
            QMessageBox.warning(self, "設定錯誤", "\n".join(errors))
            return False
        if not self._bot_engine:
            return False
        self._bot_engine.apply_settings(
            config,
            refresh_interval=self.refresh_interval_spin.value(),
            auto_agree=self.auto_agree_check.isChecked(),
            parallel_windows=self.windows_spin.value(),
        )
        return True

    def _on_start(self) -> None:
        if not self._bot_engine or not self._bot_engine.has_browser:
            self.log_widget.warning("瀏覽器已關閉，請重新按「啟動瀏覽器」")
            self._shutdown_engine(close_browser=True)
            self._set_ui("idle")
            return
        if not self._apply_ui_settings():
            return
        if self._bot_engine.is_waiting_for_start() and self._bot_engine.is_running:
            self._bot_engine.trigger_start_booking()
        elif not self._bot_engine.start_booking():
            if not self._bot_engine.has_browser:
                self._set_ui("idle")
            return
        self._set_ui("running")

    def _on_stop(self) -> None:
        if self._bot_engine:
            self._bot_engine.stop(close_browser=False)
        self._set_ui("waiting" if self._bot_engine and self._bot_engine.has_browser else "idle")

    def _set_ui(self, mode: str) -> None:
        browser_ok = bool(self._bot_engine and self._bot_engine.has_browser)
        if mode in {"waiting", "running"} and not browser_ok:
            mode = "idle"
        self.launch_btn.setEnabled(mode in {"idle", "waiting"})
        self.start_btn.setEnabled(mode == "waiting" and browser_ok)
        self.stop_btn.setEnabled(mode in {"launching", "running", "waiting"})
        editable = mode in {"idle", "waiting"}
        self.activity_url_input.setEnabled(editable)
        self.target_session_input.setEnabled(editable)
        self.quantity_spin.setEnabled(editable)
        self.exact_qty_check.setEnabled(editable)
        self.exclusive_code_input.setEnabled(editable)
        self.account_input.setEnabled(editable)
        self.password_input.setEnabled(editable)
        self.priority_list.setEnabled(editable)
        self.new_priority_input.setEnabled(editable)
        self.add_priority_btn.setEnabled(editable)
        self.remove_priority_btn.setEnabled(editable)
        self.move_up_btn.setEnabled(editable)
        self.move_down_btn.setEnabled(editable)
        self.fallback_first_check.setEnabled(editable)
        self.refresh_interval_spin.setEnabled(editable)
        self.auto_agree_check.setEnabled(editable)
        self._ui_editable = editable
        self.windows_spin.setEnabled(editable)
        self._apply_platform_ui()

    @pyqtSlot(object)
    def _on_status(self, state: BotState) -> None:
        self.status_widget.update_state(state)
        if state.status == BotStatus.WAITING_LOGIN:
            self._set_ui("waiting")
        elif state.status == BotStatus.RUNNING:
            self._set_ui("running")
        elif state.status in {BotStatus.STOPPED, BotStatus.FAILED, BotStatus.ERROR, BotStatus.SUCCESS}:
            if self._bot_engine and self._bot_engine.has_browser:
                self._set_ui("waiting")
            else:
                self._set_ui("idle")

    @pyqtSlot(str, str)
    def _on_log(self, message: str, level: str) -> None:
        self.log_widget.append_log(message, level)

    @pyqtSlot(bool)
    def _on_finished(self, success: bool) -> None:
        if self._bot_engine and self._bot_engine.has_browser:
            self._set_ui("waiting")
        else:
            self._set_ui("idle")
        if success:
            self.log_widget.success("已進入確認 / 付款頁，請完成付款")
            QMessageBox.information(self, "完成", "已進入付款頁，請在瀏覽器完成付款。")

    def closeEvent(self, event) -> None:
        if self._bot_engine and self._bot_engine.is_running:
            reply = QMessageBox.question(
                self,
                "確認",
                "流程還在執行，確定關閉？關閉視窗才會關掉瀏覽器。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        self._shutdown_engine(close_browser=True)
        event.accept()


def run_app() -> None:
    from ..utils.logger import init_default_logger

    init_default_logger(level="INFO", log_file="logs/bot.log", console_output=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
