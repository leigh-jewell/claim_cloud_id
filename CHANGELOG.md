# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]
### Added
- Dry-run mode (`--dry-run`) to preview actions without making API calls

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

[Unreleased]: https://github.com/leigh-jewell/claim_cloud_id/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/leigh-jewell/claim_cloud_id/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/leigh-jewell/claim_cloud_id/releases/tag/v0.1.0