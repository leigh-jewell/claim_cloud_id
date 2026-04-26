import argparse
import os

from claim_cloud_id.constants import DEFAULT_BATCH_SIZE, DEFAULT_REPORT_CSV


def get_action(cli_action: str | None) -> str:
    if cli_action:
        return cli_action

    action = input("Choose action [claim/release/check]: ").strip().lower()
    if action not in {"claim", "release", "check"}:
        raise ValueError("Action must be 'claim', 'release', or 'check'")
    return action


def get_report_csv_path(cli_report_csv: str | None) -> str:
    if cli_report_csv:
        return cli_report_csv

    user_value = input(f"Enter report CSV path [default {DEFAULT_REPORT_CSV}]: ").strip()
    return DEFAULT_REPORT_CSV if not user_value else user_value


def get_batch_size(cli_batch_size: int | None) -> int:
    if cli_batch_size is not None:
        batch_size = cli_batch_size
    else:
        env_batch_size = os.getenv("MERAKI_BATCH_SIZE")
        if env_batch_size:
            try:
                batch_size = int(env_batch_size)
            except ValueError as exc:
                raise ValueError("MERAKI_BATCH_SIZE must be a positive integer") from exc
        else:
            user_value = input(f"Enter batch size [default {DEFAULT_BATCH_SIZE}]: ").strip()
            try:
                batch_size = DEFAULT_BATCH_SIZE if not user_value else int(user_value)
            except ValueError:
                raise ValueError(f"Batch size must be a positive integer, got: {user_value!r}") from None

    if batch_size < 1:
        raise ValueError("Batch size must be greater than 0")
    return batch_size


def prompt_for_csv_path() -> str:
    csv_path = input("Enter path to CSV file with cloud IDs: ").strip()
    if not csv_path:
        raise ValueError("CSV path cannot be empty")
    return csv_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claim, release, or check Meraki cloud IDs from a CSV file")
    parser.add_argument(
        "--csv",
        dest="csv_path",
        help="Path to CSV file containing cloud IDs (header: cloud_id or serial)",
    )
    parser.add_argument(
        "--action",
        choices=("claim", "release", "check"),
        help="Inventory action to perform",
    )
    parser.add_argument(
        "--org-id",
        help="Meraki organization ID (or set MERAKI_ORG_ID)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Number of serials per API request (or set MERAKI_BATCH_SIZE)",
    )
    parser.add_argument(
        "--report-csv",
        help="Path for inventory check report CSV (used with --action check)",
    )
    parser.add_argument(
        "--log-file",
        help="Path to run log file (or set MERAKI_LOG_FILE)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Preview which devices would be acted on without making any inventory changes",
    )
    return parser.parse_args()
