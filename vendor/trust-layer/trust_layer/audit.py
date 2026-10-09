"""Append-only, hash-chained audit log.

Two independent protections:
  1. SQLite triggers abort any UPDATE or DELETE on the table.
  2. Each entry's hash covers the previous entry's hash, so an edit made
     around the triggers (e.g. by dropping them) is detected by verify().
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from trust_layer.schemas import canonical_json, sha256_hex

GENESIS = "0" * 64

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY,
    recorded_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    evaluation_id TEXT,
    actor TEXT,
    payload_json TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
"""

EVENT_TYPES = {
    "EVALUATED", "APPROVED", "REJECTED", "APPROVAL_DENIED",
    "EXECUTED_SIMULATED", "EXECUTION_REFUSED",
}


def _entry_hash(seq: int, recorded_at: str, event_type: str, evaluation_id: str | None,
                actor: str | None, payload_json: str, prev_hash: str) -> str:
    return sha256_hex(canonical_json([seq, recorded_at, event_type, evaluation_id, actor, payload_json, prev_hash]))


@dataclass
class ChainReport:
    ok: bool
    entries: int
    first_bad_seq: int | None = None
    detail: str = ""


class AuditLog:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        conn.executescript(SCHEMA)

    def append(self, event_type: str, payload: dict, evaluation_id: str | None = None,
               actor: str | None = None, commit: bool = True) -> dict:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown audit event type {event_type}")
        last = self.conn.execute("SELECT seq, entry_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
        seq = (last[0] + 1) if last else 1
        prev = last[1] if last else GENESIS
        recorded_at = datetime.now(timezone.utc).isoformat()
        payload_json = canonical_json(payload)
        h = _entry_hash(seq, recorded_at, event_type, evaluation_id, actor, payload_json, prev)
        self.conn.execute(
            "INSERT INTO audit_log (seq, recorded_at, event_type, evaluation_id, actor, payload_json, prev_hash, entry_hash)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (seq, recorded_at, event_type, evaluation_id, actor, payload_json, prev, h),
        )
        if commit:
            self.conn.commit()
        return {"seq": seq, "entry_hash": h}

    def entries(self, evaluation_id: str | None = None) -> list[dict]:
        q, args = "SELECT * FROM audit_log", ()
        if evaluation_id:
            q, args = q + " WHERE evaluation_id = ?", (evaluation_id,)
        rows = self.conn.execute(q + " ORDER BY seq", args).fetchall()
        return [{
            "seq": r[0], "recorded_at": r[1], "event_type": r[2], "evaluation_id": r[3],
            "actor": r[4], "payload": json.loads(r[5]), "prev_hash": r[6], "entry_hash": r[7],
        } for r in rows]

    def verify(self) -> ChainReport:
        prev, n = GENESIS, 0
        for r in self.conn.execute("SELECT * FROM audit_log ORDER BY seq").fetchall():
            n += 1
            seq, recorded_at, event_type, ev_id, actor, payload_json, prev_hash, entry_hash = r
            if seq != n:
                return ChainReport(False, n, seq, f"sequence gap: expected {n}, found {seq}")
            if prev_hash != prev:
                return ChainReport(False, n, seq, "prev_hash does not match the previous entry")
            if _entry_hash(seq, recorded_at, event_type, ev_id, actor, payload_json, prev_hash) != entry_hash:
                return ChainReport(False, n, seq, "entry contents do not match entry_hash")
            prev = entry_hash
        return ChainReport(True, n)
