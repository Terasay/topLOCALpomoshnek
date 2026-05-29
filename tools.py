import os
import json
import time
import shutil
import subprocess

import psutil
import pyautogui
import pyperclip
from rapidfuzz import fuzz

try:
    import win32gui
    import win32con
    import win32process
except ImportError:
    win32gui = None
    win32con = None
    win32process = None


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.12


APP_ALIASES = {
    "проводник": "explorer",
    "explorer": "explorer",
    "file explorer": "explorer",

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

    "store": "store",
    "microsoft store": "store",
    "магазин": "store",
    "магазин microsoft": "store",

    "copilot": "copilot",
    "копилот": "copilot",

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
    "store": "ms-windows-store:",
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
    "store": ["WinStore.App.exe", "ApplicationFrameHost.exe"],
    "taskmgr": ["taskmgr.exe"],
    "settings": ["SystemSettings.exe"],
}


TITLE_HINTS = {
    "explorer": ["проводник", "explorer"],
    "notepad": ["блокнот", "notepad"],
    "calculator": ["калькулятор", "calculator"],
    "paint": ["paint", "пейнт"],
    "chrome": ["chrome"],
    "edge": ["edge"],
    "store": ["microsoft store", "store", "магазин"],
    "taskmgr": ["диспетчер задач", "task manager"],
    "settings": ["settings", "параметры", "настройки"],
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


START_APPS_CACHE = None


def normalize_app_name(app_name: str) -> str:
    app = str(app_name).lower().strip()

    if app in APP_ALIASES:
        return APP_ALIASES[app]

    for alias, canonical in APP_ALIASES.items():
        if alias in app:
            return canonical

    return app


def get_visible_windows() -> list[dict]:
    result = []

    if not win32gui or not win32process:
        return result

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd).strip()

        if not title:
            return

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = psutil.Process(pid).name()
        except Exception:
            pid = None
            proc_name = ""

        result.append({
            "hwnd": hwnd,
            "title": title,
            "pid": pid,
            "process": proc_name,
        })

    win32gui.EnumWindows(callback, None)
    return result


def focus_hwnd(hwnd: int):
    if not win32gui or not win32con:
        return

    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.1)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def close_hwnd(hwnd: int):
    if not win32gui or not win32con:
        return

    try:
        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    except Exception:
        pass


def find_window_for_app(app_name: str) -> dict | None:
    app = normalize_app_name(app_name)
    windows = get_visible_windows()

    process_hints = [x.lower() for x in PROCESS_HINTS.get(app, [])]
    title_hints = [x.lower() for x in TITLE_HINTS.get(app, [])]

    # 1. Сначала ищем по процессу. Это точнее, чем title.
    for window in windows:
        proc = window["process"].lower()

        if proc in process_hints:
            return window

    # 2. Потом ищем по заголовку.
    best_window = None
    best_score = 0

    for window in windows:
        title = window["title"].lower()

        scores = []

        for hint in title_hints:
            scores.append(fuzz.partial_ratio(hint, title))

        scores.append(fuzz.partial_ratio(str(app_name).lower(), title))
        scores.append(fuzz.partial_ratio(app, title))

        score = max(scores)

        if score > best_score:
            best_score = score
            best_window = window

    if best_window and best_score >= 60:
        return best_window

    return None


def focus_app(app_name: str):
    window = find_window_for_app(app_name)

    if not window:
        raise ValueError(f"Окно не найдено: {app_name}")

    focus_hwnd(window["hwnd"])


def find_exe_in_common_paths(exe_name: str) -> str | None:
    found = shutil.which(exe_name)

    if found:
        return found

    roots = [
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("WINDIR"),
    ]

    possible_subpaths = [
        "",
        "System32",
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


def get_start_apps() -> list[dict]:
    global START_APPS_CACHE

    if START_APPS_CACHE is not None:
        return START_APPS_CACHE

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        if result.returncode != 0 or not result.stdout.strip():
            START_APPS_CACHE = []
            return START_APPS_CACHE

        data = json.loads(result.stdout)

        if isinstance(data, dict):
            data = [data]

        START_APPS_CACHE = data
        return START_APPS_CACHE

    except Exception:
        START_APPS_CACHE = []
        return START_APPS_CACHE


def find_start_app(query: str) -> dict | None:
    query = str(query).lower().strip()
    apps = get_start_apps()

    best_app = None
    best_score = 0

    for app in apps:
        name = str(app.get("Name", "")).lower().strip()
        app_id = str(app.get("AppID", "")).strip()

        if not name or not app_id:
            continue

        if query == name:
            return app

        if query in name:
            return app

        score = fuzz.partial_ratio(query, name)

        if score > best_score:
            best_score = score
            best_app = app

    if best_app and best_score >= 72:
        return best_app

    return None


def launch_start_app(app_name: str) -> bool:
    app = find_start_app(app_name)

    if not app:
        return False

    app_id = app.get("AppID")

    if not app_id:
        return False

    subprocess.Popen(
        ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    return True


def launch_by_search(app_name: str):
    old_clipboard = ""

    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    pyautogui.hotkey("win", "s")
    time.sleep(0.7)

    pyperclip.copy(app_name)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.8)

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
            subprocess.Popen(
                [exe_path],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return

        try:
            subprocess.Popen(
                command,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return
        except Exception:
            pass

    # UWP / Store / Copilot / прочие приложения из Пуска
    if launch_start_app(app_name):
        return

    if launch_start_app(app):
        return

    # Последний fallback
    launch_by_search(app_name)


def wait_for_app_window(app_name: str, timeout: float = 5.0) -> bool:
    start = time.time()

    while time.time() - start < timeout:
        window = find_window_for_app(app_name)

        if window:
            focus_hwnd(window["hwnd"])
            return True

        time.sleep(0.25)

    return False


def open_or_focus_app(app_name: str):
    # Если уже открыто, просто фокусируем.
    try:
        focus_app(app_name)
        time.sleep(0.25)
        return
    except Exception:
        pass

    open_app(app_name)

    # После открытия обязательно ждём окно и фокусируем.
    wait_for_app_window(app_name, timeout=6.0)

    time.sleep(0.25)


def close_app(app_name: str):
    app = normalize_app_name(app_name)

    window = find_window_for_app(app)

    if window:
        close_hwnd(window["hwnd"])
        return

    if terminate_process_by_name(app):
        return

    raise ValueError(f"Не удалось найти окно или процесс для: {app_name}")


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

            score = fuzz.partial_ratio(app, name)

            if score >= 92:
                proc.terminate()
                killed = True

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    return killed


def press_hotkey(keys: list[str]):
    pyautogui.hotkey(*keys)


def press_key(key: str):
    pyautogui.press(key)


def type_text(text: str):
    old_clipboard = ""

    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass

    pyperclip.copy(str(text))
    time.sleep(0.1)
    pyautogui.hotkey("ctrl", "v")

    try:
        pyperclip.copy(old_clipboard)
    except Exception:
        pass


def click_position(x: int, y: int, button: str = "left"):
    pyautogui.click(x=x, y=y, button=button)


def wait(seconds: float = 1):
    time.sleep(seconds)


def execute_tool_call(call: dict):
    tool = call.get("tool")

    if tool == "open_app":
        return open_app(call["app"])

    if tool == "open_or_focus_app":
        return open_or_focus_app(call["app"])

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


def execute_plan(plan: dict):
    steps = plan.get("steps", [])

    if not steps:
        raise ValueError("План пустой.")

    for step in steps:
        execute_tool_call(step)
        time.sleep(0.2)