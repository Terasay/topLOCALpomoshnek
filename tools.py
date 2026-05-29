import os
import time
import shutil
import subprocess
import pyautogui
import pygetwindow as gw
import psutil
import pyperclip
from rapidfuzz import fuzz


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.12


APP_ALIASES = {
    "проводник": "explorer",
    "explorer": "explorer",
    "file explorer": "explorer",
    "store": "store",
    "microsoft store": "store",
    "магазин": "store",
    "магазин microsoft": "store",

    "блокнот": "notepad",
    "notepad": "notepad",

    "калькулятор": "calculator",
    "calculator": "calculator",
    "calc": "calculator",

    "paint": "paint",
    "pa": "paint",
    "паинт": "paint",
    "пейнт": "paint",
    "mspaint": "paint",

    "chrome": "chrome",
    "google chrome": "chrome",
    "хром": "chrome",
    "браузер": "chrome",

    "edge": "edge",
    "microsoft edge": "edge",
    "эдж": "edge",

    "taskmgr": "taskmgr",
    "диспетчер задач": "taskmgr",
    "task manager": "taskmgr",

    "settings": "settings",
    "настройки": "settings",
}


OPEN_COMMANDS = {
    "explorer": "explorer.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "chrome": "chrome.exe",
    "edge": "microsoft-edge:",
    "taskmgr": "taskmgr.exe",
    "settings": "ms-settings:",
    "store": "ms-windows-store:",
}


PROCESS_HINTS = {
    # explorer.exe специально не убиваем, иначе можно снести оболочку Windows.
    "notepad": ["notepad.exe"],
    "calculator": ["calculator.exe", "calc.exe"],
    "paint": ["mspaint.exe", "paint.exe"],
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "taskmgr": ["taskmgr.exe"],
    "settings": ["SystemSettings.exe"],
}


BLOCKED_KILL_PROCESSES = {
    "system",
    "registry",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "dwm.exe",
    "explorer.exe",
    "python.exe",
    "pythonw.exe",
}


def normalize_app_name(app_name: str) -> str:
    app = app_name.lower().strip()

    if app in APP_ALIASES:
        return APP_ALIASES[app]

    best_key = None
    best_score = 0

    for alias in APP_ALIASES:
        score = fuzz.partial_ratio(app, alias)

        if score > best_score:
            best_score = score
            best_key = alias

    if best_key and best_score >= 75:
        return APP_ALIASES[best_key]

    return app


def find_exe_in_common_paths(exe_name: str) -> str | None:
    found = shutil.which(exe_name)

    if found:
        return found

    roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
    ]

    possible_subpaths = [
        os.path.join("Microsoft", "Edge", "Application"),
        os.path.join("Google", "Chrome", "Application"),
    ]

    for root in roots:
        if not root:
            continue

        for sub in possible_subpaths:
            candidate = os.path.join(root, sub, exe_name)
            if os.path.exists(candidate):
                return candidate

    return None


def launch_by_search(app_name: str):
    old_clipboard = ""

    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    pyautogui.press("win")
    time.sleep(0.35)

    # Вставка через буфер обмена не зависит от русской/английской раскладки.
    pyperclip.copy(app_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.35)
    pyautogui.press("enter")

    try:
        pyperclip.copy(old_clipboard)
    except Exception:
        pass


def open_app(app_name: str):
    app = normalize_app_name(app_name)
    command = OPEN_COMMANDS.get(app)

    if command:
        if command.endswith(":"):
            os.startfile(command)
            return

        exe_path = find_exe_in_common_paths(command)

        if exe_path:
            subprocess.Popen([exe_path])
            return

        try:
            subprocess.Popen(command, shell=True)
            return
        except Exception:
            pass

    # Последний fallback: Windows Search.
    launch_by_search(app_name)


def close_window_by_title(query: str) -> bool:
    query = query.lower().strip()
    normalized = normalize_app_name(query)

    windows = gw.getAllWindows()

    best_window = None
    best_score = 0

    for window in windows:
        title = (window.title or "").lower().strip()

        if not title:
            continue

        score = max(
            fuzz.partial_ratio(query, title),
            fuzz.partial_ratio(normalized, title)
        )

        if score > best_score:
            best_score = score
            best_window = window

    if best_window and best_score >= 55:
        best_window.close()
        return True

    return False


def terminate_process_by_name(app_name: str) -> bool:
    app = normalize_app_name(app_name)
    hints = PROCESS_HINTS.get(app, [])

    killed = False

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info["name"] or "").lower()

            if not name:
                continue

            if name in BLOCKED_KILL_PROCESSES:
                continue

            if name in [h.lower() for h in hints]:
                proc.terminate()
                killed = True
                continue

            # Для неизвестных приложений fuzzy-убийство делаем осторожно.
            score = fuzz.partial_ratio(app, name)

            if score >= 90:
                proc.terminate()
                killed = True

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return killed


def close_app(app_name: str):
    if close_window_by_title(app_name):
        return

    if terminate_process_by_name(app_name):
        return

    raise ValueError(f"Не удалось найти окно или процесс для: {app_name}")


def focus_app(app_name: str):
    query = app_name.lower().strip()
    normalized = normalize_app_name(query)

    windows = gw.getAllWindows()

    best_window = None
    best_score = 0

    for window in windows:
        title = (window.title or "").lower().strip()

        if not title:
            continue

        score = max(
            fuzz.partial_ratio(query, title),
            fuzz.partial_ratio(normalized, title)
        )

        if score > best_score:
            best_score = score
            best_window = window

    if best_window and best_score >= 55:
        best_window.activate()
        return

    raise ValueError(f"Окно не найдено: {app_name}")


def press_hotkey(keys: list[str]):
    pyautogui.hotkey(*keys)


def press_key(key: str):
    pyautogui.press(key)


def type_text(text: str):
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")


def click_position(x: int, y: int, button: str = "left"):
    pyautogui.click(x=x, y=y, button=button)


def wait(seconds: float = 1):
    time.sleep(seconds)


def execute_tool_call(call: dict):
    tool = call.get("tool")

    if tool == "open_app":
        return open_app(call["app"])

    if tool == "close_app":
        return close_app(call["app"])

    if tool == "focus_app":
        return focus_app(call["app"])

    if tool == "press_hotkey":
        return press_hotkey(call["keys"])

    if tool == "press_key":
        return press_key(call["key"])

    if tool == "type_text":
        return type_text(call["text"])

    if tool == "click_position":
        return click_position(
            int(call["x"]),
            int(call["y"]),
            call.get("button", "left")
        )

    if tool == "wait":
        return wait(float(call.get("seconds", 1)))

    if tool == "refuse":
        raise ValueError(call.get("reason", "Модель отказалась"))

    raise ValueError(f"Неизвестный tool: {tool}")