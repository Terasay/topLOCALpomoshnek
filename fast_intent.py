from rapidfuzz import fuzz

WRITE_WORDS = [
    "напиши", "написать", "напечатай", "напечатать",
    "введи", "ввести", "запиши", "записать",
    "write", "type", "print"
]


OPEN_WORDS = [
    "открой", "открыть", "запусти", "запустить", "включи", "включить",
    "open", "start", "run", "launch"
]

CLOSE_WORDS = [
    "закрой", "закрыть", "выключи", "выключить", "убери",
    "заверши", "завершить",
    "close", "quit", "exit", "kill", "terminate", "stop", "end"
]

FOCUS_WORDS = [
    "переключись", "переключи", "перейди", "покажи", "выведи",
    "focus", "switch to", "show", "activate", "go to"
]


APP_ALIASES = {
    "проводник": "explorer",
    "explorer": "explorer",
    "file explorer": "explorer",

    "paint": "paint",
    "pa": "paint",
    "паинт": "paint",
    "пейнт": "paint",
    "mspaint": "paint",

    "блокнот": "notepad",
    "notepad": "notepad",
    "note pad": "notepad",

    "калькулятор": "calculator",
    "calculator": "calculator",
    "calc": "calculator",

    "диспетчер задач": "taskmgr",
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",

    "chrome": "chrome",
    "google chrome": "chrome",
    "хром": "chrome",
    "браузер": "chrome",

    "edge": "edge",
    "microsoft edge": "edge",
    "эдж": "edge",

    "store": "store",
    "microsoft store": "store",
    "магазин": "store",
    "магазин microsoft": "store",

    "настройки": "settings",
    "settings": "settings",
}


SPECIAL_COMMANDS = {
    "пуск": {"tool": "press_key", "key": "win"},
    "start menu": {"tool": "press_key", "key": "win"},
    "открой пуск": {"tool": "press_key", "key": "win"},
    "нажми пуск": {"tool": "press_key", "key": "win"},

    "сверни все": {"tool": "press_hotkey", "keys": ["win", "d"]},
    "сверни всё": {"tool": "press_hotkey", "keys": ["win", "d"]},
    "покажи рабочий стол": {"tool": "press_hotkey", "keys": ["win", "d"]},
    "show desktop": {"tool": "press_hotkey", "keys": ["win", "d"]},

    "закрой окно": {"tool": "press_hotkey", "keys": ["alt", "f4"]},
    "close window": {"tool": "press_hotkey", "keys": ["alt", "f4"]},

    "скопируй": {"tool": "press_hotkey", "keys": ["ctrl", "c"]},
    "copy": {"tool": "press_hotkey", "keys": ["ctrl", "c"]},

    "вставь": {"tool": "press_hotkey", "keys": ["ctrl", "v"]},
    "paste": {"tool": "press_hotkey", "keys": ["ctrl", "v"]},

    "выдели всё": {"tool": "press_hotkey", "keys": ["ctrl", "a"]},
    "выдели все": {"tool": "press_hotkey", "keys": ["ctrl", "a"]},
    "select all": {"tool": "press_hotkey", "keys": ["ctrl", "a"]},

    "enter": {"tool": "press_key", "key": "enter"},
    "энтер": {"tool": "press_key", "key": "enter"},
    "escape": {"tool": "press_key", "key": "esc"},
    "esc": {"tool": "press_key", "key": "esc"},
}


def clean_text(text: str) -> str:
    return " ".join(text.lower().strip().split())


def normalize_known_app(app_text: str) -> str | None:
    """
    Нормализует только если уверены.
    Не делает агрессивное fuzzy-угадывание, чтобы microsoft store не превращался в edge.
    """
    text = clean_text(app_text)

    if not text:
        return None

    if text in APP_ALIASES:
        return APP_ALIASES[text]

    # Проверка по целым фразам
    for alias, app in sorted(APP_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in text:
            return app

    # Осторожный fuzzy только для коротких ошибочных распознаваний
    # Например "паинт" / "пейнт", но не "microsoft store" → "microsoft edge"
    if len(text) <= 8:
        best_app = None
        best_score = 0

        for alias, app in APP_ALIASES.items():
            score = fuzz.ratio(text, alias)
            if score > best_score:
                best_score = score
                best_app = app

        if best_score >= 82:
            return best_app

    return None


def find_action(text: str) -> tuple[str | None, str]:
    lowered = clean_text(text)

    groups = [
        ("close_app", CLOSE_WORDS),
        ("focus_app", FOCUS_WORDS),
        ("open_app", OPEN_WORDS),
    ]

    for tool, words in groups:
        for word in sorted(words, key=len, reverse=True):
            word = clean_text(word)

            if lowered == word:
                return tool, ""

            if lowered.startswith(word + " "):
                app_part = lowered[len(word):].strip()
                return tool, app_part

    return None, lowered


def strip_outer_quotes(text: str) -> str:
    text = text.strip()

    quote_pairs = [
        ('"', '"'),
        ("'", "'"),
        ("«", "»"),
        ("“", "”"),
    ]

    for left, right in quote_pairs:
        if text.startswith(left) and text.endswith(right):
            return text[1:-1].strip()

    return text


def extract_write_command(command: str) -> dict | None:
    text = clean_text(command)

    used_word = None

    for word in sorted(WRITE_WORDS, key=len, reverse=True):
        word = clean_text(word)

        if text == word:
            return None

        if text.startswith(word + " "):
            used_word = word
            break

    if not used_word:
        return None

    rest = text[len(used_word):].strip()

    if not rest:
        return None

    # Убираем лишнюю вежливую шелуху, потому что люди почему-то разговаривают словами.
    for junk in ["пожалуйста", "плиз"]:
        rest = rest.replace(junk, "").strip()

    aliases = sorted(APP_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)

    for alias, app in aliases:
        alias = clean_text(alias)

        # Формат: "напиши в блокнот привет мир"
        prefix = f"в {alias} "
        if rest.startswith(prefix):
            text_part = rest[len(prefix):].strip()
            if text_part:
                return {
                    "tool": "write_to_app",
                    "app": app,
                    "text": strip_outer_quotes(text_part)
                }

        # Формат: "напиши привет мир в блокнот"
        suffix = f" в {alias}"
        if rest.endswith(suffix):
            text_part = rest[:-len(suffix)].strip()
            if text_part:
                return {
                    "tool": "write_to_app",
                    "app": app,
                    "text": strip_outer_quotes(text_part)
                }

        # Формат: "напиши привет мир в блокнот сейчас"
        middle = f" в {alias} "
        if middle in rest:
            before, after = rest.split(middle, 1)

            before = before.strip()
            after = after.strip()

            text_part = before or after

            if text_part:
                return {
                    "tool": "write_to_app",
                    "app": app,
                    "text": strip_outer_quotes(text_part)
                }

    # Если приложение не указано, печатаем в активное окно.
    return {
        "tool": "type_text",
        "text": strip_outer_quotes(rest)
    }

def fast_plan(command: str) -> dict | None:
    text = clean_text(command)

    write_action = extract_write_command(command)

    if write_action:
        return write_action

    if text in SPECIAL_COMMANDS:
        return SPECIAL_COMMANDS[text]

    tool, app_part = find_action(text)

    if tool:
        known_app = normalize_known_app(app_part)

        return {
            "tool": tool,
            "app": known_app or app_part
        }

    # Если сказали просто "paint" или "диспетчер задач" без глагола,
    # считаем, что хотят открыть приложение.
    known_app = normalize_known_app(text)

    if known_app:
        return {
            "tool": "open_app",
            "app": known_app
        }

    return None