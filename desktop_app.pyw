import sys
import json
import traceback
from datetime import datetime

from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
)
from PySide6.QtGui import QFont, QAction, QPainter, QColor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QCheckBox,
    QFrame,
    QSystemTrayIcon,
    QMenu,
    QStyle,
    QScrollArea,
    QGraphicsOpacityEffect,
)

from safety import is_safe_user_command
from computer_use_agent import run_desktop_agent
from voice import listen_ru


class StatusDot(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(18, 18)
        self.color = QColor("#6ee7a8")
        self.pulse = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(45)

    def set_state(self, state: str):
        if state == "ready":
            self.color = QColor("#6ee7a8")
        elif state == "busy":
            self.color = QColor("#f3c969")
        elif state == "error":
            self.color = QColor("#f08a8a")
        elif state == "voice":
            self.color = QColor("#8ab4ff")
        self.update()

    def animate(self):
        self.pulse = (self.pulse + 1) % 40
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        alpha = 60 + int(abs(20 - self.pulse) * 4)
        glow = QColor(self.color)
        glow.setAlpha(alpha)

        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(1, 1, 16, 16)

        painter.setBrush(self.color)
        painter.drawEllipse(5, 5, 8, 8)


class CommandWorker(QThread):
    log = Signal(str, str)
    done = Signal(bool)

    def __init__(self, command: str, auto_execute_model: bool):
        super().__init__()
        self.command = command
        self.auto_execute_model = auto_execute_model

    def normalize_plan(self, plan: dict) -> dict:
        """
        Поддерживает и новый формат {steps:[...]}, и старый формат {tool:...},
        чтобы приложение не падало, если agent_client ещё не обновлён.
        """
        if not isinstance(plan, dict):
            return {
                "steps": [
                    {"tool": "refuse", "reason": "Планировщик вернул не объект JSON."}
                ]
            }

        if "steps" in plan and isinstance(plan["steps"], list):
            return plan

        if "tool" in plan:
            return {"steps": [plan]}

        return {
            "steps": [
                {"tool": "refuse", "reason": "Планировщик не вернул steps."}
            ]
        }

    def run(self):
        success = False

        try:
            command = self.command.strip()

            safe, reason = is_safe_user_command(command)
            if not safe:
                self.log.emit(f"Команда заблокирована: {reason}", "error")
                return

            self.log.emit("Команда передана desktop-агенту.", "info")

            success = run_desktop_agent(
                user_goal=command,
                log=lambda message, kind="info": self.log.emit(message, kind),
                max_steps=8
            )

            if success:
                self.log.emit("Задача агента выполнена.", "success")
            else:
                self.log.emit("Задача агента не выполнена.", "warning")
                
            self.log.emit("План выполнен.", "success")
            success = True

        except Exception as e:
            self.log.emit(f"Ошибка: {e}", "error")
            self.log.emit(traceback.format_exc(), "code")
        finally:
            self.done.emit(success)


class VoiceWorker(QThread):
    recognized = Signal(str)
    log = Signal(str, str)
    done = Signal()

    def run(self):
        try:
            self.log.emit("Слушаю голосовую команду.", "info")
            text = listen_ru()

            if not text:
                self.log.emit("Речь не распознана.", "warning")
                return

            if text.startswith("[Ошибка"):
                self.log.emit(text, "error")
                return

            self.recognized.emit(text)

        except Exception as e:
            self.log.emit(f"Ошибка голосового ввода: {e}", "error")
            self.log.emit(traceback.format_exc(), "code")
        finally:
            self.done.emit()


class LogCard(QFrame):
    def __init__(self, text: str, kind: str = "info"):
        super().__init__()

        self.kind = kind
        self.setObjectName("logCard")
        self.setProperty("kind", kind)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)

        kind_label = QLabel(self.kind_title(kind))
        kind_label.setObjectName("logKind")
        kind_label.setProperty("kind", kind)

        time_label = QLabel(datetime.now().strftime("%H:%M:%S"))
        time_label.setObjectName("logTime")

        top.addWidget(kind_label)
        top.addStretch()
        top.addWidget(time_label)

        body = QLabel(text)
        body.setObjectName("logText")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        if kind == "code":
            body.setObjectName("logCode")
            body.setText(text)

        layout.addLayout(top)
        layout.addWidget(body)

        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)

        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(180)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()

    @staticmethod
    def kind_title(kind: str) -> str:
        names = {
            "info": "Инфо",
            "success": "Готово",
            "warning": "Внимание",
            "error": "Ошибка",
            "user": "Команда",
            "code": "Данные",
        }
        return names.get(kind, "Инфо")


class LocalAssistantWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("LOCAL Помощник")
        self.setMinimumSize(1060, 700)

        self.command_worker = None
        self.voice_worker = None
        self.pending_voice_text = None
        self.last_success = True

        self.build_ui()
        self.build_tray()
        self.apply_style()

    def build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        page = QHBoxLayout(root)
        page.setContentsMargins(0, 0, 0, 0)
        page.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(300)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(26, 26, 26, 26)
        sidebar_layout.setSpacing(18)

        brand = QLabel("LOCAL")
        brand.setObjectName("brand")

        subtitle = QLabel("Десктопный помощник")
        subtitle.setObjectName("subtitle")

        status_box = QFrame()
        status_box.setObjectName("statusBox")

        status_layout = QHBoxLayout(status_box)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(10)

        self.status_dot = StatusDot()

        self.status_label = QLabel("Готов к работе")
        self.status_label.setObjectName("statusLabel")

        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.auto_execute_model = QCheckBox("Автовыполнение Qwen")
        self.auto_execute_model.setChecked(True)

        self.always_on_top = QCheckBox("Поверх окон")
        self.always_on_top.stateChanged.connect(self.toggle_always_on_top)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFixedHeight(1)

        section_title = QLabel("Режимы")
        section_title.setObjectName("sectionTitle")

        self.mode_text = QLabel(
            "Команды передаются планировщику Qwen.\n"
            "Qwen возвращает план из шагов, Python выполняет инструменты."
        )
        self.mode_text.setObjectName("sideText")
        self.mode_text.setWordWrap(True)

        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(6)
        sidebar_layout.addWidget(status_box)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(section_title)
        sidebar_layout.addWidget(self.auto_execute_model)
        sidebar_layout.addWidget(self.always_on_top)
        sidebar_layout.addWidget(divider)
        sidebar_layout.addWidget(self.mode_text)
        sidebar_layout.addStretch()

        main = QFrame()
        main.setObjectName("main")

        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(30, 26, 30, 26)
        main_layout.setSpacing(18)

        header_row = QHBoxLayout()
        header_row.setSpacing(16)

        header_text = QVBoxLayout()
        header_text.setSpacing(4)

        header = QLabel("Управление компьютером")
        header.setObjectName("header")

        desc = QLabel("Текстовая или голосовая команда. План строит Qwen, действия выполняют системные инструменты.")
        desc.setObjectName("description")

        header_text.addWidget(header)
        header_text.addWidget(desc)

        clear_btn = QPushButton("Очистить лог")
        clear_btn.setObjectName("ghostButton")
        clear_btn.clicked.connect(self.clear_log)

        header_row.addLayout(header_text)
        header_row.addStretch()
        header_row.addWidget(clear_btn)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("scroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.log_container = QWidget()
        self.log_container.setObjectName("logContainer")

        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setContentsMargins(12, 12, 12, 12)
        self.log_layout.setSpacing(10)
        self.log_layout.addStretch()

        self.scroll.setWidget(self.log_container)

        command_panel = QFrame()
        command_panel.setObjectName("commandPanel")

        command_layout = QHBoxLayout(command_panel)
        command_layout.setContentsMargins(14, 14, 14, 14)
        command_layout.setSpacing(12)

        self.command_input = QLineEdit()
        self.command_input.setObjectName("commandInput")
        self.command_input.setPlaceholderText("Например: напиши в блокнот привет мир, открой Paint, сохрани файл")
        self.command_input.returnPressed.connect(self.run_text_command)

        self.run_button = QPushButton("Выполнить")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.run_text_command)

        self.voice_button = QPushButton("Голос")
        self.voice_button.setObjectName("voiceButton")
        self.voice_button.clicked.connect(self.run_voice_command)

        command_layout.addWidget(self.command_input, 1)
        command_layout.addWidget(self.run_button)
        command_layout.addWidget(self.voice_button)

        main_layout.addLayout(header_row)
        main_layout.addWidget(self.scroll, 1)
        main_layout.addWidget(command_panel)

        page.addWidget(sidebar)
        page.addWidget(main, 1)

        self.voice_anim_timer = QTimer(self)
        self.voice_anim_timer.timeout.connect(self.animate_voice_button)
        self.voice_anim_step = 0

        self.write_log("Интерфейс запущен.", "success")
        self.write_log("Аварийная остановка pyautogui: мышь в левый верхний угол экрана.", "info")

    def build_tray(self):
        self.tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray.setIcon(icon)

        menu = QMenu()

        show_action = QAction("Открыть", self)
        show_action.triggered.connect(self.show_window)

        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(QApplication.quit)

        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.tray.showMessage(
            "LOCAL Помощник",
            "Приложение свернуто в трей.",
            QSystemTrayIcon.MessageIcon.Information,
            1800
        )

    def toggle_always_on_top(self):
        flags = self.windowFlags()

        if self.always_on_top.isChecked():
            self.setWindowFlags(flags | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowType.WindowStaysOnTopHint)

        self.show()

    def set_busy(self, busy: bool, text: str = ""):
        self.run_button.setDisabled(busy)
        self.voice_button.setDisabled(busy)
        self.command_input.setDisabled(busy)

        if busy:
            self.status_label.setText(text or "Выполняю")
            if "слуш" in text.lower():
                self.status_dot.set_state("voice")
            else:
                self.status_dot.set_state("busy")
        else:
            self.status_label.setText("Готов к работе")
            self.status_dot.set_state("ready")
            self.stop_voice_animation()

    def run_text_command(self):
        command = self.command_input.text().strip()

        if not command:
            return

        self.command_input.clear()
        self.process_command(command)

    def process_command(self, command: str):
        if self.command_worker and self.command_worker.isRunning():
            self.write_log("Предыдущая команда ещё выполняется.", "warning")
            return

        self.write_log(f"> {command}", "user")
        self.set_busy(True, "Выполняю команду")

        self.command_worker = CommandWorker(
            command=command,
            auto_execute_model=self.auto_execute_model.isChecked()
        )

        self.command_worker.log.connect(self.write_log)
        self.command_worker.done.connect(self.on_command_done)
        self.command_worker.start()

    def on_command_done(self, success: bool):
        self.set_busy(False)
        if not success:
            self.status_dot.set_state("error")
            self.status_label.setText("Ошибка выполнения")

    def run_voice_command(self):
        if self.voice_worker and self.voice_worker.isRunning():
            self.write_log("Голосовой ввод уже активен.", "warning")
            return

        self.pending_voice_text = None
        self.set_busy(True, "Слушаю")
        self.start_voice_animation()

        self.voice_worker = VoiceWorker()
        self.voice_worker.log.connect(self.write_log)
        self.voice_worker.recognized.connect(self.on_voice_recognized)
        self.voice_worker.done.connect(self.on_voice_done)
        self.voice_worker.start()

    def on_voice_recognized(self, text: str):
        self.pending_voice_text = text
        self.write_log(f"Распознано: {text}", "success")

    def on_voice_done(self):
        self.set_busy(False)

        if self.pending_voice_text:
            text = self.pending_voice_text
            self.pending_voice_text = None
            QTimer.singleShot(120, lambda: self.process_command(text))

    def start_voice_animation(self):
        self.voice_anim_step = 0
        self.voice_anim_timer.start(350)

    def stop_voice_animation(self):
        self.voice_anim_timer.stop()
        self.voice_button.setText("Голос")

    def animate_voice_button(self):
        states = ["Слушаю", "Слушаю.", "Слушаю..", "Слушаю..."]
        self.voice_button.setText(states[self.voice_anim_step % len(states)])
        self.voice_anim_step += 1

    def clear_log(self):
        while self.log_layout.count() > 1:
            item = self.log_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def write_log(self, text: str, kind: str = "info"):
        card = LogCard(text, kind)

        insert_index = max(0, self.log_layout.count() - 1)
        self.log_layout.insertWidget(insert_index, card)

        QTimer.singleShot(40, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def apply_style(self):
        self.setFont(QFont("Segoe UI", 10))

        self.setStyleSheet("""
            #root {
                background: #0c0f14;
            }

            #sidebar {
                background: #111620;
                border-right: 1px solid #252c38;
            }

            #brand {
                color: #f4f7fb;
                font-size: 36px;
                font-weight: 900;
                letter-spacing: 5px;
            }

            #subtitle {
                color: #8e99aa;
                font-size: 13px;
            }

            #sectionTitle {
                color: #f0f4fa;
                font-size: 14px;
                font-weight: 700;
                margin-top: 8px;
            }

            #sideText {
                color: #8d98a8;
                font-size: 12px;
                line-height: 1.45;
            }

            #divider {
                background: #252c38;
            }

            #statusBox {
                background: #171e2a;
                border: 1px solid #293242;
                border-radius: 16px;
            }

            #statusLabel {
                color: #dce4ef;
                font-size: 13px;
                font-weight: 600;
            }

            QCheckBox {
                color: #cbd4e2;
                spacing: 9px;
                font-size: 13px;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 5px;
                border: 1px solid #3a4558;
                background: #151b25;
            }

            QCheckBox::indicator:checked {
                background: #dce4ef;
                border: 1px solid #dce4ef;
            }

            #main {
                background: #0c0f14;
            }

            #header {
                color: #f4f7fb;
                font-size: 28px;
                font-weight: 800;
            }

            #description {
                color: #8792a3;
                font-size: 13px;
            }

            #scroll {
                background: transparent;
                border: none;
            }

            #logContainer {
                background: #0f131b;
                border: 1px solid #252c38;
                border-radius: 22px;
            }

            #logCard {
                background: #171d28;
                border: 1px solid #273142;
                border-radius: 16px;
            }

            #logCard[kind="success"] {
                border: 1px solid #2d6b4b;
                background: #13231c;
            }

            #logCard[kind="warning"] {
                border: 1px solid #6d5d2b;
                background: #262313;
            }

            #logCard[kind="error"] {
                border: 1px solid #743a3a;
                background: #261616;
            }

            #logCard[kind="user"] {
                border: 1px solid #315782;
                background: #142033;
            }

            #logCard[kind="code"] {
                border: 1px solid #303949;
                background: #11151d;
            }

            #logKind {
                color: #aeb8c8;
                font-size: 11px;
                font-weight: 800;
                text-transform: uppercase;
                letter-spacing: 1px;
            }

            #logKind[kind="success"] {
                color: #9ee6bb;
            }

            #logKind[kind="warning"] {
                color: #eadc92;
            }

            #logKind[kind="error"] {
                color: #f0a0a0;
            }

            #logKind[kind="user"] {
                color: #9cc8ff;
            }

            #logTime {
                color: #687386;
                font-size: 11px;
            }

            #logText {
                color: #dce4ef;
                font-size: 13px;
            }

            #logCode {
                color: #d5dbea;
                font-family: Consolas;
                font-size: 12px;
                background: #0c1017;
                border-radius: 10px;
                padding: 10px;
            }

            #commandPanel {
                background: #111620;
                border: 1px solid #283142;
                border-radius: 20px;
            }

            #commandInput {
                background: #0d1118;
                border: 1px solid #303a4d;
                color: #f3f6fb;
                border-radius: 14px;
                padding: 13px 15px;
                font-size: 14px;
            }

            #commandInput:focus {
                border: 1px solid #8ca3c7;
                background: #101724;
            }

            QPushButton {
                border: none;
                border-radius: 14px;
                padding: 13px 18px;
                font-weight: 800;
                font-size: 13px;
            }

            #primaryButton {
                background: #edf2f7;
                color: #0c0f14;
            }

            #primaryButton:hover {
                background: #dce5ef;
            }

            #voiceButton {
                background: #243149;
                color: #f3f6fb;
            }

            #voiceButton:hover {
                background: #30405e;
            }

            #ghostButton {
                background: #171d28;
                color: #cbd4e2;
                border: 1px solid #2c3546;
            }

            #ghostButton:hover {
                background: #202838;
            }

            QPushButton:disabled {
                background: #202734;
                color: #6f7a8b;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 10px;
                margin: 4px;
            }

            QScrollBar::handle:vertical {
                background: #30394a;
                border-radius: 5px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #465168;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    window = LocalAssistantWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    