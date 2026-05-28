def get_quick_action(command: str):
    text = command.lower().strip()

    if "пуск" in text or "start" in text:
        return {"tool": "press_key", "key": "win"}

    if "сверни все" in text or "свернуть все" in text or "рабочий стол" in text:
        return {"tool": "press_hotkey", "keys": ["win", "d"]}

    if "закрой окно" in text or "закрыть окно" in text:
        return {"tool": "press_hotkey", "keys": ["alt", "f4"]}

    if "проводник" in text or "explorer" in text:
        return {"tool": "open_app", "app": "explorer"}

    if "диспетчер задач" in text:
        return {"tool": "press_hotkey", "keys": ["ctrl", "shift", "esc"]}

    if "настройки" in text:
        return {"tool": "open_app", "app": "settings"}

    if "калькулятор" in text:
        return {"tool": "open_app", "app": "calculator"}

    if "блокнот" in text:
        return {"tool": "open_app", "app": "notepad"}

    if "скопируй" in text or "копировать" in text:
        return {"tool": "press_hotkey", "keys": ["ctrl", "c"]}

    if "вставь" in text or "вставить" in text:
        return {"tool": "press_hotkey", "keys": ["ctrl", "v"]}

    if "выдели всё" in text or "выделить всё" in text or "выдели все" in text:
        return {"tool": "press_hotkey", "keys": ["ctrl", "a"]}

    if "enter" in text or "энтер" in text:
        return {"tool": "press_key", "key": "enter"}

    if "escape" in text or "esc" in text:
        return {"tool": "press_key", "key": "esc"}

    return None