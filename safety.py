from config import ALLOWED_ACTIONS


DANGEROUS_WORDS = [
    "удали",
    "сотри",
    "форматируй",
    "format",
    "delete",
    "powershell",
    "cmd",
    "regedit",
    "реестр",
    "пароль",
    "password",
    "оплати",
    "купи",
]


def is_safe_user_command(text: str) -> tuple[bool, str]:
    lowered = text.lower()

    for word in DANGEROUS_WORDS:
        if word in lowered:
            return False, f"Команда содержит опасное слово: {word}"

    return True, "ok"


def validate_action(action: dict) -> tuple[bool, str]:
    action_name = action.get("action")

    if action_name == "refuse":
        return False, action.get("reason", "Модель отказалась выполнять команду")

    if action_name not in ALLOWED_ACTIONS:
        return False, f"Действие запрещено: {action_name}"

    return True, "ok"