import unittest
from unittest.mock import patch

from claim_cloud_id.cli import get_action, get_batch_size
from claim_cloud_id.constants import DEFAULT_BATCH_SIZE, SAFE_MAX_BATCH_SIZE


# ── get_action ────────────────────────────────────────────────────────────────

class TestGetAction(unittest.TestCase):
    def test_returns_cli_action_when_provided(self):
        self.assertEqual(get_action("claim"), "claim")
        self.assertEqual(get_action("release"), "release")
        self.assertEqual(get_action("check"), "check")

    def test_none_cli_prompts_user(self):
        with patch("claim_cloud_id.cli.input", return_value="claim"):
            result = get_action(None)
        self.assertEqual(result, "claim")

    def test_prompt_strips_and_lowercases_input(self):
        with patch("claim_cloud_id.cli.input", return_value="  RELEASE  "):
            result = get_action(None)
        self.assertEqual(result, "release")

    def test_invalid_prompt_input_raises_value_error(self):
        with patch("claim_cloud_id.cli.input", return_value="delete"):
            with self.assertRaises(ValueError) as ctx:
                get_action(None)
        self.assertIn("claim", str(ctx.exception))
        self.assertIn("release", str(ctx.exception))
        self.assertIn("check", str(ctx.exception))

    def test_empty_prompt_input_raises_value_error(self):
        with patch("claim_cloud_id.cli.input", return_value=""):
            with self.assertRaises(ValueError):
                get_action(None)


# ── get_batch_size ────────────────────────────────────────────────────────────

class TestGetBatchSize(unittest.TestCase):
    def _clear_env(self, env):
        env.pop("MERAKI_BATCH_SIZE", None)

    # cli argument path
    def test_cli_value_returned_directly(self):
        self.assertEqual(get_batch_size(10), 10)

    def test_cli_value_at_boundary(self):
        self.assertEqual(get_batch_size(1), 1)

    def test_cli_zero_raises(self):
        with self.assertRaises(ValueError):
            get_batch_size(0)

    def test_cli_negative_raises(self):
        with self.assertRaises(ValueError):
            get_batch_size(-5)

    # env-var path
    def test_env_var_used_when_no_cli(self):
        with patch.dict("os.environ", {"MERAKI_BATCH_SIZE": "75"}, clear=False):
            result = get_batch_size(None)
        self.assertEqual(result, 75)

    def test_env_var_non_integer_raises(self):
        with patch.dict("os.environ", {"MERAKI_BATCH_SIZE": "abc"}, clear=False):
            with self.assertRaises(ValueError) as ctx:
                get_batch_size(None)
        self.assertIn("MERAKI_BATCH_SIZE", str(ctx.exception))

    def test_env_var_zero_raises(self):
        with patch.dict("os.environ", {"MERAKI_BATCH_SIZE": "0"}, clear=False):
            with self.assertRaises(ValueError):
                get_batch_size(None)

    # interactive prompt path
    def test_empty_input_returns_default(self):
        with patch.dict("os.environ", {}, clear=False) as env:
            self._clear_env(env)
            with patch("claim_cloud_id.cli.input", return_value=""):
                result = get_batch_size(None)
        self.assertEqual(result, DEFAULT_BATCH_SIZE)

    def test_valid_input_returned(self):
        with patch.dict("os.environ", {}, clear=False) as env:
            self._clear_env(env)
            with patch("claim_cloud_id.cli.input", return_value="25"):
                result = get_batch_size(None)
        self.assertEqual(result, 25)

    def test_non_integer_input_raises(self):
        with patch.dict("os.environ", {}, clear=False) as env:
            self._clear_env(env)
            with patch("claim_cloud_id.cli.input", return_value="abc"):
                with self.assertRaises(ValueError) as ctx:
                    get_batch_size(None)
        self.assertIn("positive integer", str(ctx.exception))

    def test_zero_input_raises(self):
        with patch.dict("os.environ", {}, clear=False) as env:
            self._clear_env(env)
            with patch("claim_cloud_id.cli.input", return_value="0"):
                with self.assertRaises(ValueError):
                    get_batch_size(None)

    def test_negative_input_raises(self):
        with patch.dict("os.environ", {}, clear=False) as env:
            self._clear_env(env)
            with patch("claim_cloud_id.cli.input", return_value="-1"):
                with self.assertRaises(ValueError):
                    get_batch_size(None)

    def test_whitespace_input_returns_default(self):
        """Whitespace-only input should behave like empty input and return default."""
        with patch.dict("os.environ", {}, clear=False) as env:
            self._clear_env(env)
            with patch("claim_cloud_id.cli.input", return_value="   "):
                result = get_batch_size(None)
        self.assertEqual(result, DEFAULT_BATCH_SIZE)


if __name__ == "__main__":
    unittest.main()
