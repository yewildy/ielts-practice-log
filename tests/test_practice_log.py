from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from practice_log import add_entry, backup_database, connect_database, edit_entry, get_entry, list_entries


class PracticeLogTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "practice.sqlite3"
        self.connection = connect_database(self.path)
        self.addCleanup(self.connection.close)

    def add(self, **changes):
        values = dict(skill="speaking", topic="一个小工具", minutes=12,
                      note="例子太短。\nTry another example.", next_step="补充一个细节。", practiced_on="2026-10-01")
        values.update(changes)
        return add_entry(self.connection, **values)

    def test_unicode_multiline_and_quotes_survive_reopening(self):
        entry_id = self.add(topic="It's a tool / 日语メモ", note="第一行\n'quoted', 100%")
        with closing(connect_database(self.path)) as reopened:
            entry = get_entry(reopened, entry_id)
            self.assertEqual(entry["topic"], "It's a tool / 日语メモ")
            self.assertEqual(entry["note"], "第一行\n'quoted', 100%")
            self.assertEqual(entry["next_step"], "补充一个细节。")

    def test_filters_order_and_limit(self):
        first = self.add(practiced_on="2026-09-30")
        second = self.add(skill="writing", topic="A useful place", practiced_on="2026-10-01")
        third = self.add(topic="A useful tool", practiced_on="2026-10-01")
        self.assertEqual([row["id"] for row in list_entries(self.connection)], [third, second, first])
        self.assertEqual([row["id"] for row in list_entries(self.connection, skill="writing", query="USEFUL", since="2026-10-01")], [second])
        self.assertEqual([row["id"] for row in list_entries(self.connection, limit=1)], [third])
        self.assertEqual(len(list_entries(self.connection, query="补充")), 3)

    def test_keywords_are_literal_and_do_not_become_sql(self):
        entry_id = self.add(note="Look at 100% of this example.")
        self.assertEqual([row["id"] for row in list_entries(self.connection, query="%")], [entry_id])
        self.assertEqual(list_entries(self.connection, query="' OR 1=1 --"), [])
        self.assertEqual(len(list_entries(self.connection)), 1)

    def test_review_filters_empty_targets_before_limit_and_does_not_write(self):
        first = self.add(practiced_on="2026-09-30", next_step="An older target")
        second = self.add(practiced_on="2026-10-01", next_step="A newer target")
        third = self.add(practiced_on="2026-10-01", next_step="Same date, later ID")
        self.add(practiced_on="2026-10-02", next_step=" \n\t ")
        before = [dict(row) for row in list_entries(self.connection)]
        changes = self.connection.total_changes
        rows = list_entries(self.connection, limit=1, next_steps_only=True)
        self.assertEqual([row["id"] for row in rows], [third])
        self.assertEqual([row["id"] for row in list_entries(self.connection, next_steps_only=True)],
                         [third, second, first])
        self.assertEqual(self.connection.total_changes, changes)
        self.assertEqual([dict(row) for row in list_entries(self.connection)], before)

    def test_review_combines_filters_and_reflects_target_edits(self):
        wanted = self.add(skill="writing", topic="A useful place", next_step="Check 100% of the examples.")
        self.add(skill="speaking", next_step="Check 100% of the examples.")
        self.add(skill="writing", practiced_on="2026-09-30", next_step="Check 100% of the examples.")
        self.add(skill="writing", next_step="")
        filters = dict(skill="writing", query="100%", since="2026-10-01", next_steps_only=True)
        self.assertEqual([row["id"] for row in list_entries(self.connection, **filters)], [wanted])
        self.assertEqual(list_entries(self.connection, query="' OR 1=1 --", next_steps_only=True), [])
        self.assertTrue(edit_entry(self.connection, wanted, next_step=""))
        with closing(connect_database(self.path)) as reopened:
            self.assertEqual(list_entries(reopened, **filters), [])
            self.assertIsNotNone(get_entry(reopened, wanted))
        self.assertTrue(edit_entry(self.connection, wanted, next_step="Try 100% again."))
        self.assertEqual([row["id"] for row in list_entries(self.connection, **filters)], [wanted])

    def test_invalid_records_do_not_add_partial_data(self):
        for changes in [dict(skill="other"), dict(topic="  "), dict(minutes=0), dict(minutes=1.5),
                        dict(practiced_on="2026-02-30"), dict(practiced_on="20261001"), dict(note="x" * 8001)]:
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValueError):
                    self.add(**changes)
        self.assertEqual(list_entries(self.connection), [])

    def test_missing_id_and_invalid_filters(self):
        self.assertIsNone(get_entry(self.connection, 123))
        for kwargs in [dict(limit=0), dict(skill="other"), dict(since="2026-13-01")]:
            with self.assertRaises(ValueError):
                list_entries(self.connection, **kwargs)
        with self.assertRaises(ValueError):
            get_entry(self.connection, 0)

    def test_backup_is_readable_independent_and_never_overwrites(self):
        first = self.add()
        destination = Path(self.folder.name) / "backups" / "snapshot.sqlite3"
        backup_database(self.connection, destination)
        self.add(topic="Second record")
        with closing(connect_database(destination)) as copied:
            self.assertEqual([row["id"] for row in list_entries(copied)], [first])
        before = destination.read_bytes()
        with self.assertRaises(FileExistsError):
            backup_database(self.connection, destination)
        self.assertEqual(destination.read_bytes(), before)
        with self.assertRaises(FileExistsError):
            backup_database(self.connection, self.path)
        self.assertEqual(len(list_entries(self.connection)), 2)

    def test_edit_changes_only_requested_fields_and_preserves_metadata(self):
        entry_id = self.add()
        original = dict(get_entry(self.connection, entry_id))
        updated_note = "补充细节。\nIt's a useful example, 100%."
        self.assertTrue(edit_entry(self.connection, entry_id, note=updated_note))
        with closing(connect_database(self.path)) as reopened:
            updated = dict(get_entry(reopened, entry_id))
        self.assertEqual(updated, {**original, "note": updated_note})
        self.assertTrue(edit_entry(self.connection, entry_id, next_step="再录一次。"))
        self.assertEqual(dict(get_entry(self.connection, entry_id)),
                         {**original, "note": updated_note, "next_step": "再录一次。"})

    def test_edit_can_clear_fields_without_changing_an_omitted_field(self):
        entry_id = self.add()
        original = dict(get_entry(self.connection, entry_id))
        self.assertTrue(edit_entry(self.connection, entry_id, note=""))
        self.assertEqual(dict(get_entry(self.connection, entry_id)), {**original, "note": ""})
        self.assertTrue(edit_entry(self.connection, entry_id, next_step=""))
        self.assertEqual(dict(get_entry(self.connection, entry_id)), {**original, "note": "", "next_step": ""})

    def test_invalid_edit_does_not_partially_write_or_create_records(self):
        entry_id = self.add()
        original = dict(get_entry(self.connection, entry_id))
        for arguments in [dict(note="changed", next_step="x" * 2001), dict(note="x" * 8001), {}]:
            with self.subTest(arguments=list(arguments)):
                with self.assertRaises(ValueError):
                    edit_entry(self.connection, entry_id, **arguments)
                self.assertEqual(dict(get_entry(self.connection, entry_id)), original)
        self.assertFalse(edit_entry(self.connection, 999, note="missing"))
        self.assertEqual(len(list_entries(self.connection)), 1)

    def test_show_and_edit_reject_ids_outside_sqlites_integer_range(self):
        for entry_id in [0, -1, True, 2**63]:
            with self.subTest(entry_id=entry_id):
                with self.assertRaises(ValueError):
                    get_entry(self.connection, entry_id)
                with self.assertRaises(ValueError):
                    edit_entry(self.connection, entry_id, note="unchanged")

    def test_unrelated_and_newer_databases_are_preserved(self):
        foreign = Path(self.folder.name) / "unrelated.sqlite3"
        with closing(sqlite3.connect(foreign)) as other:
            other.execute("CREATE TABLE other_notes (text TEXT)")
            other.commit()
        before = foreign.read_bytes()
        with self.assertRaises(ValueError):
            connect_database(foreign)
        self.assertEqual(foreign.read_bytes(), before)
        view_only = Path(self.folder.name) / "view-only.sqlite3"
        with closing(sqlite3.connect(view_only)) as other:
            other.execute("CREATE VIEW report AS SELECT 'keep this schema'")
            other.commit()
        before = view_only.read_bytes()
        with self.assertRaises(ValueError):
            connect_database(view_only)
        self.assertEqual(view_only.read_bytes(), before)
        self.connection.execute("PRAGMA user_version = 2")
        with self.assertRaises(ValueError):
            connect_database(self.path)


if __name__ == "__main__":
    unittest.main()
