from unittest.mock import patch
import unittest

from claim_cloud_id.orchestrator import run_inventory_workflow


class TestRunInventoryWorkflow(unittest.TestCase):
    def setUp(self):
        self.dashboard = object()
        self.org_id = "123"
        self.cloud_ids = ["A", "B"]
        self.batch_size = 50

    def test_check_requires_report_path(self):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "check",
            self.cloud_ids,
            self.batch_size,
            None,
        )

        self.assertFalse(success)
        self.assertEqual(message, "report CSV path is required for check action")

    @patch("claim_cloud_id.orchestrator.check_cloud_ids_in_inventory", return_value=(True, "inventory check completed"))
    def test_check_success(self, mock_check):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "check",
            self.cloud_ids,
            self.batch_size,
            "report.csv",
        )

        self.assertTrue(success)
        self.assertEqual(message, "inventory check completed")
        mock_check.assert_called_once_with(
            self.dashboard,
            self.org_id,
            self.cloud_ids,
            self.batch_size,
            "report.csv",
        )

    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A", "B"}),
    )
    def test_claim_no_claimable_devices(self, mock_get_inventory):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "claim",
            self.cloud_ids,
            self.batch_size,
        )

        self.assertTrue(success)
        self.assertEqual(message, "no claimable cloud IDs")
        mock_get_inventory.assert_called_once()

    @patch(
        "claim_cloud_id.orchestrator.get_network_bound_cloud_ids",
        return_value=(True, "checked", ["A"]),
    )
    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A", "B"}),
    )
    def test_release_blocked_by_network_binding(self, _mock_inventory, _mock_bound):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "release",
            self.cloud_ids,
            self.batch_size,
        )

        self.assertFalse(success)
        self.assertEqual(message, "release blocked due to network-bound devices")

    @patch(
        "claim_cloud_id.orchestrator.verify_inventory_update",
        return_value=(True, "inventory verification passed after claim", []),
    )
    @patch(
        "claim_cloud_id.orchestrator.run_inventory_action_in_batches",
        return_value=(True, "claimed 1 serial(s)", ["B"], 50),
    )
    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A"}),
    )
    def test_claim_executes_with_filtered_cloud_ids(self, mock_inventory, mock_run_batches, _mock_verify):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "claim",
            self.cloud_ids,
            self.batch_size,
        )

        self.assertTrue(success)
        self.assertEqual(message, "inventory verification passed after claim")
        mock_inventory.assert_called_once()
        mock_run_batches.assert_called_once_with(
            self.dashboard,
            self.org_id,
            ["B"],
            "claim",
            self.batch_size,
        )

    def test_unsupported_action(self):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "delete",
            self.cloud_ids,
            self.batch_size,
        )

        self.assertFalse(success)
        self.assertEqual(message, "unsupported action: delete")

    @patch(
        "claim_cloud_id.orchestrator.run_inventory_action_in_batches",
        return_value=(False, "Meraki API error 400: invalid serial", None, 50),
    )
    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A"}),
    )
    def test_claim_batch_action_failure(self, _mock_inventory, _mock_run_batches):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "claim",
            self.cloud_ids,
            self.batch_size,
        )

        self.assertFalse(success)
        self.assertEqual(message, "Meraki API error 400: invalid serial")

    @patch(
        "claim_cloud_id.orchestrator.verify_inventory_update",
        return_value=(True, "inventory verification passed after claim", []),
    )
    @patch(
        "claim_cloud_id.orchestrator.run_inventory_action_in_batches",
        return_value=(True, "claimed 1 serial(s)", [], 50),
    )
    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A"}),
    )
    def test_claim_serial_mismatch_after_batch_response(self, _mock_inventory, _mock_run_batches, _mock_verify):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "claim",
            self.cloud_ids,
            self.batch_size,
        )

        self.assertFalse(success)
        self.assertEqual(message, "serial mismatch in API response")

    @patch(
        "claim_cloud_id.orchestrator.verify_inventory_update",
        return_value=(False, "inventory verification failed after claim", ["B"]),
    )
    @patch(
        "claim_cloud_id.orchestrator.run_inventory_action_in_batches",
        return_value=(True, "claimed 1 serial(s)", ["B"], 50),
    )
    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A"}),
    )
    def test_claim_verification_failure(self, _mock_inventory, _mock_run_batches, _mock_verify):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "claim",
            self.cloud_ids,
            self.batch_size,
        )

        self.assertFalse(success)
        self.assertEqual(message, "inventory verification failed after claim")

    # ── dry-run ───────────────────────────────────────────────────────────────

    @patch("claim_cloud_id.orchestrator.emit_info")
    def test_dry_run_check_skips_api_call(self, mock_emit):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "check",
            self.cloud_ids,
            self.batch_size,
            report_csv_path="report.csv",
            dry_run=True,
        )

        self.assertTrue(success)
        self.assertIn("dry run", message)
        mock_emit.assert_called()

    @patch("claim_cloud_id.orchestrator.emit_info")
    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A"}),
    )
    def test_dry_run_claim_prints_preview_and_skips_execute(self, _mock_inventory, mock_emit):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "claim",
            self.cloud_ids,
            self.batch_size,
            dry_run=True,
        )

        self.assertTrue(success)
        self.assertIn("dry run", message)
        self.assertIn("claim", message)
        # "B" is the only claimable ID ("A" is already in inventory)
        printed = [call.args[0] for call in mock_emit.call_args_list]
        self.assertTrue(any("B" in s for s in printed))

    @patch("claim_cloud_id.orchestrator.emit_info")
    @patch(
        "claim_cloud_id.orchestrator.get_network_bound_cloud_ids",
        return_value=(True, "checked", []),
    )
    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A", "B"}),
    )
    def test_dry_run_release_prints_preview_and_skips_execute(self, _mock_inventory, _mock_bound, mock_emit):
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "release",
            self.cloud_ids,
            self.batch_size,
            dry_run=True,
        )

        self.assertTrue(success)
        self.assertIn("dry run", message)
        self.assertIn("release", message)

    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A", "B"}),
    )
    def test_dry_run_claim_all_already_in_inventory_returns_no_claimable(self, _mock_inventory):
        """When all IDs are already in inventory there's nothing to claim even in dry-run."""
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "claim",
            self.cloud_ids,
            self.batch_size,
            dry_run=True,
        )

        self.assertTrue(success)
        self.assertEqual(message, "no claimable cloud IDs")

    @patch(
        "claim_cloud_id.orchestrator.get_network_bound_cloud_ids",
        return_value=(True, "checked", ["A"]),
    )
    @patch(
        "claim_cloud_id.orchestrator.get_inventory_serials_for_cloud_ids",
        return_value=(True, "ok", {"A", "B"}),
    )
    def test_dry_run_release_blocked_by_network_still_fails(self, _mock_inventory, _mock_bound):
        """Network-bound check still runs and blocks release even in dry-run."""
        success, message = run_inventory_workflow(
            self.dashboard,
            self.org_id,
            "release",
            self.cloud_ids,
            self.batch_size,
            dry_run=True,
        )

        self.assertFalse(success)
        self.assertEqual(message, "release blocked due to network-bound devices")


if __name__ == "__main__":
    unittest.main()
