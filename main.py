from screen import take_screenshot
from ollama_client import ask_ollama
from safety import is_safe_user_command, validate_action
from controller import execute_action
from config import REQUIRE_CONFIRMATION


def main():
    print("AI Assistant запущен.")
    print("Для выхода напиши: exit")
    print("Для аварийной остановки pyautogui уведи мышь в левый верхний угол экрана.")
    print()

    while True:
        user_command = input("Команда > ").strip()

        if user_command.lower() in ["exit", "quit", "выход"]:
            break

        safe, reason = is_safe_user_command(user_command)
        if not safe:
            print(f"Блокировано: {reason}")
            continue

        screenshot_path = None
        print("Думаю без скриншота...")

        action = ask_ollama(user_command, screenshot_path)

        print("Модель предложила:")
        print(action)

        valid, reason = validate_action(action)
        if not valid:
            print(f"Не выполнено: {reason}")
            continue

        if REQUIRE_CONFIRMATION:
            confirm = input("Выполнить? y/n > ").strip().lower()
            if confirm != "y":
                print("Отменено.")
                continue

        execute_action(action)
        print("Готово.")


if __name__ == "__main__":
    main()