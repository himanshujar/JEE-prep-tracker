"""Data layer for the JEE prep tracker.

By default everything lives in a local SQLite file (jee_tracker.db) next to
the project, created automatically on first run and reseeded from
seed_data.py whenever the user asks for a reset.

When deployed somewhere with an ephemeral/read-only filesystem (e.g. Vercel
Functions), set TURSO_DATABASE_URL + TURSO_AUTH_TOKEN env vars to transparently
switch to a free remote Turso/libSQL database instead, so progress actually
persists across requests and deployments. See README.md for setup.
"""
import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from seed_data import MILESTONES, TOPICS

DB_PATH = Path(__file__).resolve().parent.parent / "jee_tracker.db"

TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

DEFAULT_SETTINGS = {
    "current_score": "75",
    "jan_target": "150",
    "april_target": "160",
    "current_score_date": date.today().isoformat(),
    "jan_exam_date": (date.today() + timedelta(days=60)).isoformat(),
    "april_exam_date": (date.today() + timedelta(days=150)).isoformat(),
}


class Row:
    """Mimics sqlite3.Row: supports both row["col"] and row[0] access, plus
    dict(row), regardless of which backend produced it."""

    __slots__ = ("_columns", "_values")

    def __init__(self, columns, values):
        self._columns = columns
        self._values = values

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._values[self._columns.index(key)]
        return self._values[key]

    def keys(self):
        return list(self._columns)


class RowCursor:
    """Wraps a raw DB-API cursor so fetchone/fetchall always return Row
    objects, whether the underlying driver is sqlite3 or libsql."""

    def __init__(self, cursor):
        self._cursor = cursor
        self._columns = [d[0] for d in cursor.description] if cursor.description else []

    def fetchone(self):
        row = self._cursor.fetchone()
        return None if row is None else Row(self._columns, tuple(row))

    def fetchall(self):
        return [Row(self._columns, tuple(r)) for r in self._cursor.fetchall()]


class Conn:
    """Thin wrapper giving sqlite3 and libsql connections an identical,
    dict-row-friendly interface."""

    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=()):
        return RowCursor(self._raw.execute(sql, params))

    def executemany(self, sql, seq_of_params):
        self._raw.executemany(sql, seq_of_params)

    def executescript(self, script):
        # libsql has no executescript(); split on ';' and run each statement.
        # Safe here since our schema has no semicolons inside string literals.
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self._raw.execute(statement)

    def commit(self):
        self._raw.commit()

    def close(self):
        self._raw.close()


def get_connection():
    if TURSO_DATABASE_URL:
        import libsql  # optional dependency, only needed for remote deploys

        raw = libsql.connect(database=TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    else:
        raw = sqlite3.connect(DB_PATH)
    return Conn(raw)


def init_db():
    """Create tables if they don't exist yet, and seed them on first run."""
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_ TEXT NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            subtopics TEXT,
            jee_main TEXT,
            jee_advanced TEXT,
            boards TEXT,
            priority TEXT,
            theory_status TEXT DEFAULT 'Not started',
            concept_confidence INTEGER DEFAULT 1,
            formula_confidence INTEGER DEFAULT 1,
            institute_sheet INTEGER DEFAULT 0,
            main_pyq INTEGER DEFAULT 0,
            adv_pyq INTEGER DEFAULT 0,
            board_q INTEGER DEFAULT 0,
            practice_accuracy INTEGER,
            last_studied TEXT,
            next_revision TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS mock_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_num INTEGER NOT NULL,
            test_date TEXT,
            test_type TEXT DEFAULT 'Full JEE Main',
            score INTEGER,
            physics INTEGER,
            chemistry INTEGER,
            maths INTEGER,
            attempted INTEGER,
            correct INTEGER,
            incorrect INTEGER,
            accuracy REAL,
            error_pattern TEXT,
            next_actions TEXT
        );

        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phase TEXT,
            date_range TEXT,
            outcome TEXT,
            physics TEXT,
            chemistry TEXT,
            maths TEXT,
            testing TEXT,
            exit_criteria TEXT
        );
        """
    )
    conn.commit()

    if conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0] == 0:
        seed_settings(conn)
    if conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0] == 0:
        seed_topics(conn)
    if conn.execute("SELECT COUNT(*) FROM mock_tests").fetchone()[0] == 0:
        seed_mock_tests(conn)
    if conn.execute("SELECT COUNT(*) FROM milestones").fetchone()[0] == 0:
        seed_milestones(conn)
    conn.close()


def seed_settings(conn):
    conn.executemany(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        list(DEFAULT_SETTINGS.items()),
    )
    conn.commit()


def seed_topics(conn):
    conn.execute("DELETE FROM topics")
    for t in TOPICS:
        conn.execute(
            """INSERT INTO topics
               (class_, subject, topic, subtopics, jee_main, jee_advanced, boards, priority)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                t["class_"], t["subject"], t["topic"], t["subtopics"],
                t["jee_main"], t["jee_advanced"], t["boards"], t["priority"],
            ),
        )
    conn.commit()


def seed_mock_tests(conn):
    conn.execute("DELETE FROM mock_tests")
    for i in range(1, 31):
        conn.execute(
            "INSERT INTO mock_tests (test_num, test_type) VALUES (?, ?)",
            (i, "Full JEE Main"),
        )
    conn.commit()


def seed_milestones(conn):
    conn.execute("DELETE FROM milestones")
    for m in MILESTONES:
        conn.execute(
            """INSERT INTO milestones
               (phase, date_range, outcome, physics, chemistry, maths, testing, exit_criteria)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                m["phase"], m["date_range"], m["outcome"], m["physics"],
                m["chemistry"], m["maths"], m["testing"], m["exit_criteria"],
            ),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def get_settings():
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def update_settings(values: dict):
    conn = get_connection()
    for key, value in values.items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
    conn.commit()
    conn.close()


def reset_settings():
    conn = get_connection()
    conn.execute("DELETE FROM settings")
    seed_settings(conn)
    conn.close()


# ---------------------------------------------------------------------------
# Topics helpers
# ---------------------------------------------------------------------------

def get_all_topics(class_filter=None, subject_filter=None, priority_filter=None, status_filter=None):
    conn = get_connection()
    query = "SELECT * FROM topics WHERE 1=1"
    params = []
    if class_filter:
        query += " AND class_ = ?"
        params.append(class_filter)
    if subject_filter:
        query += " AND subject = ?"
        params.append(subject_filter)
    if priority_filter:
        query += " AND priority = ?"
        params.append(priority_filter)
    if status_filter:
        query += " AND theory_status = ?"
        params.append(status_filter)
    query += " ORDER BY id"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_topic(topic_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_topic(topic_id, fields: dict):
    conn = get_connection()
    columns = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [topic_id]
    conn.execute(f"UPDATE topics SET {columns} WHERE id = ?", params)
    conn.commit()
    conn.close()


def reset_topics():
    conn = get_connection()
    seed_topics(conn)
    conn.close()


def compute_completion(topic: dict) -> float:
    """Indicative 0-100 completion score for a single topic.

    Weighted blend of: theory status (30%), practice items done (40%),
    confidence (20%), practice accuracy (10%).
    """
    status_weight = {
        "Not started": 0.0,
        "In progress": 0.5,
        "Revision needed": 0.75,
        "Completed": 1.0,
    }.get(topic["theory_status"], 0.0)

    applicable_items = []
    applicable_items.append(bool(topic["institute_sheet"]))
    if topic["jee_main"] == "Yes":
        applicable_items.append(bool(topic["main_pyq"]))
    if topic["jee_advanced"] == "Yes":
        applicable_items.append(bool(topic["adv_pyq"]))
    if topic["boards"] == "Yes":
        applicable_items.append(bool(topic["board_q"]))
    practice_ratio = (sum(applicable_items) / len(applicable_items)) if applicable_items else 0.0

    confidence_ratio = (
        (topic["concept_confidence"] + topic["formula_confidence"]) / 2.0 / 5.0
    )
    accuracy_ratio = (topic["practice_accuracy"] or 0) / 100.0

    score = (
        status_weight * 0.30
        + practice_ratio * 0.40
        + confidence_ratio * 0.20
        + accuracy_ratio * 0.10
    )
    return round(score * 100, 1)


def get_dashboard_metrics():
    topics = get_all_topics()
    total = len(topics)
    theory_completed = sum(1 for t in topics if t["theory_status"] == "Completed")
    sheets_done = sum(1 for t in topics if t["institute_sheet"])
    main_pyq_done = sum(1 for t in topics if t["jee_main"] == "Yes" and t["main_pyq"])
    adv_pyq_done = sum(1 for t in topics if t["jee_advanced"] == "Yes" and t["adv_pyq"])
    board_done = sum(1 for t in topics if t["boards"] == "Yes" and t["board_q"])
    high_priority_pending = sum(
        1 for t in topics if t["priority"] == "High" and t["theory_status"] != "Completed"
    )
    completions = [compute_completion(t) for t in topics]
    avg_completion = round(sum(completions) / len(completions), 1) if completions else 0.0

    return {
        "total_topics": total,
        "theory_completed": theory_completed,
        "sheets_done": sheets_done,
        "main_pyq_done": main_pyq_done,
        "adv_pyq_done": adv_pyq_done,
        "board_done": board_done,
        "high_priority_pending": high_priority_pending,
        "avg_completion": avg_completion,
    }


# ---------------------------------------------------------------------------
# Mock test helpers
# ---------------------------------------------------------------------------

def get_all_mock_tests():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM mock_tests ORDER BY test_num").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_mock_test(mock_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM mock_tests WHERE id = ?", (mock_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_mock_test(mock_id, fields: dict):
    conn = get_connection()
    columns = ", ".join(f"{k} = ?" for k in fields)
    params = list(fields.values()) + [mock_id]
    conn.execute(f"UPDATE mock_tests SET {columns} WHERE id = ?", params)
    conn.commit()
    conn.close()


def reset_mock_tests():
    conn = get_connection()
    seed_mock_tests(conn)
    conn.close()


# ---------------------------------------------------------------------------
# Milestones helpers
# ---------------------------------------------------------------------------

def get_all_milestones():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM milestones ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def reset_milestones():
    conn = get_connection()
    seed_milestones(conn)
    conn.close()


def reset_everything():
    conn = get_connection()
    conn.execute("DELETE FROM settings")
    conn.execute("DELETE FROM topics")
    conn.execute("DELETE FROM mock_tests")
    conn.execute("DELETE FROM milestones")
    seed_settings(conn)
    seed_topics(conn)
    seed_mock_tests(conn)
    seed_milestones(conn)
    conn.close()
