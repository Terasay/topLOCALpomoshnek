import time
import subprocess
import pyautogui
import pygetwindow as gw


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


SAFE_APPS = {
    "explorer": "explorer.exe",
    "проводник": "explorer.exe",

    "notepad": "notepad.exe",
    "блокнот": "notepad.exe",

    "calculator": "calc.exe",
    "калькулятор": "calc.exe",

    "paint": "mspaint.exe",
    "пейнт": "mspaint.exe",

    "chrome": "chrome.exe",
    "браузер": "chrome.exe",

    "edge": "msedge.exe",

    "settings": "ms-settings:",
    "настройки": "ms-settings:",
}


def open_app(app_name: str):
    app = app_name.lower().strip()
    target = SAFE_APPS.get(app)

    if not target:
        raise ValueError(f"Приложение не разрешено или неизвестно: {app_name}")

    subprocess.Popen(target, shell=True)

def close_app(app_name: str):
    app = app_name.lower().strip()

    possible_titles = {
        "explorer": ["Проводник", "Explorer"],
        "проводник": ["Проводник", "Explorer"],

        "notepad": ["Блокнот", "Notepad"],
        "блокнот": ["Блокнот", "Notepad"],

        "calculator": ["Калькулятор", "Calculator"],
        "калькулятор": ["Калькулятор", "Calculator"],

        "chrome": ["Chrome"],
        "edge": ["Edge"]
    }

    titles = possible_titles.get(app)

    if not titles:
        raise ValueError(f"Неизвестное приложение: {app_name}")

    windows = gw.getAllWindows()

    found = False

    for window in windows:
        for title in titles:
            if title.lower() in window.title.lower():
                try:
                    window.close()
                    found = True
                except Exception:
                    pass

    if not found:
        raise ValueError(f"Окно приложения не найдено: {app_name}")
    
def focus_app(app_name: str):
    app = app_name.lower().strip()

    possible_titles = {
        "explorer": ["Проводник", "Explorer"],
        "notepad": ["Блокнот", "Notepad"],
        "calculator": ["Калькулятор", "Calculator"],
        "chrome": ["Chrome"],
    }

    titles = possible_titles.get(app)

    if not titles:
        raise ValueError(f"Неизвестное приложение: {app_name}")

    windows = gw.getAllWindows()

    for window in windows:
        for title in titles:
            if title.lower() in window.title.lower():
                window.activate()
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
    
    if tool == "close_app":
        return close_app(call["app"])

    if tool == "focus_app":
        return focus_app(call["app"])

    raise ValueError(f"Неизвестный tool: {tool}")