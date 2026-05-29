from rapidfuzz import fuzz
import psutil
import pygetwindow as gw


OPEN_WORDS = [
    "открой", "открыть", "запусти", "запустить",
    "включи", "включить"
]

CLOSE_WORDS = [
    "закрой", "закрыть", "выключи", "выключить",
    "убери", "заверши", "завершить"
]

FOCUS_WORDS = [
    "переключись", "переключи", "перейди",
    "покажи", "открой окно"
]


APP_ALIASES = {
    "проводник": "explorer",
    "explorer": "explorer",

    "paint": "paint",
    "паинт": "paint",
    "пейнт": "paint",

    "блокнот": "notepad",
    "notepad": "notepad",

    "калькулятор": "calculator",
    "calculator": "calculator",
    "calc": "calculator",

    "диспетчер задач": "taskmgr",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",

    "chrome": "chrome",
    "хром": "chrome",
    "браузер": "chrome",

    "edge": "edge",

    "настройки": "settings",
    "settings": "settings",
}


def detect_action(text: str) -> str | None:
    lowered = text.lower()

    if any(word in lowered for word in CLOSE_WORDS):
        return "close_app"

    if any(word in lowered for word in FOCUS_WORDS):
        return "focus_app"

    if any(word in lowered for word in OPEN_WORDS):
        return "open_app"

    return None


def normalize_app_name(raw: str) -> str | None:
    text = raw.lower().strip()

    best_app = None
    best_score = 0

    for alias, app in APP_ALIASES.items():
        if alias in text:
            return app

        score = fuzz.partial_ratio(alias, text)
        if score > best_score:
            best_score = score
            best_app = app

    if best_score >= 75:
        return best_app

    return None


def get_running_window_names() -> list[str]:
    result = []

    for window in gw.getAllWindows():
        title = (window.title or "").strip()
        if title:
            result.append(title)

    return result


def get_running_process_names() -> list[str]:
    result = []

    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info.get("name")
            if name:
                result.append(name)
        except Exception:
            pass

    return result


def guess_app_from_running(command: str) -> str | None:
    lowered = command.lower()

    candidates = []

    for title in get_running_window_names():
        candidates.append(title)

    for proc_name in get_running_process_names():
        candidates.append(proc_name)

    best = None
    best_score = 0

    for candidate in candidates:
        score = fuzz.partial_ratio(lowered, candidate.lower())
        if score > best_score:
            best_score = score
            best = candidate

    if best_score < 55:
        return None

    return best


def fast_plan(command: str) -> dict | None:
    text = command.lower().strip()

    # Команды без объекта
    if text in ["пуск", "открой пуск", "нажми пуск"]:
        return {"tool": "press_key", "key": "win"}

    if text in ["сверни все", "сверни всё", "покажи рабочий стол", "рабочий стол"]:
        return {"tool": "press_hotkey", "keys": ["win", "d"]}

    if text in ["закрой окно", "закрой текущее окно"]:
        return {"tool": "press_hotkey", "keys": ["alt", "f4"]}

    if text in ["скопируй", "копировать"]:
        return {"tool": "press_hotkey", "keys": ["ctrl", "c"]}

    if text in ["вставь", "вставить"]:
        return {"tool": "press_hotkey", "keys": ["ctrl", "v"]}

    if text in ["выдели всё", "выдели все", "выделить всё"]:
        return {"tool": "press_hotkey", "keys": ["ctrl", "a"]}

    action = detect_action(text)
    if not action:
        return None

    app = normalize_app_name(text)

    if app:
        return {
            "tool": action,
            "app": app
        }

    # Если приложение не знаем по алиасам, пробуем найти среди открытых окон/процессов
    running_guess = guess_app_from_running(text)

    if running_guess:
        return {
            "tool": action,
            "app": running_guess
        }

    return None