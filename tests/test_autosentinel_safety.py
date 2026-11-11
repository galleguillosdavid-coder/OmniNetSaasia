import unittest
from unittest.mock import MagicMock, patch

from netopt.auto_trigger import AutoSentinel


class TestAutoSentinelSafety(unittest.TestCase):

    @patch("netopt.auto_trigger.get_hal")
    def test_live_actions_disabled_by_default(self, mock_get_hal):
        hal = MagicMock()
        hal.dry_run = False
        mock_get_hal.return_value = hal

        with patch.dict("os.environ", {}, clear=True):
            sentinel = AutoSentinel()

        self.assertFalse(sentinel.enabled)
        self.assertFalse(sentinel.allow_live_actions)
        self.assertTrue(hal.dry_run)

    @patch("netopt.auto_trigger.get_hal")
    def test_live_actions_require_explicit_authorization(self, mock_get_hal):
        hal = MagicMock()
        hal.dry_run = False
        mock_get_hal.return_value = hal

        with patch.dict("os.environ", {}, clear=True):
            sentinel = AutoSentinel(
                hal=hal,
                allow_live_actions=False
            )

        self.assertFalse(sentinel.allow_live_actions)
        self.assertTrue(hal.dry_run)

    @patch("netopt.auto_trigger.get_hal")
    def test_explicit_authorization_does_not_enable_sentinel(self, mock_get_hal):
        hal = MagicMock()
        hal.dry_run = False
        mock_get_hal.return_value = hal

        sentinel = AutoSentinel(
            hal=hal,
            enabled=False,
            allow_live_actions=True
        )

        self.assertTrue(sentinel.allow_live_actions)
        self.assertFalse(sentinel.enabled)


if __name__ == "__main__":
    unittest.main()
