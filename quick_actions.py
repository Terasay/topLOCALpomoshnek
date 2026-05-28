def get_quick_action(command: str):
    text = command.lower().strip()

    if "пуск" in text or "start" in text:
        return {"action": "press_key", "key": "win"}

    if "сверни все" in text or "рабочий стол" in text:
        return {"action": "hotkey", "keys": ["win", "d"]}

    if "закрой окно" in text:
        return {"action": "hotkey", "keys": ["alt", "f4"]}

    if "скопируй" in text:
        return {"action": "hotkey", "keys": ["ctrl", "c"]}

    if "вставь" in text:
        return {"action": "hotkey", "keys": ["ctrl", "v"]}

    if "enter" in text or "энтер" in text:
        return {"action": "press_key", "key": "enter"}

    if "escape" in text or "esc" in text:
        return {"action": "press_key", "key": "esc"}

    return None