import os
import unittest
from unittest.mock import patch

from app.utils import openrouter


class OpenRouterApiKeyRotationTests(unittest.TestCase):
    def setUp(self):
        openrouter._key_index = 0

    def test_rotates_keys_in_order_and_wraps(self):
        environment = {
            "OPENROUTER_API_KEY_v1": "key-1",
            "OPENROUTER_API_KEY_v2": "key-2",
            "OPENROUTER_API_KEY_v3": "key-3",
        }

        with patch.dict(os.environ, environment, clear=True):
            keys = [
                openrouter.get_next_openrouter_api_key()
                for _ in range(4)
            ]

        self.assertEqual(keys, ["key-1", "key-2", "key-3", "key-1"])

    def test_rotates_only_configured_keys(self):
        environment = {
            "OPENROUTER_API_KEY_v1": "key-1",
            "OPENROUTER_API_KEY_v3": "key-3",
        }

        with patch.dict(os.environ, environment, clear=True):
            keys = [
                openrouter.get_next_openrouter_api_key()
                for _ in range(4)
            ]

        self.assertEqual(keys, ["key-1", "key-3", "key-1", "key-3"])

    def test_reuses_single_configured_key(self):
        environment = {
            "OPENROUTER_API_KEY_v1": "key-1",
        }

        with patch.dict(os.environ, environment, clear=True):
            keys = [
                openrouter.get_next_openrouter_api_key()
                for _ in range(3)
            ]

        self.assertEqual(keys, ["key-1", "key-1", "key-1"])

    def test_raises_when_no_keys_are_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                RuntimeError,
                "No OpenRouter API key configured",
            ):
                openrouter.get_next_openrouter_api_key()


if __name__ == "__main__":
    unittest.main()
