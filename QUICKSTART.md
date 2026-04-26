## ⚡ Quick Start

**1. Clone the repo and install:**
```bash
git clone https://github.com/username/repo.git
cd repo
pip install uv
uv sync
```

**2. Create your `.env` file:**
```bash
cp .env.example .env
```

```text
MERAKI_DASHBOARD_API_KEY=your_api_key_here
MERAKI_ORG_ID=meraki_org_id
```

**3. Prepare your CSV file** with a `cloud_id` or `serial` column:

```text
cloud_id
Q2XX-XXXX-XXXX
Q2XX-XXXX-XXXY
Q2XX-XXXX-XXXZ
```

**4. Run:**
```bash
# Check which devices exist in inventory
claim-cloud-id --action check --csv devices.csv

# Claim devices into inventory
claim-cloud-id --action claim --csv devices.csv

# Release devices from inventory
claim-cloud-id --action release --csv devices.csv
```
**4. Example Run:**
```console
$ claim-cloud-id --action claim --csv cloud_id.csv
Logging to meraki_inventory_actions.log
Info: CSV header missing. Treating all rows as data.
Loaded 2 cloud IDs from cloud_id.csv for claim with requested batch size 50
[OK] claimed 2 serial(s) in batches of up to 50
Claimed serials:
- Q2XX-XXXX-XXXY
- Q2XX-XXXX-XXXZ
[OK] inventory verification passed after claim
$
```

That's it. The script will log all activity and confirm inventory state after each operation.

📖 **Need more information? Check out [README Guide](README.md)**
