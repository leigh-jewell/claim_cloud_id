import csv
from pathlib import Path

from claim_cloud_id.logger import emit_info, emit_warning


def load_cloud_ids_from_csv(csv_path: str) -> list[str]:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    cloud_ids: list[str] = []
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        rows = list(csv.reader(csv_file))

    if not rows:
        raise ValueError("CSV file is empty")

    first_row = rows[0]
    normalized_first_row = [value.strip().lower() for value in first_row if value and value.strip()]
    header_index = None

    for candidate in ("cloud_id", "serial"):
        if candidate in normalized_first_row:
            header_index = normalized_first_row.index(candidate)
            break

    data_rows = rows
    start_row_number = 1
    if header_index is not None:
        data_rows = rows[1:]
        start_row_number = 2
    else:
        emit_info("Info: CSV header missing. Treating all rows as data.")

    for row_index, row in enumerate(data_rows, start=start_row_number):
        if header_index is not None and header_index < len(row):
            raw_value = row[header_index].strip()
        else:
            raw_value = next((value.strip() for value in row if value and value.strip()), "")

        if not raw_value:
            emit_warning(f"Skipping row {row_index}: missing cloud_id/serial value")
            continue

        cloud_ids.append(raw_value)

    if not cloud_ids:
        raise ValueError("No valid cloud IDs found in CSV")
    return list(dict.fromkeys(cloud_ids))
