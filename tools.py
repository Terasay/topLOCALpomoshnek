import time
import subprocess
import pyautogui
import pygetwindow as gw
import psutil
from rapidfuzz import fuzz


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


APP_ALIASES = {
    "проводник": "explorer",
    "explorer": "explorer",

    "блокнот": "notepad",
    "notepad": "notepad",

    "калькулятор": "calculator",
    "calculator": "calculator",
    "calc": "calculator",

    "paint": "paint",
    "паинт": "paint",
    "пейнт": "paint",

    "браузер": "chrome",
    "chrome": "chrome",
    "хром": "chrome",

    "edge": "edge",

    "диспетчер задач": "taskmgr",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",

    "настройки": "settings",
    "settings": "settings",
}


OPEN_COMMANDS = {
    "explorer": "explorer.exe",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "taskmgr": "taskmgr.exe",
    "settings": "ms-settings:",
}


PROCESS_HINTS = {
    "explorer": ["explorer.exe"],
    "notepad": ["notepad.exe"],
    "calculator": ["calculator.exe", "calc.exe"],
    "paint": ["mspaint.exe", "paint.exe"],
    "chrome": ["chrome.exe"],
    "edge": ["msedge.exe"],
    "taskmgr": ["taskmgr.exe"],
    "settings": ["SystemSettings.exe"],
}


def normalize_app_name(app_name: str) -> str:
    app = app_name.lower().strip()

    if app in APP_ALIASES:
        return APP_ALIASES[app]

    best_key = None
    best_score = 0

    for alias in APP_ALIASES:
        score = fuzz.ratio(app, alias)
        if score > best_score:
            best_score = score
            best_key = alias

    if best_score >= 70:
        return APP_ALIASES[best_key]

    return app


def open_app(app_name: str):
    app = normalize_app_name(app_name)
    target = OPEN_COMMANDS.get(app)

    if target:
        subprocess.Popen(target, shell=True)
        return

    # Универсальный fallback: открыть через Windows Search
    pyautogui.press("win")
    time.sleep(0.4)
    pyautogui.write(app_name)
    time.sleep(0.3)
    pyautogui.press("enter")


def close_app(app_name: str):
    app = normalize_app_name(app_name)

    closed = close_window_by_title(app_name)

    if closed:
        return

    killed = terminate_process_by_name(app)

    if killed:
        return

    raise ValueError(f"Не удалось найти окно или процесс для: {app_name}")


def close_window_by_title(query: str) -> bool:
    query = query.lower().strip()
    normalized_query = normalize_app_name(query)

    windows = gw.getAllWindows()

    best_window = None
    best_score = 0

    for window in windows:
        title = (window.title or "").lower().strip()

        if not title:
            continue

        score1 = fuzz.partial_ratio(query, title)
        score2 = fuzz.partial_ratio(normalized_query, title)
        score = max(score1, score2)

        if score > best_score:
            best_score = score
            best_window = window

    if best_window and best_score >= 55:
        best_window.close()
        return True

    return False


def terminate_process_by_name(app: str) -> bool:
    hints = PROCESS_HINTS.get(app, [])
    killed = False

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info["name"] or "").lower()

            if not name:
                continue

            if name in [h.lower() for h in hints]:
                proc.terminate()
                killed = True
                continue

            score = fuzz.partial_ratio(app, name)
            if score >= 80:
                proc.terminate()
                killed = True

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return killed


def focus_app(app_name: str):
    query = app_name.lower().strip()
    normalized_query = normalize_app_name(query)

    windows = gw.getAllWindows()

    best_window = None
    best_score = 0

    for window in windows:
        title = (window.title or "").lower().strip()

        if not title:
            continue

        score1 = fuzz.partial_ratio(query, title)
        score2 = fuzz.partial_ratio(normalized_query, title)
        score = max(score1, score2)

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
    pyautogui.write(text, interval=0.02)


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