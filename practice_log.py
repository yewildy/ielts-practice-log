"""A small local journal for speaking and writing practice."""

import argparse
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
import sqlite3
import sys

SKILLS = ("speaking", "writing")
APP_ID = 0x494C4F47  # ILOG: distinguish this journal from an unrelated SQLite file.
DEFAULT_DB = Path(__file__).resolve().parent / "data" / "practice.sqlite3"


def checked_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return value
    except (ValueError, TypeError):
        raise ValueError("Date must use YYYY-MM-DD and be a valid calendar date.") from None


def checked_skill(value):
    if value not in SKILLS:
        raise ValueError("Skill must be speaking or writing.")
    return value


def connect_database(path):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        app_id = connection.execute("PRAGMA application_id").fetchone()[0]
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        objects = connection.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
        if app_id == 0 and version == 0 and not objects:
            with connection:
                connection.execute("BEGIN")
                connection.execute("""CREATE TABLE entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill TEXT NOT NULL CHECK (skill IN ('speaking', 'writing')),
                    topic TEXT NOT NULL,
                    minutes INTEGER NOT NULL CHECK (minutes BETWEEN 1 AND 240),
                    note TEXT NOT NULL,
                    next_step TEXT NOT NULL,
                    practiced_on TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )""")
                connection.execute(f"PRAGMA application_id = {APP_ID}")
                connection.execute("PRAGMA user_version = 1")
        elif app_id != APP_ID or version != 1:
            raise ValueError("This is not a supported practice-log database; choose a new --db path.")
        return connection
    except Exception:
        connection.close()
        raise


def add_entry(connection, skill, topic, minutes, note="", next_step="", practiced_on=None):
    checked_skill(skill)
    topic, note, next_step = topic.strip(), note.strip(), next_step.strip()
    if not topic or len(topic) > 160:
        raise ValueError("Topic must contain 1-160 characters.")
    if type(minutes) is not int or not 1 <= minutes <= 240:
        raise ValueError("Minutes must be a whole number from 1 to 240.")
    if len(note) > 8000 or len(next_step) > 2000:
        raise ValueError("Note is limited to 8000 characters; next step to 2000.")
    practiced_on = checked_date(practiced_on if practiced_on is not None else date.today().isoformat())
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with connection:
        cursor = connection.execute(
            """INSERT INTO entries (skill, topic, minutes, note, next_step, practiced_on, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (skill, topic, minutes, note, next_step, practiced_on, created_at),
        )
    return cursor.lastrowid


def list_entries(connection, skill=None, query=None, since=None, limit=20):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Limit must be a whole number from 1 to 100.")
    filters, values = [], []
    if skill is not None:
        filters.append("skill = ?")
        values.append(checked_skill(skill))
    if query is not None:
        filters.append("instr(lower(topic || char(10) || note || char(10) || next_step), lower(?)) > 0")
        values.append(query)
    if since is not None:
        filters.append("practiced_on >= ?")
        values.append(checked_date(since))
    where = " WHERE " + " AND ".join(filters) if filters else ""
    return connection.execute(
        "SELECT * FROM entries" + where + " ORDER BY practiced_on DESC, id DESC LIMIT ?",
        [*values, limit],
    ).fetchall()


def get_entry(connection, entry_id):
    if type(entry_id) is not int or entry_id < 1:
        raise ValueError("Record ID must be a positive integer.")
    return connection.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()


def backup_database(connection, destination):
    destination = Path(destination).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reserve a new file exclusively so an existing backup is never overwritten.
    with destination.open("xb"):
        pass
    try:
        with closing(sqlite3.connect(destination)) as target:
            connection.backup(target)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def single_line(value, limit=70):
    value = " ".join(value.split())
    return value if len(value) <= limit else value[:limit - 1] + "…"


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite file (default: data/practice.sqlite3 beside this script)")
    actions = command.add_subparsers(dest="action", required=True)
    add = actions.add_parser("add", help="Save a completed practice and reflection")
    add.add_argument("--skill", choices=SKILLS, required=True)
    add.add_argument("--topic", required=True)
    add.add_argument("--minutes", type=int, required=True)
    add.add_argument("--note", default="")
    add.add_argument("--next-step", default="")
    add.add_argument("--date", dest="practiced_on", help="Practice date, YYYY-MM-DD; defaults to today")
    listing = actions.add_parser("list", help="Find recent records")
    listing.add_argument("--skill", choices=SKILLS)
    listing.add_argument("--query", help="Literal keyword in topic, note or next step")
    listing.add_argument("--since", help="Include this date and later dates, YYYY-MM-DD")
    listing.add_argument("--limit", type=int, default=20)
    show = actions.add_parser("show", help="Read one record in full")
    show.add_argument("id", type=int)
    backup = actions.add_parser("backup", help="Save a new SQLite backup file")
    backup.add_argument("destination", type=Path)
    return command


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        with closing(connect_database(args.db)) as connection:
            if args.action == "add":
                entry_id = add_entry(connection, args.skill, args.topic, args.minutes,
                                     args.note, args.next_step, args.practiced_on)
                print(f"Saved practice #{entry_id}.")
            elif args.action == "list":
                entries = list_entries(connection, args.skill, args.query, args.since, args.limit)
                if not entries:
                    print("No matching practice records.")
                for entry in entries:
                    print(f"#{entry['id']} | {entry['practiced_on']} | {entry['skill']} | {entry['minutes']} min | {single_line(entry['topic'])}")
                    if entry["next_step"]:
                        print("  Next: " + single_line(entry["next_step"]))
            elif args.action == "show":
                entry = get_entry(connection, args.id)
                if entry is None:
                    print(f"Practice #{args.id} was not found.", file=sys.stderr)
                    return 1
                print(f"#{entry['id']} | {entry['practiced_on']} | {entry['skill']} | {entry['minutes']} min")
                print(f"Topic: {entry['topic']}\nNote:\n{entry['note'] or '(empty)'}")
                print(f"Next step:\n{entry['next_step'] or '(empty)'}\nSaved at: {entry['created_at']}")
            elif args.action == "backup":
                destination = backup_database(connection, args.destination)
                print(f"Backup saved: {destination}")
        return 0
    except (ValueError, OSError, sqlite3.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
