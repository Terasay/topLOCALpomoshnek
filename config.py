OLLAMA_MODEL = "qwen2.5vl:3b"
OLLAMA_URL = "http://localhost:11434/api/generate"

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