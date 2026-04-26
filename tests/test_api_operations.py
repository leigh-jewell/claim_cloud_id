import unittest
from unittest.mock import MagicMock, patch, call

import meraki

from claim_cloud_id.api_operations import (
    get_inventory_devices_for_cloud_ids,
    get_network_bound_cloud_ids,
    get_inventory_serials_for_cloud_ids,
    run_inventory_action,
    run_inventory_action_in_batches,
    list_accessible_orgs,
)
from claim_cloud_id.constants import SAFE_MAX_BATCH_SIZE


def _make_api_error(status: int = 400, message: str = "bad request") -> meraki.APIError:
    """Construct a meraki.APIError without making a real request."""
    exc = meraki.APIError.__new__(meraki.APIError)
    exc.status = status
    exc.message = {"errors": [message]}
    exc.reason = message
    exc.args = (message,)
    return exc


# ── list_accessible_orgs ──────────────────────────────────────────────────────

class TestListAccessibleOrgs(unittest.TestCase):
    def _dashboard(self):
        return MagicMock()

    def test_returns_org_list_on_success(self):
        dashboard = self._dashboard()
        orgs = [{"id": "1", "name": "Org A"}]
        dashboard.organizations.getOrganizations.return_value = orgs

        ok, msg, result = list_accessible_orgs(dashboard)

        self.assertTrue(ok)
        self.assertIn("1", msg)
        self.assertEqual(result, orgs)

    def test_api_error_returns_false(self):
        dashboard = self._dashboard()
        dashboard.organizations.getOrganizations.side_effect = _make_api_error(403, "forbidden")

        ok, msg, result = list_accessible_orgs(dashboard)

        self.assertFalse(ok)
        self.assertIn("403", msg)
        self.assertIsNone(result)

    def test_unexpected_exception_returns_false(self):
        dashboard = self._dashboard()
        dashboard.organizations.getOrganizations.side_effect = RuntimeError("network down")

        ok, msg, result = list_accessible_orgs(dashboard)

        self.assertFalse(ok)
        self.assertIn("Unexpected", msg)
        self.assertIsNone(result)

    def test_non_list_response_returns_false(self):
        dashboard = self._dashboard()
        dashboard.organizations.getOrganizations.return_value = {"unexpected": "dict"}

        ok, msg, result = list_accessible_orgs(dashboard)

        self.assertFalse(ok)
        self.assertIn("Unexpected SDK response type", msg)


# ── run_inventory_action ──────────────────────────────────────────────────────

class TestRunInventoryAction(unittest.TestCase):
    def _dashboard(self):
        return MagicMock()

    def test_claim_success(self):
        dashboard = self._dashboard()
        dashboard.organizations.claimIntoOrganizationInventory.return_value = {
            "serials": ["AAA-1111", "BBB-2222"]
        }

        ok, msg, response = run_inventory_action(dashboard, "org1", ["AAA-1111", "BBB-2222"], action="claim")

        self.assertTrue(ok)
        self.assertIn("2", msg)
        self.assertIsNotNone(response)

    def test_release_success(self):
        dashboard = self._dashboard()
        dashboard.organizations.releaseFromOrganizationInventory.return_value = {
            "serials": ["AAA-1111"]
        }

        ok, msg, response = run_inventory_action(dashboard, "org1", ["AAA-1111"], action="release")

        self.assertTrue(ok)
        self.assertIn("1", msg)

    def test_api_error_returns_false(self):
        dashboard = self._dashboard()
        dashboard.organizations.claimIntoOrganizationInventory.side_effect = _make_api_error(400, "bad serial")

        ok, msg, response = run_inventory_action(dashboard, "org1", ["BAD"], action="claim")

        self.assertFalse(ok)
        self.assertIn("400", msg)
        self.assertIsNone(response)

    def test_unexpected_exception_returns_false(self):
        dashboard = self._dashboard()
        dashboard.organizations.claimIntoOrganizationInventory.side_effect = RuntimeError("boom")

        ok, msg, response = run_inventory_action(dashboard, "org1", ["AAA"], action="claim")

        self.assertFalse(ok)
        self.assertIn("Unexpected", msg)

    def test_non_dict_response_returns_false(self):
        dashboard = self._dashboard()
        dashboard.organizations.claimIntoOrganizationInventory.return_value = ["not", "a", "dict"]

        ok, msg, response = run_inventory_action(dashboard, "org1", ["AAA"], action="claim")

        self.assertFalse(ok)
        self.assertIn("Unexpected SDK response type", msg)

    def test_response_missing_serials_key_returns_false(self):
        dashboard = self._dashboard()
        dashboard.organizations.claimIntoOrganizationInventory.return_value = {"other": "data"}

        ok, msg, response = run_inventory_action(dashboard, "org1", ["AAA"], action="claim")

        self.assertFalse(ok)
        self.assertIn("missing 'serials'", msg)

    def test_response_serials_not_list_returns_false(self):
        dashboard = self._dashboard()
        dashboard.organizations.claimIntoOrganizationInventory.return_value = {"serials": "not-a-list"}

        ok, msg, response = run_inventory_action(dashboard, "org1", ["AAA"], action="claim")

        self.assertFalse(ok)
        self.assertIn("not a list", msg)


# ── run_inventory_action_in_batches ───────────────────────────────────────────

class TestRunInventoryActionInBatches(unittest.TestCase):
    def _dashboard(self):
        return MagicMock()

    @patch("claim_cloud_id.api_operations.run_inventory_action")
    def test_single_batch_success(self, mock_action):
        mock_action.return_value = (True, "claimed 2 serial(s)", {"serials": ["A", "B"]})
        dashboard = self._dashboard()

        ok, msg, serials, eff_size = run_inventory_action_in_batches(
            dashboard, "org1", ["A", "B"], "claim", requested_batch_size=50
        )

        self.assertTrue(ok)
        self.assertEqual(serials, ["A", "B"])
        self.assertEqual(eff_size, 50)
        mock_action.assert_called_once_with(dashboard, "org1", ["A", "B"], "claim")

    @patch("claim_cloud_id.api_operations.run_inventory_action")
    def test_multiple_batches_accumulated(self, mock_action):
        mock_action.side_effect = [
            (True, "ok", {"serials": ["A", "B"]}),
            (True, "ok", {"serials": ["C"]}),
        ]
        dashboard = self._dashboard()
        cloud_ids = ["A", "B", "C"]

        ok, msg, serials, eff_size = run_inventory_action_in_batches(
            dashboard, "org1", cloud_ids, "claim", requested_batch_size=2
        )

        self.assertTrue(ok)
        self.assertEqual(serials, ["A", "B", "C"])
        self.assertEqual(mock_action.call_count, 2)

    @patch("claim_cloud_id.api_operations.emit_info")
    @patch("claim_cloud_id.api_operations.run_inventory_action")
    def test_backoff_triggered_on_first_failure(self, mock_action, mock_emit):
        """Failure at large batch size should trigger one retry at SAFE_MAX_BATCH_SIZE."""
        large_size = SAFE_MAX_BATCH_SIZE + 1
        cloud_ids = ["A"]
        mock_action.side_effect = [
            (False, "API error", None),           # first attempt at large_size → fail
            (True, "ok", {"serials": ["A"]}),     # retry at SAFE_MAX_BATCH_SIZE → succeed
        ]
        dashboard = self._dashboard()

        ok, msg, serials, eff_size = run_inventory_action_in_batches(
            dashboard, "org1", cloud_ids, "claim", requested_batch_size=large_size
        )

        self.assertTrue(ok)
        self.assertEqual(eff_size, SAFE_MAX_BATCH_SIZE)
        self.assertEqual(mock_action.call_count, 2)
        mock_emit.assert_called_once()

    @patch("claim_cloud_id.api_operations.run_inventory_action")
    def test_backoff_not_triggered_second_time(self, mock_action):
        """Once backoff is used, a second failure should propagate as an error."""
        large_size = SAFE_MAX_BATCH_SIZE + 1
        cloud_ids = ["A"]
        mock_action.side_effect = [
            (False, "first failure", None),
            (False, "second failure", None),
        ]
        dashboard = self._dashboard()

        ok, msg, serials, eff_size = run_inventory_action_in_batches(
            dashboard, "org1", cloud_ids, "claim", requested_batch_size=large_size
        )

        self.assertFalse(ok)
        self.assertIn("second failure", msg)

    @patch("claim_cloud_id.api_operations.run_inventory_action")
    def test_failure_at_safe_batch_size_returns_error(self, mock_action):
        """Failure at or below SAFE_MAX_BATCH_SIZE should not trigger backoff."""
        mock_action.return_value = (False, "API error", None)
        dashboard = self._dashboard()

        ok, msg, serials, eff_size = run_inventory_action_in_batches(
            dashboard, "org1", ["A"], "claim", requested_batch_size=SAFE_MAX_BATCH_SIZE
        )

        self.assertFalse(ok)
        self.assertIsNone(serials)
        mock_action.assert_called_once()


# ── get_inventory_devices_for_cloud_ids (batch loop + backoff) ────────────────

class TestGetInventoryDevicesForCloudIds(unittest.TestCase):
    def _dashboard(self):
        return MagicMock()

    @patch("claim_cloud_id.api_operations.get_inventory_devices")
    def test_successful_single_batch(self, mock_get):
        devices = [{"serial": "A"}, {"serial": "B"}]
        mock_get.return_value = (True, "ok", devices)
        dashboard = self._dashboard()

        ok, msg, result = get_inventory_devices_for_cloud_ids(dashboard, "org1", ["A", "B"], batch_size=50)

        self.assertTrue(ok)
        self.assertEqual(result, devices)
        mock_get.assert_called_once()

    @patch("claim_cloud_id.api_operations.get_inventory_devices")
    def test_multiple_batches_combined(self, mock_get):
        mock_get.side_effect = [
            (True, "ok", [{"serial": "A"}]),
            (True, "ok", [{"serial": "B"}]),
        ]
        dashboard = self._dashboard()

        ok, msg, result = get_inventory_devices_for_cloud_ids(
            dashboard, "org1", ["A", "B"], batch_size=1
        )

        self.assertTrue(ok)
        self.assertEqual(len(result), 2)

    @patch("claim_cloud_id.api_operations.emit_info")
    @patch("claim_cloud_id.api_operations.get_inventory_devices")
    def test_backoff_then_success(self, mock_get, mock_emit):
        large_size = SAFE_MAX_BATCH_SIZE + 10
        mock_get.side_effect = [
            (False, "error", None),
            (True, "ok", [{"serial": "A"}]),
        ]
        dashboard = self._dashboard()

        ok, msg, result = get_inventory_devices_for_cloud_ids(
            dashboard, "org1", ["A"], batch_size=large_size
        )

        self.assertTrue(ok)
        self.assertEqual(mock_get.call_count, 2)
        mock_emit.assert_called_once()

    @patch("claim_cloud_id.api_operations.get_inventory_devices")
    def test_failure_after_backoff_returns_error(self, mock_get):
        large_size = SAFE_MAX_BATCH_SIZE + 10
        mock_get.side_effect = [
            (False, "first error", None),
            (False, "second error", None),
        ]
        dashboard = self._dashboard()

        ok, msg, result = get_inventory_devices_for_cloud_ids(
            dashboard, "org1", ["A"], batch_size=large_size
        )

        self.assertFalse(ok)
        self.assertIn("second error", msg)


# ── get_network_bound_cloud_ids ───────────────────────────────────────────────

class TestGetNetworkBoundCloudIds(unittest.TestCase):
    def _dashboard(self):
        return MagicMock()

    @patch("claim_cloud_id.api_operations.get_inventory_devices_for_cloud_ids")
    def test_returns_only_network_bound_serials(self, mock_batch):
        mock_batch.return_value = (
            True,
            "ok",
            [
                {"serial": "A", "networkId": "net-1"},
                {"serial": "B", "networkId": None},
                {"serial": "C", "networkId": "net-2"},
            ],
        )
        dashboard = self._dashboard()

        ok, msg, bound = get_network_bound_cloud_ids(dashboard, "org1", ["A", "B", "C"], batch_size=50)

        self.assertTrue(ok)
        self.assertEqual(sorted(bound), ["A", "C"])

    @patch("claim_cloud_id.api_operations.get_inventory_devices_for_cloud_ids")
    def test_excludes_serials_not_in_input_list(self, mock_batch):
        mock_batch.return_value = (
            True,
            "ok",
            [{"serial": "EXTRA", "networkId": "net-1"}],
        )
        dashboard = self._dashboard()

        ok, msg, bound = get_network_bound_cloud_ids(dashboard, "org1", ["A"], batch_size=50)

        self.assertTrue(ok)
        self.assertEqual(bound, [])

    @patch("claim_cloud_id.api_operations.get_inventory_devices_for_cloud_ids")
    def test_propagates_batch_failure(self, mock_batch):
        mock_batch.return_value = (False, "API error", None)
        dashboard = self._dashboard()

        ok, msg, bound = get_network_bound_cloud_ids(dashboard, "org1", ["A"], batch_size=50)

        self.assertFalse(ok)
        self.assertIsNone(bound)


# ── get_inventory_serials_for_cloud_ids ───────────────────────────────────────

class TestGetInventorySerials(unittest.TestCase):
    def _dashboard(self):
        return MagicMock()

    @patch("claim_cloud_id.api_operations.get_inventory_devices_for_cloud_ids")
    def test_returns_serial_set(self, mock_batch):
        mock_batch.return_value = (
            True,
            "ok",
            [{"serial": "A"}, {"serial": "B"}, {"serial": None}],
        )
        dashboard = self._dashboard()

        ok, msg, serials = get_inventory_serials_for_cloud_ids(dashboard, "org1", ["A", "B"], batch_size=50)

        self.assertTrue(ok)
        self.assertEqual(serials, {"A", "B"})

    @patch("claim_cloud_id.api_operations.get_inventory_devices_for_cloud_ids")
    def test_propagates_failure(self, mock_batch):
        mock_batch.return_value = (False, "fail", None)
        dashboard = self._dashboard()

        ok, msg, serials = get_inventory_serials_for_cloud_ids(dashboard, "org1", ["A"], batch_size=50)

        self.assertFalse(ok)
        self.assertIsNone(serials)


if __name__ == "__main__":
    unittest.main()
