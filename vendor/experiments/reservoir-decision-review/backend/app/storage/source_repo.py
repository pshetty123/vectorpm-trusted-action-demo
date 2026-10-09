import sqlite3

from app.schemas.context_source import ContextSource
from app.storage.db import json_list, parse_json_list


def _row_to_source(row: sqlite3.Row) -> ContextSource:
    return ContextSource(
        source_id=row["source_id"],
        source_type=row["source_type"],
        title=row["title"],
        created_at=row["created_at"],
        product_area=row["product_area"],
        status=row["status"],
        content=row["content"],
        source_reference=row["source_reference"],
        superseded_by=row["superseded_by"],
        related_sources=parse_json_list(row["related_sources"]),
        segment=row["segment"],
        author_role=row["author_role"],
        strategic_area=row["strategic_area"],
        decision_owner=row["decision_owner"],
        effective_from=row["effective_from"],
        effective_to=row["effective_to"],
        tags=parse_json_list(row["tags"]),
    )


def insert_source(conn: sqlite3.Connection, source: ContextSource) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO sources (
            source_id, source_type, title, created_at, product_area, status, content,
            source_reference, superseded_by, related_sources, segment, author_role,
            strategic_area, decision_owner, effective_from, effective_to, tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source.source_id,
            source.source_type.value,
            source.title,
            source.created_at.isoformat(),
            source.product_area,
            source.status.value,
            source.content,
            source.source_reference,
            source.superseded_by,
            json_list(source.related_sources),
            source.segment,
            source.author_role,
            source.strategic_area,
            source.decision_owner,
            source.effective_from.isoformat() if source.effective_from else None,
            source.effective_to.isoformat() if source.effective_to else None,
            json_list(source.tags),
        ),
    )


def insert_chunk(conn: sqlite3.Connection, chunk_id: str, source_id: str, chunk_index: int, text: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO chunks (chunk_id, source_id, chunk_index, text) VALUES (?, ?, ?, ?)",
        (chunk_id, source_id, chunk_index, text),
    )


def get_source(conn: sqlite3.Connection, source_id: str) -> ContextSource | None:
    row = conn.execute("SELECT * FROM sources WHERE source_id = ?", (source_id,)).fetchone()
    return _row_to_source(row) if row else None


def list_sources(
    conn: sqlite3.Connection, source_type: str | None = None, status: str | None = None
) -> list[ContextSource]:
    query = "SELECT * FROM sources WHERE 1=1"
    params: list[str] = []
    if source_type:
        query += " AND source_type = ?"
        params.append(source_type)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_source(r) for r in rows]


def get_all_chunks(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM chunks ORDER BY source_id, chunk_index").fetchall()


def get_chunk_text(conn: sqlite3.Connection, chunk_id: str) -> str | None:
    row = conn.execute("SELECT text FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
    return row["text"] if row else None


def get_chunk_ids_for_sources(conn: sqlite3.Connection, source_ids: set[str]) -> set[str]:
    if not source_ids:
        return set()
    placeholders = ",".join("?" for _ in source_ids)
    rows = conn.execute(
        f"SELECT chunk_id FROM chunks WHERE source_id IN ({placeholders})", tuple(source_ids)
    ).fetchall()
    return {r["chunk_id"] for r in rows}


def filter_source_ids(
    conn: sqlite3.Connection,
    source_types: set[str] | None = None,
    status: str | None = None,
    created_after: str | None = None,
) -> set[str] | None:
    """Returns matching source_ids, or None if no filter applies at all
    (meaning: don't restrict candidates). An empty set means filters excluded
    everything — distinct from None."""
    if source_types is None and status is None and created_after is None:
        return None

    query = "SELECT source_id FROM sources WHERE 1=1"
    params: list[str] = []
    if source_types:
        placeholders = ",".join("?" for _ in source_types)
        query += f" AND source_type IN ({placeholders})"
        params.extend(source_types)
    if status:
        query += " AND status = ?"
        params.append(status)
    if created_after:
        query += " AND created_at >= ?"
        params.append(created_after)

    rows = conn.execute(query, params).fetchall()
    return {r["source_id"] for r in rows}
