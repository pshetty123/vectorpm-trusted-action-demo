import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    product_area TEXT NOT NULL,
    status TEXT NOT NULL,
    content TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    superseded_by TEXT,
    related_sources TEXT NOT NULL DEFAULT '[]',
    segment TEXT,
    author_role TEXT,
    strategic_area TEXT,
    decision_owner TEXT,
    effective_from TEXT,
    effective_to TEXT,
    tags TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    decision_status TEXT NOT NULL,
    date TEXT NOT NULL,
    owner TEXT NOT NULL,
    rationale TEXT NOT NULL,
    supporting_evidence TEXT NOT NULL DEFAULT '[]',
    challenging_evidence TEXT NOT NULL DEFAULT '[]',
    assumptions TEXT NOT NULL DEFAULT '[]',
    missing_context TEXT NOT NULL DEFAULT '[]',
    expected_outcome TEXT NOT NULL,
    success_metric TEXT NOT NULL,
    review_date TEXT NOT NULL,
    related_decisions TEXT NOT NULL DEFAULT '[]',
    proposed_decision_text TEXT,
    review_id TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    review_id TEXT PRIMARY KEY,
    proposed_decision TEXT NOT NULL,
    synthesis_json TEXT NOT NULL,
    trace_json TEXT,
    created_at TEXT NOT NULL
);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_db(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(
            "DROP TABLE IF EXISTS chunks; DROP TABLE IF EXISTS sources; "
            "DROP TABLE IF EXISTS decisions; DROP TABLE IF EXISTS reviews;"
        )
        conn.commit()
    finally:
        conn.close()
    init_db(db_path)


def json_list(value) -> str:
    return json.dumps(value or [])


def parse_json_list(value: str | None) -> list:
    if not value:
        return []
    return json.loads(value)
