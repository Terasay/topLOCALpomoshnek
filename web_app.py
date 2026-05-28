from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from safety import is_safe_user_command
from quick_actions import get_quick_action
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

    # 1. Сначала быстрые локальные команды без Qwen
    quick_action = get_quick_action(command)

    if quick_action:
        try:
            execute_tool_call(quick_action)
        except Exception as e:
            return {
                "ok": False,
                "type": "quick_execute_error",
                "message": f"Ошибка выполнения быстрой команды: {e}",
                "action": quick_action
            }

        return {
            "ok": True,
            "type": "quick",
            "message": "Быстрая команда выполнена.",
            "action": quick_action,
            "executed": True
        }

    # 2. Если быстрой команды нет, тогда уже спрашиваем Qwen
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

    # Пока выполняем Qwen-команды автоматически.
    # Если станет страшно, вернём подтверждение.
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
    try:
        execute_tool_call(action)
    except Exception as e:
        return {
            "ok": False,
            "message": f"Ошибка выполнения: {e}",
            "action": action
        }

    return {
        "ok": True,
        "message": "Действие выполнено.",
        "action": action
    }