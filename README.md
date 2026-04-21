# claim-cloud-id

## Environment variables

This project loads variables from a local `.env` file (using `python-dotenv`).

1. Copy `.env.example` to `.env`.
2. Set your real API key in `.env`:

```env
MERAKI_DASHBOARD_API_KEY=your_real_key_here
MERAKI_ORG_ID=123456
MERAKI_BATCH_SIZE=50
MERAKI_LOG_FILE=meraki_inventory_actions.log
```

`.env` is ignored by Git, so secrets are not committed.

## Manage cloud IDs from CSV

The script reads cloud IDs (serials) from a CSV file and can claim them, release them, or check whether they exist in inventory.

Preferred CSV header is `cloud_id` or `serial`. If neither exists, the first non-empty column value per row is used.

The script uses the Meraki Python SDK methods `claimIntoOrganizationInventory`, `releaseFromOrganizationInventory`, and `getOrganizationInventoryDevices`.

For `release`, the script first checks whether any CSV cloud IDs are currently bound to a network (`networkId` present in inventory). If any are bound, it prints those cloud IDs and exits without attempting release.

For `release`, the script also checks whether each CSV cloud ID exists in inventory before release. Any cloud IDs not found are printed as informational output and skipped, while existing cloud IDs continue through the release flow.

For `claim`, the script checks whether each CSV cloud ID already exists in inventory before claim. Any already-existing cloud IDs are printed as informational output and skipped, while missing cloud IDs continue through the claim flow.

After a claim or release request succeeds, the script automatically checks organization inventory using `getOrganizationInventoryDevices` to verify the serials are present after claim or absent after release.

Run with command line options:

```bash
uv run python main.py --action claim --csv devices.csv --org-id 123456
uv run python main.py --action release --csv devices.csv --org-id 123456
uv run python main.py --action check --csv devices.csv --report-csv inventory_report.csv
uv run python main.py --action claim --csv devices.csv --batch-size 200
uv run python main.py --action claim --csv devices.csv --log-file run_audit.log
```

Or rely on `.env` for org ID and only pass CSV:

```bash
uv run python main.py --action claim --csv devices.csv
```

If `--action` is omitted, the script will prompt for `claim`, `release`, or `check`.

If `--batch-size` is omitted, the script checks `MERAKI_BATCH_SIZE`. If that is also missing, it prompts for batch size and defaults to `50`.

Each run writes a log file with timestamps for API calls, inventory checks, skips, retries/backoff, and errors. Use `--log-file` or `MERAKI_LOG_FILE` to choose the path.

If a very large batch size causes API failures, the script automatically backs off and retries with a safe maximum batch size of `50`.

For `--action check`, the script prints a summary of how many CSV cloud IDs exist or are missing from inventory and writes a report CSV with columns `cloud_id`, `status` (`exists` or `missing`), and `networkId` (when present).

If `--report-csv` is omitted in check mode, it prompts for a report path and defaults to `inventory_check_report.csv`.

If `--csv` is omitted, the script will prompt for the CSV file path.

If no org ID is provided via `MERAKI_ORG_ID` or `--org-id`, the script will list the organizations available to the API key and then exit.
