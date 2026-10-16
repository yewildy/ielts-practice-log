from pathlib import Path
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
        self.assertIn("Saved at:", shown.stdout)
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
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
