OLLAMA_PLANNER_MODEL = "qwen2.5:1.5b"
OLLAMA_VISION_MODEL = "qwen2.5vl:3b"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

REQUIRE_CONFIRMATION = True

ALLOWED_ACTIONS = {
    "move_mouse",
    "click",
    "type_text",
    "press_key",
    "hotkey",
    "screenshot",
    "wait"
}