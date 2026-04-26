# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]
### Changed
- Added `--dry-run` to the CLI Options table in `README.md`

---
## [1.1.0] - 2026-04-26
### Added
- Dry-run mode (`--dry-run`) to preview which devices would be claimed/released without making any inventory changes; prepare and safety checks (e.g. network-binding) still run so output is accurate
- `claim-cloud-id` console script entry point — users can now run `claim-cloud-id --action claim --csv devices.csv` directly instead of `python main.py`
- Test coverage for `csv_loader` (header detection, deduplication, multi-column CSVs, empty row skipping), `api_operations` (batch loop, backoff logic, serial extraction), `report_writer` (happy path and `OSError`), and `cli` (`get_batch_size` validation, `get_action` invalid input, `--dry-run` flag)

### Changed
- Moved entry-point logic from top-level `main.py` into `claim_cloud_id/main.py`; added `claim_cloud_id/__main__.py` so `python -m claim_cloud_id` still works
- Updated `README.md` and `QUICKSTART.md` to use the `claim-cloud-id` command throughout

### Fixed
- Interactive batch size prompt now raises a clear error on non-integer input instead of crashing
- Removed redundant intermediate variable in `get_inventory_serials_for_cloud_ids`
- Removed duplicate `[OK]` emit in `check_cloud_ids_in_inventory`
- `pyproject.toml` description updated from placeholder text

---

## [1.0.0] - 2026-04-26
### Added
- Initial release of Meraki Dashboard Inventory Manager
- `claim`, `release`, and `check` actions via CLI
- CSV input with auto-detection of `cloud_id` and `serial` headers
- Batch API calls with automatic backoff and retry on failure
- Post-action inventory verification for claim and release
- Network-binding safety check before release
- `--report-csv` export for `check` action
- `.env` support via `python-dotenv`
- Logging to file via `--log-file`

### Changed
- Refactored monolithic script into modules: `orchestrator`, `cli`, `config`,
  `api_operations`, `csv_loader`, `report_writer`, `logger`

### Fixed
- Duplicate serial handling — already-claimed devices now skipped gracefully

---

## [0.1.0] - 2026-03-10
### Added
- Proof of concept script for bulk claiming devices via Meraki API

---

[Unreleased]: https://github.com/leigh-jewell/claim_cloud_id/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/leigh-jewell/claim_cloud_id/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/leigh-jewell/claim_cloud_id/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/leigh-jewell/claim_cloud_id/releases/tag/v0.1.0