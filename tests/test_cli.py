from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "practice_log.py"


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="practice demo ")
        self.addCleanup(self.folder.cleanup)
        self.db = Path(self.folder.name) / "practice.sqlite3"

    def run_cli(self, *arguments, db=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--db", str(db or self.db), *arguments],
            capture_output=True, text=True, encoding="utf-8",
            env=dict(os.environ, PYTHONUTF8="1"), timeout=10,
        )

    def test_record_find_read_and_backup_through_real_commands(self):
        added = self.run_cli("add", "--skill", "speaking", "--topic", "It's a useful tool / 日语メモ",
                             "--minutes", "12", "--note", "First thought.\n补一个例子。",
                             "--next-step", "Explain one detail.", "--date", "2026-10-17")
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertIn("Saved practice #1", added.stdout)
        listed = self.run_cli("list", "--skill", "speaking", "--query", "USEFUL", "--since", "2026-10-17")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("日语メモ", listed.stdout)
        self.assertIn("Next: Explain one detail.", listed.stdout)
        shown = self.run_cli("show", "1")
        self.assertIn("First thought.\n补一个例子。", shown.stdout)
        self.assertIn("Created at:", shown.stdout)
        invalid = self.run_cli("add", "--skill", "writing", "--topic", "Invalid", "--minutes", "0")
        self.assertEqual(invalid.returncode, 2)
        self.assertNotIn("Traceback", invalid.stderr)
        self.assertEqual(self.run_cli("list").stdout.count("#"), 1)
        self.assertEqual(self.run_cli("show", "999").returncode, 1)
        backup = Path(self.folder.name) / "copy.sqlite3"
        copied = self.run_cli("backup", str(backup))
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual(self.run_cli("show", "1", db=backup).stdout, shown.stdout)
        before = backup.read_bytes()
        self.assertEqual(self.run_cli("backup", str(backup)).returncode, 2)
        self.assertEqual(backup.read_bytes(), before)

    def test_missing_arguments_do_not_create_a_database(self):
        result = self.run_cli("add", "--skill", "speaking", "--minutes", "10")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.db.exists())
        self.assertEqual(self.run_cli("--help").returncode, 0)
        self.assertEqual(self.run_cli("review", "--help").returncode, 0)
        self.assertEqual(self.run_cli("export", "--help").returncode, 0)
        self.assertEqual(self.run_cli("export").returncode, 2)
        self.assertFalse(self.db.exists())

    def test_review_uses_filters_before_limit_without_changing_the_database(self):
        target = ("检查 100% 的例子。\n" + "A longer next step. " * 9).strip()
        for topic, skill, next_step, practiced_on in [
                ("Earlier writing", "writing", target, "2026-10-01"),
                ("Speaking target", "speaking", "Explain one detail.", "2026-10-02"),
                ("No target", "writing", "", "2026-10-03")]:
            added = self.run_cli("add", "--skill", skill, "--topic", topic, "--minutes", "10",
                                 "--next-step", next_step, "--date", practiced_on)
            self.assertEqual(added.returncode, 0, added.stderr)
        before = self.db.read_bytes()
        reviewed = self.run_cli("review", "--skill", "writing", "--query", "100%",
                                "--since", "2026-10-01", "--limit", "1")
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        self.assertIn("#1 | 2026-10-01 | writing", reviewed.stdout)
        self.assertIn("Next: 检查 100% 的例子。 A longer next step.", reviewed.stdout)
        preview = reviewed.stdout.splitlines()[1].removeprefix("  Next: ")
        self.assertEqual(len(preview), 120)
        self.assertTrue(preview.endswith("…"))
        self.assertNotIn("No target", reviewed.stdout)
        self.assertNotIn("Speaking target", reviewed.stdout)
        self.assertIn(target, self.run_cli("show", "1").stdout)
        self.assertEqual(self.db.read_bytes(), before)
        invalid = self.run_cli("review", "--limit", "0")
        self.assertEqual(invalid.returncode, 2)
        self.assertNotIn("Traceback", invalid.stderr)
        self.assertEqual(self.db.read_bytes(), before)

    def test_review_empty_state_and_clearing_a_target_keep_the_record(self):
        empty = self.run_cli("review")
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertEqual(empty.stdout.strip(), "No matching records with a next step.")
        self.assertEqual(self.run_cli("add", "--skill", "speaking", "--topic", "A tool",
                                     "--minutes", "10", "--next-step", "Add a detail.").returncode, 0)
        self.assertIn("Add a detail.", self.run_cli("review").stdout)
        self.assertEqual(self.run_cli("edit", "1", "--clear-next-step").returncode, 0)
        self.assertEqual(self.run_cli("review").stdout, empty.stdout)
        self.assertIn("A tool", self.run_cli("list").stdout)
        self.assertEqual(self.run_cli("show", "1").returncode, 0)

    def test_export_full_text_filtering_and_overwrite_protection_through_real_commands(self):
        topic = "A useful tool / 日语メモ"
        reflection = "It's a tool.\nCheck \"example\", 100%."
        next_step = "补充细节。 " * 30
        for skill in ["writing", "speaking"]:
            added = self.run_cli("add", "--skill", skill, "--topic", topic, "--minutes", "12",
                                 "--note", reflection, "--next-step", next_step, "--date", "2026-10-01")
            self.assertEqual(added.returncode, 0, added.stderr)
        before = self.db.read_bytes()
        destination = Path(self.folder.name) / "exports with spaces" / "复盘.json"
        result = self.run_cli("export", str(destination), "--skill", "writing", "--query", "100%",
                              "--since", "2026-10-01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Records exported: 1.", result.stdout)
        records = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["topic"], topic)
        self.assertEqual(records[0]["note"], reflection)
        self.assertEqual(records[0]["next_step"], next_step.strip())
        self.assertIn("created_at", records[0])
        self.assertEqual(self.db.read_bytes(), before)
        exported = destination.read_bytes()
        refused = self.run_cli("export", str(destination))
        self.assertEqual(refused.returncode, 2)
        self.assertNotIn("Traceback", refused.stderr)
        self.assertEqual(destination.read_bytes(), exported)
        self.assertEqual(self.run_cli("export", str(self.db)).returncode, 2)
        self.assertEqual(self.db.read_bytes(), before)

    def test_export_no_matches_and_invalid_filters(self):
        destination = Path(self.folder.name) / "empty.json"
        result = self.run_cli("export", str(destination), "--skill", "writing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Records exported: 0.", result.stdout)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), [])
        invalid = Path(self.folder.name) / "invalid.json"
        result = self.run_cli("export", str(invalid), "--since", "2026-02-30")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(invalid.exists())

    def test_edit_clear_and_error_cases_through_real_commands(self):
        self.assertEqual(self.run_cli("add", "--skill", "speaking", "--topic", "Example",
                                      "--minutes", "10", "--note", "Old reflection",
                                      "--next-step", "Keep this target").returncode, 0)
        original = self.run_cli("show", "1").stdout
        created_at = next(line for line in original.splitlines() if line.startswith("Created at:"))
        edited = self.run_cli("edit", "1", "--note", "新的复盘\nIt's clearer.")
        self.assertEqual(edited.returncode, 0, edited.stderr)
        self.assertIn("Updated practice #1", edited.stdout)
        shown = self.run_cli("show", "1").stdout
        self.assertIn("新的复盘\nIt's clearer.", shown)
        self.assertIn("Keep this target", shown)
        self.assertIn(created_at, shown)
        self.assertEqual(self.run_cli("edit", "1", "--clear-note").returncode, 0)
        self.assertIn("Note:\n(empty)\nNext step:\nKeep this target", self.run_cli("show", "1").stdout)
        self.assertEqual(self.run_cli("edit", "1", "--clear-next-step").returncode, 0)
        original = self.run_cli("show", "1").stdout
        for arguments in [("edit", "1"), ("edit", "1", "--note", "x" * 8001),
                          ("edit", "1", "--note", "conflict", "--clear-note"),
                          ("edit", str(2**63), "--note", "invalid ID")]:
            result = self.run_cli(*arguments)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(self.run_cli("show", "1").stdout, original)
        self.assertEqual(self.run_cli("edit", "999", "--note", "missing").returncode, 1)


if __name__ == "__main__":
    unittest.main()
