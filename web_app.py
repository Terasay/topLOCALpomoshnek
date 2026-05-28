from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from safety import is_safe_user_command
from agent_client import plan_command
from tools import execute_tool_call


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

    try:
        tool_call = plan_command(command)
    except Exception as e:
        return {
            "ok": False,
            "type": "planner_error",
            "message": f"Ошибка планирования: {e}"
        }

    if tool_call.get("tool") == "refuse":
        return {
            "ok": False,
            "type": "refuse",
            "message": tool_call.get("reason", "Модель отказалась."),
            "action": tool_call
        }

    try:
        execute_tool_call(tool_call)
    except Exception as e:
        return {
            "ok": False,
            "type": "execute_error",
            "message": f"Ошибка выполнения: {e}",
            "action": tool_call
        }

    return {
        "ok": True,
        "type": "tool",
        "message": "Инструмент выполнен.",
        "action": tool_call,
        "executed": True
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