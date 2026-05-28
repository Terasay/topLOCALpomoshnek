import time
import pyautogui


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.2


def execute_action(action: dict):
    name = action.get("action")

    if name == "move_mouse":
        pyautogui.moveTo(action["x"], action["y"], duration=0.2)

    elif name == "click":
        pyautogui.click(
            x=action["x"],
            y=action["y"],
            button=action.get("button", "left")
        )

    elif name == "type_text":
        pyautogui.write(action["text"], interval=0.02)

    elif name == "press_key":
        pyautogui.press(action["key"])

    elif name == "hotkey":
        pyautogui.hotkey(*action["keys"])

    elif name == "wait":
        time.sleep(float(action.get("seconds", 1)))

    elif name == "screenshot":
        print("Скриншот уже сделан перед запросом.")