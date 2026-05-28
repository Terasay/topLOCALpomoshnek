import base64
import json
import requests
from config import OLLAMA_MODEL, OLLAMA_URL


def image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def ask_ollama(user_command: str, screenshot_path: str | None = None) -> dict:
    system_prompt = """
Ты управляющий ассистентом Windows.
Твоя задача — вернуть ТОЛЬКО JSON без пояснений.

Доступные действия:
1. move_mouse: {"action":"move_mouse","x":100,"y":200}
2. click: {"action":"click","x":100,"y":200,"button":"left"}
3. type_text: {"action":"type_text","text":"hello"}
4. press_key: {"action":"press_key","key":"enter"}
5. hotkey: {"action":"hotkey","keys":["ctrl","c"]}
6. screenshot: {"action":"screenshot"}
7. wait: {"action":"wait","seconds":1}

Запрещено:
- удалять файлы
- запускать команды cmd/powershell
- менять системные настройки
- вводить пароли
- покупать что-либо
- отправлять сообщения без подтверждения пользователя

Если команда опасная или непонятная:
{"action":"refuse","reason":"причина"}
"""

    prompt = f"{system_prompt}\n\nКоманда пользователя: {user_command}"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }

    if screenshot_path:
        payload["images"] = [image_to_base64(screenshot_path)]

    response = requests.post(OLLAMA_URL, json=payload, timeout=120)
    response.raise_for_status()

    raw = response.json().get("response", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "action": "refuse",
            "reason": f"Модель вернула не JSON: {raw}"
        }