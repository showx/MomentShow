from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from momentshow.paths import database_path


@dataclass(frozen=True)
class Moment:
    id: int
    author: str
    time_text: str
    body: str
    raw_text: str
    captured_at: str
    content_hash: str


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _init(conn)
    return conn


def _init(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS moments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author TEXT NOT NULL,
            time_text TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            raw_text TEXT NOT NULL DEFAULT '',
            captured_at TEXT NOT NULL,
            content_hash TEXT NOT NULL UNIQUE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_moments_author ON moments(author)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_moments_captured ON moments(captured_at DESC)"
    )
    conn.commit()


def insert_moment(
    conn: sqlite3.Connection,
    *,
    author: str,
    time_text: str,
    body: str,
    raw_text: str,
    content_hash: str,
    captured_at: str | None = None,
) -> bool:
    stamp = captured_at or datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            """
            INSERT INTO moments (author, time_text, body, raw_text, captured_at, content_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (author, time_text, body, raw_text, stamp, content_hash),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def list_moments(
    conn: sqlite3.Connection,
    *,
    author: str | None = None,
    limit: int = 200,
) -> list[Moment]:
    sql = "SELECT * FROM moments"
    params: list[object] = []
    if author:
        sql += " WHERE author = ?"
        params.append(author)
    sql += " ORDER BY captured_at DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_moment(row) for row in rows]


def list_authors(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        """
        SELECT author, COUNT(*) AS n
        FROM moments
        GROUP BY author
        ORDER BY n DESC, author COLLATE NOCASE
        """
    ).fetchall()
    return [str(row["author"]) for row in rows]


def count_moments(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM moments").fetchone()
    return int(row["n"] if row else 0)


def _row_to_moment(row: sqlite3.Row) -> Moment:
    return Moment(
        id=int(row["id"]),
        author=str(row["author"]),
        time_text=str(row["time_text"]),
        body=str(row["body"]),
        raw_text=str(row["raw_text"]),
        captured_at=str(row["captured_at"]),
        content_hash=str(row["content_hash"]),
    )
