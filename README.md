# 🚀 Meraki Dashboard Inventory Manager 🚀

> A Python utility for interacting with the [Meraki Dashboard](https://dashboard.meraki.com) API to automate device inventory tasks — bulk add, release and reporting. 

📖 **New here? Start with the [Quick Start Guide](QUICKSTART.md)**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](https://github.com/leigh-jewell/claim_cloud_id/releases)
[![Issues](https://img.shields.io/github/issues/leigh-jewell/claim_cloud_id/issues)](https://github.com/leigh-jewell/claim_cloud_id/issues)

---

## 📖 Table of Contents

- [About](#-about)
- [Features](#-features)
- [Demo](#-demo)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#-usage)
- [Configuration](#-configuration)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgements](#-acknowledgements)

---

## 🧐 About

> This tool is an open-source tool that reads a csv file of Meraki cloud ids and can either: **claim**, **release** or **check** those devices in your specified organisation in [Meraki Dashboard](https://dashboard.meraki.com). Built for [Meraki Dashboard](https://dashboard.meraki.com) Admins for when your claim-id doesn't work or you want to migrate devices from one organisation to another.

---

## ✨ Features

- ⚡ **Fast** — it has a batch function to reduce API calls
- 🔒 **Secure** — uses the Meraki API SDK for security
- 🌍 **Cross-platform** — works on any platform that can run Python
- 📦 **Minimal dependencies** - only needs Meraki and python-dotenv libraries
- 🛠️ **Easy to configure** — single config file and options can be run from command line

---

## 🎮 Demo

Claiming a list of devices into Meraki Dashboard from a CSV file using interactive option:
```console
$ python main.py      
Logging to meraki_inventory_actions.log
Choose action [claim/release/check]: claim
Enter path to CSV file with cloud IDs: cloud_id.csv
Info: CSV header missing. Treating all rows as data.
Loaded 2 cloud IDs from cloud_id.csv for claim with requested batch size 50
Info: the following cloud IDs are already in inventory and will be skipped:
- AAAA-BBB-CCCC
- DDDD-EEE-DDDD
Info: no claimable cloud IDs were found outside inventory.
```

---
## 🚀 Getting Started

### Prerequisites

- [Python](https://python.org/) >= 3.x
- API key from [Meraki Dashboard](https://dashboard.meraki.com)

### Installation

**1. Clone the repo:**
```bash
git clone https://github.com/leigh-jewell/claim_cloud_id.git
cd claim_cloud_id
```

**2. Install dependencies:**
```console
git clone https://github.com/username/repo.git
cd repo
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install .                    # Users only
```
Or if using [UV](https://docs.astral.sh/uv/ "Python package and project manager"):
```console
pip install uv           # Install uv
uv sync                  # Create venv + install everything
```

**3. Creating Meraki Dashboard API:**

You can create an API key within [Meraki Dashboard](https://dashboard.meraki.com) by clicking the person icon 👤 in the top right of your dashboard and selecting **My Profile** from the drop down. Scroll down to the **API access** section and click on **Generate new API key**. Copy this key and add it to your environment variables file (see below).

**4. Set up environment variables:**
```bash
cp .env.example .env
# Edit .env with your values
```
Edit the following variables in your `.env` file:

| Variable | Required | Description |
|---|---|---|
| `MERAKI_DASHBOARD_API_KEY` | ✅ | API key generated from the Meraki Dashboard (see [Creating an API Key](#creating-an-api-key)) |
| `MERAKI_ORG_ID` | ❌ | Your Meraki Organisation ID. If left empty, a list of available organisations will be printed on first run |
| `MERAKI_BATCH_SIZE` | ❌ | Number of devices per API batch upload. Larger values are faster but may cause API errors — start with `100` |
| `MERAKI_LOG_FILE` | ❌ | Path to a log file for script output e.g. `logs/meraki.log` |

Here is an example environment variable file:

```env
MERAKI_DASHBOARD_API_KEY=your_real_key_here
MERAKI_ORG_ID=123456
MERAKI_BATCH_SIZE=50
MERAKI_LOG_FILE=meraki_inventory_actions.log
```

**5. Run the script:**

Run with command options:
```bash
uv run python main.py --action claim   --csv devices.csv
```
Run interactive:
```bash
uv run python main.py
```

Run without [UV](https://docs.astral.sh/uv/):
```bash
source .venv/bin/activate
python main.py
```


---

## 💡 Usage

The script reads device serial numbers from a CSV file and can claim, release, or check devices
against your [Meraki Dashboard](https://dashboard.meraki.com) organisation inventory.

Run with `--action` and `--csv` as the minimum required arguments:

```bash
uv run python main.py --action claim   --csv devices.csv
uv run python main.py --action release --csv devices.csv
uv run python main.py --action check   --csv devices.csv
```

---

### Actions

| Action | Description |
|---|---|
| `claim` | Claims devices into organisation inventory, skipping any serials already present |
| `release` | Releases devices from inventory. Exits early if any device is currently bound to a network |
| `check` | Reports which CSV serials exist or are missing from inventory, with an optional CSV export |

---

### CLI Options

| Option | Default | Description |
|---|---|---|
| `--action` | prompted | `claim`, `release`, or `check` |
| `--csv` | prompted | Path to input CSV file |
| `--org-id` | `MERAKI_ORG_ID` | Organisation ID. If omitted, lists available orgs and exits |
| `--batch-size` | `MERAKI_BATCH_SIZE` or `50` | Devices per API request. Larger is faster but may cause errors |
| `--log-file` | `MERAKI_LOG_FILE` | Path to log file e.g. `logs/run.log` |
| `--report-csv` | `inventory_check_report.csv` | Output report path for `check` action |

---

### CSV Format

The preferred column header is `cloud_id` or `serial`. If neither is found, the first
non-empty value in each row is used.

---

### Behaviour & Safeguards

**Claim**
- Checks inventory before claiming — any serials already present are skipped and logged

**Release**
- Checks that no devices are currently bound to a network (`networkId` present) before
  attempting release — if any are bound, they are printed and the script exits without
  making changes
- Serials not found in inventory are skipped and logged; remaining serials proceed

**After claim or release**, the script automatically re-queries inventory via
`getOrganizationInventoryDevices` to verify serials are present (claim) or absent (release)

**Batch failures** — if a large batch size causes API errors, the script automatically backs
off and retries at a safe maximum of `50` per batch

---

### Logging

Every run produces a timestamped log covering API calls, inventory checks, skips,
retries, backoff events, and errors. Set the path via `--log-file` or `MERAKI_LOG_FILE`.

---

### Examples

```bash
# Claim with explicit org ID and batch size
uv run python main.py --action claim --csv devices.csv --org-id 123456 --batch-size 200

# Release using org ID from .env
uv run python main.py --action release --csv devices.csv

# Check inventory and export a report
uv run python main.py --action check --csv devices.csv --report-csv report.csv

# Log output to a file
uv run python main.py --action claim --csv devices.csv --log-file run_audit.log
```
---

## 🧪 Refactor Validation (Phase 1)

If you are validating the first refactor phase (constants/config/CLI extraction), run:

```bash
uv run python -m py_compile main.py claim_cloud_id/constants.py claim_cloud_id/config.py claim_cloud_id/cli.py claim_cloud_id/logger.py claim_cloud_id/csv_loader.py claim_cloud_id/report_writer.py
uv run python main.py --action check --csv cloud_id.csv
```

These checks confirm the module extraction compiles and that the existing check workflow still runs.

---

## 🤝 Contributing

Contributions are what make the open-source community great. Any contributions you make are **greatly appreciated**.

1. Fork the project
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

---

## 📄 License

This project is licensed under the [MIT License](LICENSE). You are free to use, modify, and distribute this script. It is provided as-is with no warranty — while reasonable safeguards are in place, always test in a non-production environment before running against live inventory.

---

## 🙏 Acknowledgements

- [Meraki SDK](https://developer.cisco.com/meraki/api-v1/python/) — all the Meraki Dashboard API calls
- [python-dotenv](https://pypi.org/project/python-dotenv/) — handles all the environment variables
- [shields.io](https://shields.io/) for the badges

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/leigh-jewell">Leigh J</a>
</p>
