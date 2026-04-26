import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from claim_cloud_id.report_writer import write_inventory_check_report


class TestWriteInventoryCheckReport(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.report_path = os.path.join(self.tmp_dir, "report.csv")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def _read_lines(self) -> list[str]:
        with open(self.report_path, encoding="utf-8", newline="") as f:
            return f.read().splitlines()

    # ── happy path ─────────────────────────────────────────────────────────

    def test_writes_header_and_rows(self):
        cloud_ids = ["AAA-1111", "BBB-2222"]
        inventory_serials = {"AAA-1111"}
        network_ids = {"AAA-1111": "net-abc"}

        ok, msg = write_inventory_check_report(
            self.report_path, cloud_ids, inventory_serials, network_ids
        )

        self.assertTrue(ok)
        self.assertIn(str(self.report_path), msg)

        lines = self._read_lines()
        self.assertEqual(lines[0], "cloud_id,status,networkId")
        self.assertEqual(lines[1], "AAA-1111,exists,net-abc")
        self.assertEqual(lines[2], "BBB-2222,missing,NONE")

    def test_creates_parent_directories(self):
        nested_path = os.path.join(self.tmp_dir, "sub", "dir", "report.csv")
        ok, msg = write_inventory_check_report(nested_path, ["AAA"], set(), {})

        self.assertTrue(ok)
        self.assertTrue(os.path.exists(nested_path))

    def test_empty_cloud_ids_writes_only_header(self):
        ok, msg = write_inventory_check_report(self.report_path, [], set(), {})

        self.assertTrue(ok)
        lines = self._read_lines()
        self.assertEqual(lines, ["cloud_id,status,networkId"])

    def test_serial_in_inventory_and_bound_to_network(self):
        ok, msg = write_inventory_check_report(
            self.report_path, ["X"], {"X"}, {"X": "net-xyz"}
        )

        self.assertTrue(ok)
        lines = self._read_lines()
        self.assertEqual(lines[1], "X,exists,net-xyz")

    def test_serial_missing_has_none_network_id(self):
        ok, msg = write_inventory_check_report(
            self.report_path, ["X"], set(), {}
        )

        self.assertTrue(ok)
        lines = self._read_lines()
        self.assertEqual(lines[1], "X,missing,NONE")

    # ── CSV formula-injection sanitization (CWE-1236) ──────────────────────

    def test_cloud_id_starting_with_equals_is_neutralized(self):
        ok, _ = write_inventory_check_report(
            self.report_path, ["=cmd|'/c calc'!A1"], set(), {}
        )
        self.assertTrue(ok)
        lines = self._read_lines()
        # csv.writer quotes the cell because the leading "'" + "=" makes it a special value
        self.assertTrue(lines[1].startswith("'="), f"Expected leading apostrophe-equals, got: {lines[1]!r}")

    def test_network_id_starting_with_at_is_neutralized(self):
        ok, _ = write_inventory_check_report(
            self.report_path, ["X"], {"X"}, {"X": "@SUM(1+1)"}
        )
        self.assertTrue(ok)
        lines = self._read_lines()
        self.assertIn("'@SUM(1+1)", lines[1])

    def test_safe_values_are_unchanged(self):
        ok, _ = write_inventory_check_report(
            self.report_path, ["AAA-1111"], {"AAA-1111"}, {"AAA-1111": "net-abc"}
        )
        self.assertTrue(ok)
        lines = self._read_lines()
        self.assertEqual(lines[1], "AAA-1111,exists,net-abc")

    # ── OSError path ───────────────────────────────────────────────────────

    def test_os_error_returns_false(self):
        with patch("claim_cloud_id.report_writer.Path.open", side_effect=OSError("disk full")):
            ok, msg = write_inventory_check_report(
                self.report_path, ["AAA"], set(), {}
            )

        self.assertFalse(ok)
        self.assertIn("failed to write report CSV", msg)
        self.assertIn("disk full", msg)


if __name__ == "__main__":
    unittest.main()
