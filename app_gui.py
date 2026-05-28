import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox

from screen import take_screenshot
from ollama_client import ask_ollama
from safety import is_safe_user_command, validate_action
from controller import execute_action
from quick_actions import get_quick_action


USE_SCREENSHOT = False
REQUIRE_CONFIRMATION = True


class AssistantGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("LOCAL Помощник")
        self.root.geometry("760x520")

        self.title = tk.Label(
            root,
            text="LOCAL Помощник",
            font=("Segoe UI", 18, "bold")
        )
        self.title.pack(pady=10)

        self.log = scrolledtext.ScrolledText(
            root,
            height=20,
            font=("Consolas", 10)
        )
        self.log.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)

        bottom = tk.Frame(root)
        bottom.pack(fill=tk.X, padx=12, pady=10)

        self.entry = tk.Entry(bottom, font=("Segoe UI", 12))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", lambda event: self.run_command())

        self.send_btn = tk.Button(
            bottom,
            text="Выполнить",
            command=self.run_command,
            width=14
        )
        self.send_btn.pack(side=tk.LEFT, padx=8)

        self.screen_var = tk.BooleanVar(value=USE_SCREENSHOT)
        self.screen_check = tk.Checkbutton(
            root,
            text="Отправлять скриншот в Qwen",
            variable=self.screen_var
        )
        self.screen_check.pack(anchor="w", padx=14)

        self.write_log("Готово. Введи команду.")
        self.write_log("Быстрые команды: Пуск, сверни все, закрой окно, скопируй, вставь.")

    def write_log(self, text):
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def run_command(self):
        command = self.entry.get().strip()
        if not command:
            return

        self.entry.delete(0, tk.END)
        self.write_log(f"\n> {command}")

        thread = threading.Thread(target=self.process_command, args=(command,), daemon=True)
        thread.start()

    def process_command(self, command):
        safe, reason = is_safe_user_command(command)
        if not safe:
            self.write_log(f"Блокировано: {reason}")
            return

        quick_action = get_quick_action(command)

        if quick_action:
            self.write_log(f"Быстрое действие: {quick_action}")
            action = quick_action
        else:
            screenshot_path = None

            if self.screen_var.get():
                screenshot_path = take_screenshot()
                self.write_log("Скриншот сделан.")

            self.write_log("Отправляю в Qwen...")
            action = ask_ollama(command, screenshot_path)

        self.write_log(f"Действие: {action}")

        valid, reason = validate_action(action)
        if not valid:
            self.write_log(f"Не выполнено: {reason}")
            return

        if REQUIRE_CONFIRMATION:
            answer = messagebox.askyesno("Подтверждение", f"Выполнить?\n\n{action}")
            if not answer:
                self.write_log("Отменено.")
                return

        try:
            execute_action(action)
            self.write_log("Готово.")
        except Exception as e:
            self.write_log(f"Ошибка выполнения: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = AssistantGUI(root)
    root.mainloop()