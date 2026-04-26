from types import SimpleNamespace
from unittest.mock import patch
import unittest

import claim_cloud_id.main as app_main


class TestMainBootstrap(unittest.TestCase):
    def test_missing_org_lists_orgs_and_exits_zero(self):
        args = SimpleNamespace(
            action="check",
            batch_size=50,
            csv_path="cloud_id.csv",
            report_csv="inventory_check_report.csv",
            org_id=None,
            log_file=None,
        )

        with (
            patch("claim_cloud_id.main.parse_args", return_value=args),
            patch("claim_cloud_id.main.get_log_file_path", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.setup_file_logger", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.get_dashboard_api_key", return_value="api-key"),
            patch("claim_cloud_id.main.get_dashboard_client", return_value=object()),
            patch("claim_cloud_id.main.get_org_id", return_value=""),
            patch(
                "claim_cloud_id.main.list_accessible_orgs",
                return_value=(
                    True,
                    "found 2 organization(s)",
                    [{"name": "Org A", "id": "111"}, {"name": "Org B", "id": "222"}],
                ),
            ),
            patch("claim_cloud_id.main.emit_info") as mock_emit_info,
            patch("claim_cloud_id.main.emit_error") as _mock_emit_error,
        ):
            with self.assertRaises(SystemExit) as exc:
                app_main.main()

        self.assertEqual(exc.exception.code, 0)
        mock_emit_info.assert_any_call("- Org A: 111")
        mock_emit_info.assert_any_call("- Org B: 222")

    def test_missing_org_api_failure_exits_one(self):
        args = SimpleNamespace(
            action="check",
            batch_size=50,
            csv_path="cloud_id.csv",
            report_csv="inventory_check_report.csv",
            org_id=None,
            log_file=None,
        )

        with (
            patch("claim_cloud_id.main.parse_args", return_value=args),
            patch("claim_cloud_id.main.get_log_file_path", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.setup_file_logger", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.get_dashboard_api_key", return_value="api-key"),
            patch("claim_cloud_id.main.get_dashboard_client", return_value=object()),
            patch("claim_cloud_id.main.get_org_id", return_value=""),
            patch("claim_cloud_id.main.list_accessible_orgs", return_value=(False, "Meraki API error 403", None)),
            patch("claim_cloud_id.main.emit_error") as mock_emit_error,
        ):
            with self.assertRaises(SystemExit) as exc:
                app_main.main()

        self.assertEqual(exc.exception.code, 1)
        mock_emit_error.assert_any_call("[ERROR] Meraki API error 403")

    def test_check_action_delegates_to_workflow_with_report_path(self):
        args = SimpleNamespace(
            action="check",
            batch_size=50,
            csv_path="cloud_id.csv",
            report_csv="inventory_check_report.csv",
            org_id="123",
            log_file=None,
        )
        dashboard = object()

        with (
            patch("claim_cloud_id.main.parse_args", return_value=args),
            patch("claim_cloud_id.main.get_log_file_path", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.setup_file_logger", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.get_dashboard_api_key", return_value="api-key"),
            patch("claim_cloud_id.main.get_dashboard_client", return_value=dashboard),
            patch("claim_cloud_id.main.get_org_id", return_value="123"),
            patch("claim_cloud_id.main.get_action", return_value="check"),
            patch("claim_cloud_id.main.get_batch_size", return_value=50),
            patch("claim_cloud_id.main.load_cloud_ids_from_csv", return_value=["A", "B"]),
            patch("claim_cloud_id.main.get_report_csv_path", return_value="inventory_check_report.csv"),
            patch("claim_cloud_id.main.run_inventory_workflow", return_value=(True, "inventory check completed")) as mock_run,
            patch("claim_cloud_id.main.emit_info") as _mock_emit_info,
        ):
            app_main.main()

        mock_run.assert_called_once_with(
            dashboard,
            "123",
            "check",
            ["A", "B"],
            50,
            "inventory_check_report.csv",
        )

    def test_release_action_delegates_with_no_report_path(self):
        args = SimpleNamespace(
            action="release",
            batch_size=50,
            csv_path="cloud_id.csv",
            report_csv="inventory_check_report.csv",
            org_id="123",
            log_file=None,
        )
        dashboard = object()

        with (
            patch("claim_cloud_id.main.parse_args", return_value=args),
            patch("claim_cloud_id.main.get_log_file_path", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.setup_file_logger", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.get_dashboard_api_key", return_value="api-key"),
            patch("claim_cloud_id.main.get_dashboard_client", return_value=dashboard),
            patch("claim_cloud_id.main.get_org_id", return_value="123"),
            patch("claim_cloud_id.main.get_action", return_value="release"),
            patch("claim_cloud_id.main.get_batch_size", return_value=50),
            patch("claim_cloud_id.main.load_cloud_ids_from_csv", return_value=["A", "B"]),
            patch("claim_cloud_id.main.get_report_csv_path") as mock_get_report_path,
            patch("claim_cloud_id.main.run_inventory_workflow", return_value=(True, "inventory verification passed after release")) as mock_run,
            patch("claim_cloud_id.main.emit_info") as _mock_emit_info,
        ):
            app_main.main()

        mock_get_report_path.assert_not_called()
        mock_run.assert_called_once_with(
            dashboard,
            "123",
            "release",
            ["A", "B"],
            50,
            None,
        )

    def test_claim_action_delegates_with_no_report_path(self):
        args = SimpleNamespace(
            action="claim",
            batch_size=50,
            csv_path="cloud_id.csv",
            report_csv="inventory_check_report.csv",
            org_id="123",
            log_file=None,
        )
        dashboard = object()

        with (
            patch("claim_cloud_id.main.parse_args", return_value=args),
            patch("claim_cloud_id.main.get_log_file_path", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.setup_file_logger", return_value="meraki_inventory_actions.log"),
            patch("claim_cloud_id.main.get_dashboard_api_key", return_value="api-key"),
            patch("claim_cloud_id.main.get_dashboard_client", return_value=dashboard),
            patch("claim_cloud_id.main.get_org_id", return_value="123"),
            patch("claim_cloud_id.main.get_action", return_value="claim"),
            patch("claim_cloud_id.main.get_batch_size", return_value=50),
            patch("claim_cloud_id.main.load_cloud_ids_from_csv", return_value=["A", "B"]),
            patch("claim_cloud_id.main.get_report_csv_path") as mock_get_report_path,
            patch("claim_cloud_id.main.run_inventory_workflow", return_value=(True, "inventory verification passed after claim")) as mock_run,
            patch("claim_cloud_id.main.emit_info") as _mock_emit_info,
        ):
            app_main.main()

        mock_get_report_path.assert_not_called()
        mock_run.assert_called_once_with(
            dashboard,
            "123",
            "claim",
            ["A", "B"],
            50,
            None,
        )


if __name__ == "__main__":
    unittest.main()
