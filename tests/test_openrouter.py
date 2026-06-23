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

    def test_missing_key_does_not_advance_rotation(self):
        environment = {
            "OPENROUTER_API_KEY_v1": "key-1",
            "OPENROUTER_API_KEY_v3": "key-3",
        }

        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(openrouter.get_next_openrouter_api_key(), "key-1")
            with self.assertRaisesRegex(
                RuntimeError,
                "OPENROUTER_API_KEY_v2 is not configured",
            ):
                openrouter.get_next_openrouter_api_key()

            with self.assertRaisesRegex(
                RuntimeError,
                "OPENROUTER_API_KEY_v2 is not configured",
            ):
                openrouter.get_next_openrouter_api_key()


if __name__ == "__main__":
    unittest.main()
