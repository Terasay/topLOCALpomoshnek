from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from screen import take_screenshot
from ollama_client import ask_ollama
from safety import is_safe_user_command, validate_action
from controller import execute_action
from quick_actions import get_quick_action


app = FastAPI()

app.mount("/web", StaticFiles(directory="web"), name="web")


class CommandRequest(BaseModel):
    command: str
    use_screenshot: bool = False
    auto_execute_ai: bool = False


@app.get("/")
def index():
    return FileResponse("web/index.html")


@app.post("/api/command")
def run_command(data: CommandRequest):
    command = data.command.strip()

    if not command:
        return {
            "ok": False,
            "type": "error",
            "message": "Пустая команда."
        }

    safe, reason = is_safe_user_command(command)
    if not safe:
        return {
            "ok": False,
            "type": "blocked",
            "message": reason
        }

    quick_action = get_quick_action(command)

    if quick_action:
        valid, reason = validate_action(quick_action)
        if not valid:
            return {
                "ok": False,
                "type": "blocked",
                "message": reason
            }

        execute_action(quick_action)

        return {
            "ok": True,
            "type": "quick",
            "message": "Быстрая команда выполнена автономно.",
            "action": quick_action
        }

    screenshot_path = None

    if data.use_screenshot:
        screenshot_path = take_screenshot()

    action = ask_ollama(command, screenshot_path)

    valid, reason = validate_action(action)
    if not valid:
        return {
            "ok": False,
            "type": "ai_refused",
            "message": reason,
            "action": action
        }

    if data.auto_execute_ai:
        execute_action(action)
        executed = True
    else:
        executed = False

    return {
        "ok": True,
        "type": "ai",
        "message": "Qwen предложил действие.",
        "action": action,
        "executed": executed
    }


@app.post("/api/execute")
def execute_confirmed_action(action: dict):
    valid, reason = validate_action(action)
    if not valid:
        return {
            "ok": False,
            "message": reason
        }

    execute_action(action)

    return {
        "ok": True,
        "message": "Действие выполнено.",
        "action": action
    }