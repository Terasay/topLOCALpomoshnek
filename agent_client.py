import json
import re
import requests
from config import OLLAMA_PLANNER_MODEL, OLLAMA_CHAT_URL


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
        "steps": [
            {
                "tool": "refuse",
                "reason": f"Модель вернула не JSON: {text}"
            }
        ]
    }


def plan_command(user_command: str) -> dict:
    system_prompt = """
Ты локальный планировщик действий для Windows.
Твоя задача — преобразовать команду пользователя в JSON-план.
Верни ТОЛЬКО JSON без markdown и пояснений.

Формат ответа:
{
  "steps": [
    {"tool": "open_or_focus_app", "app": "notepad"},
    {"tool": "type_text", "text": "привет мир"}
  ]
}

Доступные инструменты:

1. Открыть приложение:
{"tool":"open_app","app":"notepad"}

2. Открыть приложение или переключиться на него, если оно уже открыто:
{"tool":"open_or_focus_app","app":"notepad"}

3. Закрыть приложение:
{"tool":"close_app","app":"paint"}

4. Переключиться на приложение:
{"tool":"focus_app","app":"chrome"}

5. Напечатать текст в активное окно:
{"tool":"type_text","text":"привет мир"}

6. Нажать одну клавишу:
{"tool":"press_key","key":"enter"}

7. Нажать сочетание клавиш:
{"tool":"press_hotkey","keys":["ctrl","s"]}

8. Подождать:
{"tool":"wait","seconds":1}

9. Отказ:
{"tool":"refuse","reason":"причина"}

Правила:
- Не кликай мышкой без крайней необходимости.
- Если пользователь просит написать/напечатать/ввести текст в приложение, сделай два шага:
  1) open_or_focus_app
  2) type_text
- Пример: "напиши в блокнот привет мир"
  → {"steps":[{"tool":"open_or_focus_app","app":"notepad"},{"tool":"type_text","text":"привет мир"}]}
- Пример: "напиши в блокноте привет мир"
  → {"steps":[{"tool":"open_or_focus_app","app":"notepad"},{"tool":"type_text","text":"привет мир"}]}
- Пример: "открой paint"
  → {"steps":[{"tool":"open_app","app":"paint"}]}
- Пример: "закрой диспетчер задач"
  → {"steps":[{"tool":"close_app","app":"taskmgr"}]}
- Пример: "переключись на chrome"
  → {"steps":[{"tool":"focus_app","app":"chrome"}]}
- Пример: "сохрани файл"
  → {"steps":[{"tool":"press_hotkey","keys":["ctrl","s"]}]}
- Если приложение неизвестно, всё равно передай его как app обычным текстом.
- Не запускай cmd, powershell, regedit.
- Не удаляй файлы.
- Не вводи пароли.
- Не покупай ничего.
- Не отправляй сообщения без явной команды пользователя.
"""

    payload = {
        "model": OLLAMA_PLANNER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_command}
        ],
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {
            "temperature": 0,
            "num_ctx": 1024,
            "num_predict": 160
        }
    }

    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=60)
    response.raise_for_status()

    raw = response.json().get("message", {}).get("content", "").strip()
    print("План модели:", raw)

    plan = extract_json(raw)

    if "tool" in plan:
        return {"steps": [plan]}

    if "steps" not in plan:
        return {
            "steps": [
                {
                    "tool": "refuse",
                    "reason": "Модель не вернула steps."
                }
            ]
        }

    return plan