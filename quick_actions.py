def get_quick_action(command: str):
    text = command.lower().strip()

    # Только команды, где вообще нет объекта и смысла думать не надо

    if text in ["пуск", "start", "открой пуск", "нажми пуск"]:
        return {"tool": "press_key", "key": "win"}

    if text in ["сверни все", "сверни всё", "свернуть все окна", "рабочий стол", "покажи рабочий стол"]:
        return {"tool": "press_hotkey", "keys": ["win", "d"]}

    if text in ["закрой окно", "закрыть окно", "закрой текущее окно"]:
        return {"tool": "press_hotkey", "keys": ["alt", "f4"]}

    if text in ["скопируй", "копировать"]:
        return {"tool": "press_hotkey", "keys": ["ctrl", "c"]}

    if text in ["вставь", "вставить"]:
        return {"tool": "press_hotkey", "keys": ["ctrl", "v"]}

    if text in ["выдели всё", "выделить всё", "выдели все"]:
        return {"tool": "press_hotkey", "keys": ["ctrl", "a"]}

    if text in ["enter", "энтер", "нажми enter", "нажми энтер"]:
        return {"tool": "press_key", "key": "enter"}

    if text in ["esc", "escape", "нажми esc", "нажми escape"]:
        return {"tool": "press_key", "key": "esc"}

    return None