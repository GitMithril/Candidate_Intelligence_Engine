import os
import threading


_API_KEY_NAMES = (
    "OPENROUTER_API_KEY_v1",
    "OPENROUTER_API_KEY_v2",
    "OPENROUTER_API_KEY_v3",
)
_key_index = 0
_key_lock = threading.Lock()


def _configured_api_keys() -> list[tuple[str, str]]:
    return [
        (key_name, api_key)
        for key_name in _API_KEY_NAMES
        if (api_key := os.environ.get(key_name))
    ]


def get_next_openrouter_api_key() -> str:
    """Return the next configured OpenRouter API key in round-robin order."""
    global _key_index

    with _key_lock:
        configured_keys = _configured_api_keys()
        if not configured_keys:
            names = ", ".join(_API_KEY_NAMES)
            raise RuntimeError(f"No OpenRouter API key configured. Set one of: {names}")

        _key_index %= len(configured_keys)
        _key_name, api_key = configured_keys[_key_index]
        _key_index = (_key_index + 1) % len(configured_keys)
        return api_key
