import time
import pyautogui


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


SAFE_APPS = {
    "explorer": "explorer",
    "проводник": "explorer",
    "notepad": "notepad",
    "блокнот": "notepad",
    "calculator": "calc",
    "калькулятор": "calc",
    "chrome": "chrome",
    "браузер": "chrome",
    "edge": "msedge",
    "paint": "mspaint",
    "пейнт": "mspaint",
    "settings": "ms-settings:",
    "настройки": "ms-settings:",
}


def open_app(app_name: str):
    app = app_name.lower().strip()
    target = SAFE_APPS.get(app)

    if not target:
        raise ValueError(f"Приложение не разрешено или неизвестно: {app_name}")

    pyautogui.hotkey("win", "r")
    time.sleep(0.2)
    pyautogui.write(target)
    pyautogui.press("enter")


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

    raise ValueError(f"Неизвестный tool: {tool}")