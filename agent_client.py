import json
import re
import requests
from config import OLLAMA_MODEL


OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"


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
        "tool": "refuse",
        "reason": f"Модель вернула не JSON: {text}"
    }


def plan_command(user_command: str) -> dict:
    system_prompt = """
Ты локальный агент управления Windows.
Ты НЕ кликаешь по экрану без необходимости.
Ты выбираешь один инструмент и возвращаешь ТОЛЬКО JSON.

Доступные инструменты:

1. Открыть приложение:
{"tool":"open_app","app":"explorer"}

Разрешённые приложения:
explorer, notepad, calculator, chrome, edge, paint, settings

2. Нажать горячие клавиши:
{"tool":"press_hotkey","keys":["win","d"]}

3. Нажать одну клавишу:
{"tool":"press_key","key":"enter"}

4. Напечатать текст:
{"tool":"type_text","text":"пример"}

5. Кликнуть по координатам:
{"tool":"click_position","x":100,"y":200,"button":"left"}

6. Подождать:
{"tool":"wait","seconds":1}

7. Отказ:
{"tool":"refuse","reason":"причина"}

8. Закрыть приложение:
{"tool":"close_app","app":"explorer"}

9. Переключиться на приложение:
{"tool":"focus_app","app":"chrome"}

Разрешённые приложения и их app id:
- explorer: проводник, explorer
- taskmgr: диспетчер задач, task manager
- notepad: блокнот, notepad
- calculator: калькулятор, calc
- chrome: браузер, chrome
- edge: edge
- paint: paint, пейнт
- settings: настройки

Правила:
- Если пользователь просит открыть проводник — используй open_app explorer.
- Если пользователь просит открыть блокнот — используй open_app notepad.
- Если пользователь просит открыть калькулятор — используй open_app calculator.
- Если пользователь просит открыть браузер — используй open_app chrome.
- Если пользователь просит свернуть все окна — используй press_hotkey win+d.
- Если пользователь просит закрыть окно — используй press_hotkey alt+f4.
- Если пользователь просит скопировать — используй press_hotkey ctrl+c.
- Если пользователь просит вставить — используй press_hotkey ctrl+v.
- Если пользователь просит закрыть приложение — используй close_app.
- Если пользователь просит переключиться на приложение — используй focus_app.
- Не открывай приложение, если пользователь просит его закрыть.
- Если пользователь просит открыть приложение — используй open_app.
- Если пользователь просит закрыть приложение — используй close_app.
- Если пользователь просит переключиться на приложение — используй focus_app.
- "диспетчер задач" всегда app="taskmgr".
- "проводник" всегда app="explorer".
- "блокнот" всегда app="notepad".
- "калькулятор" всегда app="calculator".
- Не используй press_hotkey ctrl+shift+esc для закрытия диспетчера задач.
- Для закрытия диспетчера задач используй {"tool":"close_app","app":"taskmgr"}.
- Внимательно различай:
  открыть
  закрыть
  переключиться
  свернуть
- Не запускай cmd, powershell, regedit.
- Не удаляй файлы.
- Не вводи пароли.
- Не отправляй сообщения.
- Если команда непонятна — refuse.
"""

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_command}
        ],
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
            "temperature": 0,
            "num_predict": 80,
            "num_ctx": 1024
        }
    }

    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=180)
    response.raise_for_status()

    raw = response.json().get("message", {}).get("content", "").strip()
    print("План модели:", raw)

    return extract_json(raw)