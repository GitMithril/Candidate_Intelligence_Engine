import os
import threading


_API_KEY_NAMES = (
    "OPENROUTER_API_KEY_v1",
    "OPENROUTER_API_KEY_v2",
    "OPENROUTER_API_KEY_v3",
)
_key_index = 0
_key_lock = threading.Lock()


def get_next_openrouter_api_key() -> str:
    """Return the next configured OpenRouter API key in round-robin order."""
    global _key_index

    with _key_lock:
        key_name = _API_KEY_NAMES[_key_index]
        api_key = os.environ.get(key_name)
        if not api_key:
            raise RuntimeError(f"{key_name} is not configured")

        _key_index = (_key_index + 1) % len(_API_KEY_NAMES)
        return api_key
