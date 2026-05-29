import base64
import json
import re
import time
import requests

from screen import take_screenshot
from tools import execute_tool_call
from config import OLLAMA_VISION_MODEL, OLLAMA_CHAT_URL


ALLOWED_TOOLS = {
    "click_position",
    "double_click_position",
    "move_mouse",
    "press_key",
    "press_hotkey",
    "type_text",
    "scroll",
    "wait",
    "done",
    "refuse"
}


def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_json(text: str) -> dict:
    text = text.strip()

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


def normalize_action(data: dict) -> dict:
    if "action" not in data:
        if data.get("tool"):
            return {
                "done": False,
                "comment": data.get("comment", ""),
                "action": data
            }

        return {
            "done": True,
            "comment": "Нет действия.",
            "action": {"tool": "done"}
        }

    return data


def ask_next_action(user_goal: str, screenshot_path: str, history: list[str]) -> dict:
    system_prompt = """
Ты агент управления Windows по скриншоту.
Ты видишь экран и должен выбрать ОДНО следующее действие для достижения цели пользователя.

Верни ТОЛЬКО JSON без markdown.

Формат:
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

1. Клик:
{"tool":"click_position","x":100,"y":200,"button":"left"}

2. Двойной клик:
{"tool":"double_click_position","x":100,"y":200,"button":"left"}

3. Переместить мышь:
{"tool":"move_mouse","x":100,"y":200}

4. Нажать клавишу:
{"tool":"press_key","key":"enter"}

5. Горячие клавиши:
{"tool":"press_hotkey","keys":["ctrl","s"]}

6. Напечатать текст:
{"tool":"type_text","text":"привет мир"}

7. Прокрутить:
{"tool":"scroll","amount":-500}

8. Подождать:
{"tool":"wait","seconds":1}

Правила:
- Делай только один следующий шаг.
- Не пытайся выполнить всю задачу одним JSON.
- Координаты считай по скриншоту: левый верхний угол это x=0,y=0.
- Если нужно открыть приложение, можно использовать Win+S, затем type_text с названием приложения, затем Enter.
- Если нужно написать текст, сначала убедись, что нужное окно активно.
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
    tool = action.get("tool")

    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"Запрещённый или неизвестный tool: {tool}")

    return True


def run_desktop_agent(user_goal: str, log=None, max_steps: int = 8):
    history = []

    def write(message: str, kind: str = "info"):
        if log:
            log(message, kind)

    for step_index in range(1, max_steps + 1):
        write(f"Шаг агента {step_index}: делаю скриншот.", "info")

        screenshot_path = take_screenshot("agent_screen.png")

        plan = ask_next_action(user_goal, screenshot_path, history)

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

        execute_tool_call(action)

        history.append(f"{step_index}. {comment} -> {action}")

        time.sleep(0.5)

    write("Достигнут лимит шагов агента. Задача остановлена.", "warning")
    return False