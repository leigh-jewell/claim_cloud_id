import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from claim_cloud_id.csv_loader import load_cloud_ids_from_csv


class TestLoadCloudIdsFromCSV(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def _write_csv(self, content: str, filename: str = "test.csv") -> str:
        path = os.path.join(self.tmp_dir, filename)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        return path

    # ── file-level errors ──────────────────────────────────────────────────

    def test_file_not_found_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_cloud_ids_from_csv(os.path.join(self.tmp_dir, "nonexistent.csv"))

    def test_path_is_directory_raises(self):
        with self.assertRaises(ValueError):
            load_cloud_ids_from_csv(self.tmp_dir)

    def test_empty_file_raises(self):
        path = self._write_csv("")
        with self.assertRaises(ValueError) as ctx:
            load_cloud_ids_from_csv(path)
        self.assertIn("empty", str(ctx.exception).lower())

    # ── header detection ───────────────────────────────────────────────────

    def test_cloud_id_header_detected(self):
        path = self._write_csv("cloud_id\nAAA-1111\nBBB-2222\n")
        result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    def test_serial_header_detected(self):
        path = self._write_csv("serial\nAAA-1111\nBBB-2222\n")
        result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    def test_header_case_insensitive(self):
        path = self._write_csv("Cloud_ID\nAAA-1111\n")
        result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111"])

    def test_header_with_surrounding_spaces(self):
        path = self._write_csv(" cloud_id \nAAA-1111\n")
        result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111"])

    def test_no_header_treats_all_rows_as_data(self):
        path = self._write_csv("AAA-1111\nBBB-2222\n")
        with patch("claim_cloud_id.csv_loader.emit_info"):
            result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    # ── multi-column CSVs ─────────────────────────────────────────────────

    def test_multi_column_cloud_id_header_picks_correct_column(self):
        path = self._write_csv("name,cloud_id,notes\nDevice A,AAA-1111,note\nDevice B,BBB-2222,\n")
        result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    def test_multi_column_serial_header_picks_correct_column(self):
        path = self._write_csv("name,serial\nDevice A,AAA-1111\nDevice B,BBB-2222\n")
        result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    def test_multi_column_no_header_uses_first_nonempty_value(self):
        # First row has no recognized header; all rows become data.
        # Function picks first non-empty cell per row.
        path = self._write_csv(",AAA-1111\n,BBB-2222\n")
        with patch("claim_cloud_id.csv_loader.emit_info"):
            result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    # ── deduplication ─────────────────────────────────────────────────────

    def test_deduplication_preserves_insertion_order(self):
        path = self._write_csv("cloud_id\nAAA-1111\nBBB-2222\nAAA-1111\nCCC-3333\n")
        result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222", "CCC-3333"])

    # ── empty row skipping ────────────────────────────────────────────────

    def test_empty_rows_are_skipped(self):
        path = self._write_csv("cloud_id\nAAA-1111\n\nBBB-2222\n")
        with patch("claim_cloud_id.csv_loader.emit_warning"):
            result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    def test_whitespace_only_rows_are_skipped(self):
        path = self._write_csv("cloud_id\nAAA-1111\n   \nBBB-2222\n")
        with patch("claim_cloud_id.csv_loader.emit_warning"):
            result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    def test_all_data_rows_empty_raises(self):
        path = self._write_csv("cloud_id\n\n\n")
        with patch("claim_cloud_id.csv_loader.emit_warning"):
            with self.assertRaises(ValueError) as ctx:
                load_cloud_ids_from_csv(path)
        self.assertIn("No valid cloud IDs", str(ctx.exception))

    # ── value cleaning ────────────────────────────────────────────────────

    def test_values_stripped_of_whitespace(self):
        path = self._write_csv("cloud_id\n  AAA-1111  \n  BBB-2222  \n")
        result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111", "BBB-2222"])

    # ── single-row edge cases ─────────────────────────────────────────────

    def test_only_header_row_raises(self):
        path = self._write_csv("cloud_id\n")
        with self.assertRaises(ValueError):
            load_cloud_ids_from_csv(path)

    def test_single_data_row_no_header(self):
        path = self._write_csv("AAA-1111\n")
        with patch("claim_cloud_id.csv_loader.emit_info"):
            result = load_cloud_ids_from_csv(path)
        self.assertEqual(result, ["AAA-1111"])


if __name__ == "__main__":
    unittest.main()
