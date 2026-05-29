import sys
import traceback

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QAction
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QLineEdit,
    QLabel,
    QCheckBox,
    QFrame,
    QMessageBox,
    QSystemTrayIcon,
    QMenu,
    QStyle,
)

from safety import is_safe_user_command
from quick_actions import get_quick_action
from agent_client import plan_command
from tools import execute_tool_call
from voice import listen_ru


class CommandWorker(QThread):
    log = Signal(str, str)
    done = Signal()

    def __init__(self, command: str, auto_execute_model: bool):
        super().__init__()
        self.command = command
        self.auto_execute_model = auto_execute_model

    def run(self):
        try:
            command = self.command.strip()

            safe, reason = is_safe_user_command(command)
            if not safe:
                self.log.emit(f"Команда заблокирована: {reason}", "error")
                return

            quick_action = get_quick_action(command)

            if quick_action:
                self.log.emit("Найдено быстрое действие.", "info")
                self.log.emit(str(quick_action), "code")
                execute_tool_call(quick_action)
                self.log.emit("Быстрое действие выполнено.", "success")
                return

            self.log.emit("Команда отправлена планировщику Qwen.", "info")

            tool_call = plan_command(command)

            self.log.emit("План модели:", "info")
            self.log.emit(str(tool_call), "code")

            if tool_call.get("tool") == "refuse":
                self.log.emit(tool_call.get("reason", "Модель отказалась выполнять команду."), "error")
                return

            if not self.auto_execute_model:
                self.log.emit(
                    "Автовыполнение команд модели отключено. Действие только показано в логе.",
                    "warning"
                )
                return

            execute_tool_call(tool_call)
            self.log.emit("Инструмент выполнен.", "success")

        except Exception as e:
            self.log.emit(f"Ошибка: {e}", "error")
            self.log.emit(traceback.format_exc(), "code")
        finally:
            self.done.emit()


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


class LocalAssistantWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("LOCAL Помощник")
        self.setMinimumSize(980, 640)

        self.command_worker = None
        self.voice_worker = None

        self.build_ui()
        self.build_tray()
        self.apply_style()

    def build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 24, 24, 24)
        sidebar_layout.setSpacing(18)

        title = QLabel("LOCAL")
        title.setObjectName("appTitle")

        subtitle = QLabel("Локальный помощник ПК")
        subtitle.setObjectName("subtitle")

        self.status_label = QLabel("Статус: готов")
        self.status_label.setObjectName("statusLabel")

        self.auto_execute_model = QCheckBox("Автовыполнение команд модели")
        self.auto_execute_model.setChecked(True)

        self.always_on_top = QCheckBox("Поверх окон")
        self.always_on_top.stateChanged.connect(self.toggle_always_on_top)

        hint = QLabel(
            "Быстрые команды выполняются сразу.\n"
            "Остальные команды проходят через Qwen и инструменты системы."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)

        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(8)
        sidebar_layout.addWidget(self.status_label)
        sidebar_layout.addSpacing(10)
        sidebar_layout.addWidget(self.auto_execute_model)
        sidebar_layout.addWidget(self.always_on_top)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(hint)

        main = QFrame()
        main.setObjectName("main")

        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(28, 24, 28, 24)
        main_layout.setSpacing(16)

        header = QLabel("Управление компьютером")
        header.setObjectName("header")

        desc = QLabel("Введи команду или используй голосовой ввод. Без браузера, без uvicorn, без лишнего цирка.")
        desc.setObjectName("description")

        self.log = QTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)

        input_row = QHBoxLayout()
        input_row.setSpacing(12)

        self.command_input = QLineEdit()
        self.command_input.setObjectName("commandInput")
        self.command_input.setPlaceholderText("Например: открой проводник, закрой paint, сверни все окна")
        self.command_input.returnPressed.connect(self.run_text_command)

        self.run_button = QPushButton("Выполнить")
        self.run_button.setObjectName("primaryButton")
        self.run_button.clicked.connect(self.run_text_command)

        self.voice_button = QPushButton("Голос")
        self.voice_button.setObjectName("secondaryButton")
        self.voice_button.clicked.connect(self.run_voice_command)

        input_row.addWidget(self.command_input)
        input_row.addWidget(self.run_button)
        input_row.addWidget(self.voice_button)

        main_layout.addWidget(header)
        main_layout.addWidget(desc)
        main_layout.addWidget(self.log, 1)
        main_layout.addLayout(input_row)

        layout.addWidget(sidebar)
        layout.addWidget(main, 1)

        self.write_log("Интерфейс запущен.", "success")
        self.write_log("Аварийная остановка pyautogui: уведи мышь в левый верхний угол экрана.", "info")

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
            self.status_label.setText(f"Статус: {text or 'работаю'}")
        else:
            self.status_label.setText("Статус: готов")

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

        self.set_busy(True, "выполняю команду")

        self.command_worker = CommandWorker(
            command=command,
            auto_execute_model=self.auto_execute_model.isChecked()
        )

        self.command_worker.log.connect(self.write_log)
        self.command_worker.done.connect(lambda: self.set_busy(False))
        self.command_worker.start()

    def run_voice_command(self):
        if self.voice_worker and self.voice_worker.isRunning():
            self.write_log("Голосовой ввод уже активен.", "warning")
            return

        self.set_busy(True, "слушаю")

        self.voice_worker = VoiceWorker()
        self.voice_worker.log.connect(self.write_log)
        self.voice_worker.recognized.connect(self.on_voice_recognized)
        self.voice_worker.done.connect(lambda: self.set_busy(False))
        self.voice_worker.start()

    def on_voice_recognized(self, text: str):
        self.write_log(f"Распознано: {text}", "success")
        self.process_command(text)

    def write_log(self, text: str, kind: str = "info"):
        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        colors = {
            "info": "#c7ccd8",
            "success": "#b8e6c2",
            "warning": "#e8d99a",
            "error": "#f0a0a0",
            "user": "#b7d3ff",
            "code": "#d6d6d6",
        }

        color = colors.get(kind, "#c7ccd8")

        if kind == "code":
            html = (
                f'<pre style="color:{color}; background:#11141a; '
                f'border:1px solid #2e3440; border-radius:10px; '
                f'padding:10px; white-space:pre-wrap;">{escaped}</pre>'
            )
        else:
            html = (
                f'<div style="color:{color}; background:#1b2029; '
                f'border-radius:10px; padding:10px 12px; margin:6px 0;">'
                f'{escaped}</div>'
            )

        self.log.append(html)
        self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())

    def apply_style(self):
        self.setFont(QFont("Segoe UI", 10))

        self.setStyleSheet("""
            QMainWindow {
                background: #101217;
            }

            #sidebar {
                background: #151821;
                border-right: 1px solid #252b36;
            }

            #main {
                background: #101217;
            }

            #appTitle {
                color: #f0f2f5;
                font-size: 32px;
                font-weight: 800;
                letter-spacing: 4px;
            }

            #subtitle {
                color: #9aa3b2;
                font-size: 13px;
            }

            #statusLabel {
                color: #d4dae5;
                background: #202633;
                padding: 10px;
                border-radius: 10px;
            }

            #hint {
                color: #8f98a8;
                font-size: 12px;
                line-height: 1.35;
            }

            QCheckBox {
                color: #cdd3df;
                spacing: 8px;
            }

            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }

            #header {
                color: #f0f2f5;
                font-size: 26px;
                font-weight: 700;
            }

            #description {
                color: #9aa3b2;
                font-size: 13px;
            }

            #log {
                background: #131720;
                border: 1px solid #2a303d;
                border-radius: 16px;
                padding: 12px;
                color: #e3e7ee;
                selection-background-color: #3a4558;
            }

            #commandInput {
                background: #151a23;
                border: 1px solid #303848;
                color: #f0f2f5;
                border-radius: 12px;
                padding: 12px 14px;
                font-size: 14px;
            }

            #commandInput:focus {
                border: 1px solid #69758c;
            }

            QPushButton {
                border: none;
                border-radius: 12px;
                padding: 12px 18px;
                font-weight: 700;
            }

            #primaryButton {
                background: #e8ebf0;
                color: #101217;
            }

            #primaryButton:hover {
                background: #d9dde5;
            }

            #secondaryButton {
                background: #252c3a;
                color: #e8ebf0;
            }

            #secondaryButton:hover {
                background: #30394a;
            }

            QPushButton:disabled {
                background: #2a2f3a;
                color: #777f8f;
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