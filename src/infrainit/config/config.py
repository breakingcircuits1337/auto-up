import json
import os
from pathlib import Path

INFRAINIT_DIR = Path.home() / ".infrainit"
STATE_FILE = INFRAINIT_DIR / "state.json"


def _ensure_dir():
    INFRAINIT_DIR.mkdir(parents=True, exist_ok=True)


def get_env(key: str) -> str | None:
    return os.environ.get(key)


def require_env(key: str) -> str:
    val = get_env(key)
    if not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val


def load_state() -> dict:
    _ensure_dir()
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict):
    _ensure_dir()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_app_state(name: str) -> dict | None:
    return load_state().get(name)


def set_app_state(name: str, data: dict):
    state = load_state()
    state[name] = data
    save_state(state)


def remove_app_state(name: str):
    state = load_state()
    state.pop(name, None)
    save_state(state)
