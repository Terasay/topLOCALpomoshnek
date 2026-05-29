import base64
import json
import re
import time
import subprocess
import requests

try:
    import pyperclip
except Exception:
    pyperclip = None

from screen import take_screenshot
from tools import execute_tool_call
from config import OLLAMA_VISION_MODEL, OLLAMA_CHAT_URL

try:
    from agent_client import plan_command
except Exception:
    plan_command = None


ALLOWED_TOOLS = {
    "click_position",
    "double_click_position",
    "move_mouse",
    "press_key",
    "press_hotkey",
    "type_text",
    "scroll",
    "wait",
    "open_app",
    "open_or_focus_app",
    "focus_app",
    "close_app",
    "done",
    "refuse",
}


APP_ALIASES = {
    "notepad": "notepad",
    "notepad.exe": "notepad",
    "блокнот": "notepad",
    "блокноте": "notepad",

    "paint": "paint",
    "mspaint": "paint",
    "mspaint.exe": "paint",
    "паинт": "paint",
    "пейнт": "paint",

    "chrome": "chrome",
    "google chrome": "chrome",
    "гугл": "chrome",
    "гугл хром": "chrome",
    "хром": "chrome",
    "браузер": "chrome",

    "edge": "edge",
    "microsoft edge": "edge",
    "эдж": "edge",

    "explorer": "explorer",
    "проводник": "explorer",

    "taskmgr": "taskmgr",
    "task manager": "taskmgr",
    "диспетчер задач": "taskmgr",

    "calculator": "calculator",
    "calc": "calculator",
    "калькулятор": "calculator",
}


APP_COMMANDS = {
    "notepad": "notepad.exe",
    "paint": "mspaint.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "explorer": "explorer.exe",
    "taskmgr": "taskmgr.exe",
    "calculator": "calc.exe",
}


WINDOW_TITLES = {
    "notepad": [
        "Блокнот",
        "Notepad",
        "Без имени",
        "Untitled",
        "Без имени - Блокнот",
        "Untitled - Notepad",
    ],
    "paint": [
        "Paint",
        "Безымянный - Paint",
        "Untitled - Paint",
    ],
    "chrome": [
        "Google Chrome",
        "Chrome",
    ],
    "edge": [
        "Microsoft Edge",
        "Edge",
    ],
    "explorer": [
        "Проводник",
        "File Explorer",
        "Explorer",
    ],
    "taskmgr": [
        "Диспетчер задач",
        "Task Manager",
    ],
    "calculator": [
        "Калькулятор",
        "Calculator",
    ],
}


def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_json(text: str) -> dict:
    text = str(text or "").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return {
        "done": False,
        "comment": "Модель вернула не JSON.",
        "action": {
            "tool": "refuse",
            "reason": text
        }
    }


def normalize_app_name(app) -> str:
    if app is None:
        return ""

    app = str(app).strip().lower()
    return APP_ALIASES.get(app, app)


def normalize_keys(keys):
    if keys is None:
        return []

    if isinstance(keys, list):
        return [str(key).strip().lower() for key in keys if str(key).strip()]

    if isinstance(keys, str):
        text = keys.strip().lower()

        if "+" in text:
            return [part.strip() for part in text.split("+") if part.strip()]

        if "," in text:
            return [part.strip() for part in text.split(",") if part.strip()]

        return [text]

    return []


def normalize_action(data) -> dict:
    """
    Приводит ответы модели к одному формату:

    {
        "done": false,
        "comment": "...",
        "action": {
            "tool": "...",
            ...
        }
    }
    """

    if not isinstance(data, dict):
        return {
            "done": False,
            "comment": "Модель вернула не объект JSON.",
            "action": {
                "tool": "refuse",
                "reason": str(data)
            }
        }

    done = bool(data.get("done", False))
    comment = str(data.get("comment", "") or "")

    if "action" not in data and "tool" in data:
        action = dict(data)
    else:
        action = data.get("action", {"tool": "done"})

    if isinstance(action, str):
        action = {"tool": action}

        for key in ("app", "block", "program", "application", "window", "name"):
            if key in data:
                action["app"] = data.get(key)
                break

    if not isinstance(action, dict):
        return {
            "done": False,
            "comment": "Модель вернула action в неправильном формате.",
            "action": {
                "tool": "refuse",
                "reason": str(action)
            }
        }

    if "tool" not in action and "action" in action:
        action["tool"] = action.get("action")

    tool = str(action.get("tool", "done") or "done").strip().lower()

    tool_aliases = {
        "open": "open_or_focus_app",
        "launch": "open_or_focus_app",
        "start": "open_or_focus_app",
        "run": "open_or_focus_app",
        "открыть": "open_or_focus_app",
        "открой": "open_or_focus_app",
        "запусти": "open_or_focus_app",

        "focus": "focus_app",
        "activate": "focus_app",
        "switch": "focus_app",
        "переключись": "focus_app",

        "close": "close_app",
        "exit": "close_app",
        "закрой": "close_app",

        "click": "click_position",
        "double_click": "double_click_position",
        "dblclick": "double_click_position",

        "hotkey": "press_hotkey",
        "keyboard_shortcut": "press_hotkey",

        "type": "type_text",
        "write": "type_text",
        "input": "type_text",
        "напиши": "type_text",
        "введи": "type_text",

        "finish": "done",
        "complete": "done",
        "готово": "done",
    }

    tool = tool_aliases.get(tool, tool)
    action["tool"] = tool

    if "block" in action and "app" not in action:
        action["app"] = action.pop("block")

    if "app" not in action:
        for key in ("program", "application", "window", "name"):
            if key in action:
                action["app"] = action.get(key)
                break

    if "app" in action:
        action["app"] = normalize_app_name(action.get("app"))

    if tool == "press_hotkey":
        action["keys"] = normalize_keys(action.get("keys"))

    if tool == "press_key" and "key" in action:
        action["key"] = str(action.get("key")).strip().lower()

    if tool in {"click_position", "double_click_position", "move_mouse"}:
        try:
            action["x"] = int(action.get("x", 0))
            action["y"] = int(action.get("y", 0))
        except Exception:
            action["x"] = 0
            action["y"] = 0

    if tool in {"click_position", "double_click_position"}:
        action["button"] = str(action.get("button", "left") or "left").lower()

    if tool == "wait":
        try:
            action["seconds"] = float(action.get("seconds", 1))
        except Exception:
            action["seconds"] = 1

    if tool == "scroll":
        try:
            action["amount"] = int(action.get("amount", -500))
        except Exception:
            action["amount"] = -500

    return {
        "done": done,
        "comment": comment,
        "action": action
    }


def get_app_alias_pattern() -> str:
    aliases = sorted(APP_ALIASES.keys(), key=len, reverse=True)
    return "|".join(re.escape(alias) for alias in aliases)


def detect_app_in_text(text: str) -> str:
    text_lower = str(text or "").lower()

    for alias in sorted(APP_ALIASES.keys(), key=len, reverse=True):
        if alias in text_lower:
            return APP_ALIASES[alias]

    return ""


def build_fast_local_plan(user_goal: str):
    """
    Быстрый локальный план без нейросети.

    Простые команды выполняются тут:
    - открой блокнот
    - напиши в блокнот привет
    - закрой блокнот
    - сохрани файл
    """

    original = str(user_goal or "").strip()
    text = original.lower()

    if not text:
        return None

    app_pattern = get_app_alias_pattern()

    # "напиши в блокнот привет"
    match = re.match(
        rf"^\s*(?:напиши|напечатай|введи|запиши)\s+"
        rf"(?:в\s+|во\s+|внутри\s+|в\s+окне\s+)?"
        rf"(?P<app>{app_pattern})\s+"
        rf"(?P<text>.+?)\s*$",
        original,
        flags=re.IGNORECASE
    )

    if match:
        app = normalize_app_name(match.group("app"))
        typed_text = match.group("text").strip()

        return {
            "steps": [
                {"tool": "open_or_focus_app", "app": app},
                {"tool": "wait", "seconds": 0.6},
                {"tool": "type_text", "text": typed_text},
            ]
        }

    # "напиши привет в блокнот"
    match = re.match(
        rf"^\s*(?:напиши|напечатай|введи|запиши)\s+"
        rf"(?P<text>.+?)\s+"
        rf"(?:в\s+|во\s+|внутри\s+|в\s+окне\s+)"
        rf"(?P<app>{app_pattern})\s*$",
        original,
        flags=re.IGNORECASE
    )

    if match:
        app = normalize_app_name(match.group("app"))
        typed_text = match.group("text").strip()

        return {
            "steps": [
                {"tool": "open_or_focus_app", "app": app},
                {"tool": "wait", "seconds": 0.6},
                {"tool": "type_text", "text": typed_text},
            ]
        }

    app = detect_app_in_text(text)

    if app and re.search(r"(открой|открыть|запусти|запустить|open|launch|start)", text):
        return {
            "steps": [
                {"tool": "open_or_focus_app", "app": app}
            ]
        }

    if app and re.search(r"(закрой|закрыть|close|exit)", text):
        return {
            "steps": [
                {"tool": "close_app", "app": app}
            ]
        }

    if app and re.search(r"(переключись|переключи|сфокусируй|focus|switch)", text):
        return {
            "steps": [
                {"tool": "focus_app", "app": app}
            ]
        }

    if re.search(r"(сохрани|сохранить)", text):
        return {
            "steps": [
                {"tool": "press_hotkey", "keys": ["ctrl", "s"]}
            ]
        }

    if re.search(r"(скопируй|копировать)", text):
        return {
            "steps": [
                {"tool": "press_hotkey", "keys": ["ctrl", "c"]}
            ]
        }

    if re.search(r"(вставь|вставить)", text):
        return {
            "steps": [
                {"tool": "press_hotkey", "keys": ["ctrl", "v"]}
            ]
        }

    if re.search(r"(вырежи|вырезать)", text):
        return {
            "steps": [
                {"tool": "press_hotkey", "keys": ["ctrl", "x"]}
            ]
        }

    if re.search(r"(отмени|отменить)", text):
        return {
            "steps": [
                {"tool": "press_hotkey", "keys": ["ctrl", "z"]}
            ]
        }

    if re.search(r"(нажми|press)\s+enter", text):
        return {
            "steps": [
                {"tool": "press_key", "key": "enter"}
            ]
        }

    if re.search(r"(нажми|press)\s+esc", text):
        return {
            "steps": [
                {"tool": "press_key", "key": "esc"}
            ]
        }

    return None


def ask_next_action(user_goal: str, screenshot_path: str, history: list[str]) -> dict:
    system_prompt = """
Ты агент управления Windows по скриншоту.
Ты видишь экран и должен выбрать ОДНО следующее действие для достижения цели пользователя.

Верни ТОЛЬКО JSON без markdown и пояснений.

Главный формат:
{
  "done": false,
  "comment": "коротко что делаешь",
  "action": {
    "tool": "click_position",
    "x": 100,
    "y": 200,
    "button": "left"
  }
}

Когда задача завершена:
{
  "done": true,
  "comment": "задача выполнена",
  "action": {"tool": "done"}
}

Доступные действия:

1. Открыть приложение или переключиться на него:
{"tool":"open_or_focus_app","app":"notepad"}

2. Открыть приложение:
{"tool":"open_app","app":"notepad"}

3. Переключиться на приложение:
{"tool":"focus_app","app":"notepad"}

4. Закрыть активное/указанное приложение:
{"tool":"close_app","app":"notepad"}

5. Клик:
{"tool":"click_position","x":100,"y":200,"button":"left"}

6. Двойной клик:
{"tool":"double_click_position","x":100,"y":200,"button":"left"}

7. Переместить мышь:
{"tool":"move_mouse","x":100,"y":200}

8. Нажать клавишу:
{"tool":"press_key","key":"enter"}

9. Горячие клавиши:
{"tool":"press_hotkey","keys":["ctrl","s"]}

10. Напечатать текст:
{"tool":"type_text","text":"привет мир"}

11. Прокрутить:
{"tool":"scroll","amount":-500}

12. Подождать:
{"tool":"wait","seconds":1}

Правила:
- Делай только один следующий шаг.
- Не пытайся выполнить всю задачу одним JSON.
- Координаты считай по скриншоту: левый верхний угол это x=0,y=0.
- НИКОГДА не кликай и не перемещай мышь в точку x=0,y=0.
- НИКОГДА не кликай и не перемещай мышь в левый верхний угол.
- Если нужно открыть блокнот, используй:
  {"tool":"open_or_focus_app","app":"notepad"}
- Если нужно написать текст, сначала убедись, что нужное окно активно.
- Не используй поле "block". Используй только "app".
- Не используй cmd, powershell, regedit.
- Не удаляй файлы.
- Не вводи пароли.
- Не покупай ничего.
- Не отправляй сообщения без явной команды пользователя.
- Если не уверен, используй wait или refuse.
"""

    history_text = "\n".join(history[-8:])

    user_prompt = f"""
Цель пользователя:
{user_goal}

Последние действия:
{history_text}

Выбери следующее действие.
"""

    payload = {
        "model": OLLAMA_VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt,
                "images": [image_to_base64(screenshot_path)]
            }
        ],
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
            "temperature": 0,
            "num_ctx": 2048,
            "num_predict": 180
        }
    }

    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=120)
    response.raise_for_status()

    raw = response.json().get("message", {}).get("content", "").strip()
    return normalize_action(extract_json(raw))


def validate_agent_action(action: dict):
    if not isinstance(action, dict):
        raise ValueError(f"action должен быть dict, а получил: {type(action)}")

    tool = action.get("tool")

    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"Запрещённый или неизвестный tool: {tool}")

    if tool in {"click_position", "double_click_position", "move_mouse"}:
        try:
            x = int(action.get("x", -1))
            y = int(action.get("y", -1))
        except Exception:
            raise ValueError("Координаты мыши должны быть числами.")

        if x <= 5 and y <= 5:
            raise ValueError(
                "Агент попытался нажать или двинуть мышь в левый верхний угол экрана. "
                "Это аварийная зона PyAutoGUI, действие заблокировано."
            )

    return True


def focus_existing_window(app: str) -> bool:
    """
    Пытается найти уже открытое окно и сфокусировать его.
    Если pygetwindow не установлен или окно не найдено — просто вернёт False.
    """

    app = normalize_app_name(app)
    titles = WINDOW_TITLES.get(app, [app])

    try:
        import pygetwindow as gw
    except Exception:
        return False

    try:
        for title in titles:
            windows = gw.getWindowsWithTitle(title)

            for window in windows:
                if not window:
                    continue

                try:
                    if window.isMinimized:
                        window.restore()

                    window.activate()
                    time.sleep(0.25)
                    return True
                except Exception:
                    continue
    except Exception:
        return False

    return False


def open_application(app: str) -> bool:
    app = normalize_app_name(app)

    if not app:
        return False

    command = APP_COMMANDS.get(app)

    if command:
        try:
            subprocess.Popen([command], shell=False)
            time.sleep(1.0)
            focus_existing_window(app)
            return True
        except Exception:
            pass

    # Запасной способ через Win+R.
    try:
        execute_tool_call({"tool": "press_hotkey", "keys": ["win", "r"]})
        time.sleep(0.25)
        execute_tool_call({"tool": "type_text", "text": app})
        time.sleep(0.15)
        execute_tool_call({"tool": "press_key", "key": "enter"})
        time.sleep(1.0)
        focus_existing_window(app)
        return True
    except Exception:
        return False


def close_application(app: str) -> bool:
    app = normalize_app_name(app)

    if app:
        focus_existing_window(app)

    try:
        execute_tool_call({"tool": "press_hotkey", "keys": ["alt", "f4"]})
        time.sleep(0.3)
        return True
    except Exception:
        return False


def paste_text(text: str):
    """
    Ввод текста через буфер обмена.
    Это нужно, потому что pyautogui/keyboard часто не печатают кириллицу нормально.
    """

    text = str(text or "")

    if not text:
        return

    if pyperclip is None:
        raise RuntimeError(
            "Не установлен pyperclip. Выполни команду: py -3.11 -m pip install pyperclip"
        )

    pyperclip.copy(text)
    time.sleep(0.15)

    execute_tool_call({
        "tool": "press_hotkey",
        "keys": ["ctrl", "v"]
    })

    time.sleep(0.2)


def execute_normalized_action(action: dict):
    tool = action.get("tool")

    if tool == "type_text":
        paste_text(action.get("text", ""))
        return

    if tool == "open_or_focus_app":
        app = action.get("app", "")

        if focus_existing_window(app):
            return

        if not open_application(app):
            raise RuntimeError(f"Не удалось открыть приложение: {app}")

        time.sleep(0.5)
        focus_existing_window(app)
        return

    if tool == "open_app":
        app = action.get("app", "")

        if not open_application(app):
            raise RuntimeError(f"Не удалось открыть приложение: {app}")

        time.sleep(0.5)
        focus_existing_window(app)
        return

    if tool == "focus_app":
        app = action.get("app", "")

        if not focus_existing_window(app):
            raise RuntimeError(f"Не удалось переключиться на приложение: {app}")

        return

    if tool == "close_app":
        app = action.get("app", "")

        if not close_application(app):
            raise RuntimeError(f"Не удалось закрыть приложение: {app}")

        return

    execute_tool_call(action)


def execute_steps(plan: dict, write, source_name: str = "План"):
    if not isinstance(plan, dict):
        write(f"{source_name} вернул не объект JSON.", "error")
        return False

    steps = plan.get("steps")

    if not isinstance(steps, list) or not steps:
        write(f"{source_name} не вернул steps.", "warning")
        return None

    write(f"{source_name} вернул план:", "info")
    write(json.dumps(plan, ensure_ascii=False, indent=2), "code")

    for index, raw_action in enumerate(steps, start=1):
        normalized = normalize_action({
            "done": False,
            "comment": f"Шаг {index}",
            "action": raw_action
        })

        action = normalized.get("action", {"tool": "done"})

        write(f"{source_name}. Шаг {index}:", "info")
        write(json.dumps(action, ensure_ascii=False, indent=2), "code")

        if action.get("tool") == "done":
            return True

        if action.get("tool") == "refuse":
            reason = action.get("reason", f"{source_name} отказался выполнять команду.")
            write(reason, "error")
            return False

        validate_agent_action(action)
        execute_normalized_action(action)

        time.sleep(0.35)

    return True


def run_planner_steps(user_goal: str, write):
    """
    Сначала пробуем:
    1. быстрый локальный план без нейросети;
    2. текстовый планировщик agent_client.py.

    Только если оба не справились, запускаем зрительного агента.
    """

    fast_plan = build_fast_local_plan(user_goal)

    if fast_plan is not None:
        result = execute_steps(fast_plan, write, "Быстрый локальный план")
        if result is not None:
            return result

    if plan_command is None:
        write("agent_client.plan_command недоступен. Перехожу к агенту по скриншоту.", "warning")
        return None

    try:
        plan = plan_command(user_goal)
    except Exception as e:
        write(f"Планировщик не сработал, перехожу к агенту по скриншоту: {e}", "warning")
        return None

    result = execute_steps(plan, write, "Текстовый планировщик")

    if result is not None:
        return result

    return None


def run_desktop_agent(user_goal: str, log=None, max_steps: int = 8):
    history = []

    def write(message: str, kind: str = "info"):
        if log:
            log(message, kind)

    planner_result = run_planner_steps(user_goal, write)

    if planner_result is not None:
        return planner_result

    for step_index in range(1, max_steps + 1):
        write(f"Шаг агента {step_index}: делаю скриншот.", "info")

        screenshot_path = take_screenshot("agent_screen.png")

        plan = ask_next_action(user_goal, screenshot_path, history)
        plan = normalize_action(plan)

        comment = plan.get("comment", "")
        action = plan.get("action", {"tool": "done"})
        done = bool(plan.get("done", False))

        write("Решение агента:", "info")
        write(json.dumps(plan, ensure_ascii=False, indent=2), "code")

        if done or action.get("tool") == "done":
            write(comment or "Задача завершена.", "success")
            return True

        validate_agent_action(action)

        if action.get("tool") == "refuse":
            reason = action.get("reason", "Агент отказался выполнять действие.")
            write(reason, "error")
            return False

        execute_normalized_action(action)

        history.append(f"{step_index}. {comment} -> {action}")

        time.sleep(0.5)

    write("Достигнут лимит шагов агента. Задача остановлена.", "warning")
    return False