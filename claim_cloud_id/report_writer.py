import csv
from pathlib import Path

from claim_cloud_id.logger import log_error, log_info


def write_inventory_check_report(
    report_csv_path: str,
    cloud_ids: list[str],
    inventory_serials: set[str],
    network_ids_by_serial: dict[str, str],
) -> tuple[bool, str]:
    report_path = Path(report_csv_path)
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["cloud_id", "status", "networkId"])
            for cloud_id in cloud_ids:
                status = "exists" if cloud_id in inventory_serials else "missing"
                network_id = network_ids_by_serial.get(cloud_id, "NONE")
                writer.writerow([cloud_id, status, network_id])
    except OSError as exc:
        log_error(f"Failed writing check report CSV at {report_path}: {exc}")
        return False, f"failed to write report CSV: {exc}"

    log_info(f"Check report CSV written: path={report_path}, rows={len(cloud_ids)}")
    return True, f"report written to {report_path}"
