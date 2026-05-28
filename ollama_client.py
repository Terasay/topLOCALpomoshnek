import base64
import json
import re
import requests
from config import OLLAMA_MODEL


OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"


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
        "action": "refuse",
        "reason": f"Модель вернула не JSON: {text}"
    }


def ask_ollama(user_command: str, screenshot_path: str | None = None) -> dict:
    system_prompt = """
Ты управляющий ассистентом Windows.
Верни ТОЛЬКО один JSON-объект без markdown и пояснений.

Доступные действия:
{"action":"move_mouse","x":100,"y":200}
{"action":"click","x":100,"y":200,"button":"left"}
{"action":"type_text","text":"hello"}
{"action":"press_key","key":"enter"}
{"action":"hotkey","keys":["ctrl","c"]}
{"action":"screenshot"}
{"action":"wait","seconds":1}
{"action":"refuse","reason":"причина"}

Если пользователь просит нажать Пуск, верни:
{"action":"press_key","key":"win"}

Запрещено:
- удалять файлы
- запускать cmd/powershell
- менять системные настройки
- вводить пароли
- покупать что-либо
- отправлять сообщения без подтверждения пользователя
"""

    content = f"Команда пользователя: {user_command}"

    message = {
        "role": "user",
        "content": content
    }

    if screenshot_path:
        message["images"] = [image_to_base64(screenshot_path)]

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            message
        ],
        "stream": False,
        "options": {
            "temperature": 0
        }
    }

    print("Отправляю запрос в Ollama...")

    response = requests.post(OLLAMA_CHAT_URL, json=payload, timeout=300)

    print("HTTP статус:", response.status_code)
    response.raise_for_status()

    data = response.json()
    raw = data.get("message", {}).get("content", "").strip()

    print("Сырой ответ модели:")
    print(raw)

    return extract_json(raw)