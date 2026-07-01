"""Persistence for generated briefings history."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


_ROOT = Path(__file__).resolve().parent.parent
if os.getenv("VERCEL"):
    _DB_DIR = Path("/tmp/data")
else:
    _DB_DIR = _ROOT / "data"
_DB_PATH = _DB_DIR / "history.db"
_MAX_HTML_CHARS = 350_000


def _conn() -> sqlite3.Connection:
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_history_store() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS briefing_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                email TEXT DEFAULT '',
                delivered INTEGER DEFAULT 0,
                delivery_message TEXT DEFAULT '',
                elapsed_seconds REAL DEFAULT 0,
                html TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_history_entry(
    *,
    topic: str,
    email: str,
    delivered: bool,
    delivery_message: str,
    elapsed_seconds: float,
    html: str,
) -> int:
    init_history_store()
    created_at = datetime.now(timezone.utc).isoformat()
    html_to_store = (html or "")[:_MAX_HTML_CHARS]

    with _conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO briefing_history
                (topic, email, delivered, delivery_message, elapsed_seconds, html, created_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic.strip()[:250],
                (email or "").strip()[:250],
                1 if delivered else 0,
                (delivery_message or "")[:500],
                float(elapsed_seconds or 0),
                html_to_store,
                created_at,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_history_entries(limit: int = 20) -> List[Dict]:
    init_history_store()
    cap = max(1, min(int(limit), 100))
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT
                id, topic, email, delivered, delivery_message, elapsed_seconds, created_at
            FROM briefing_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (cap,),
        ).fetchall()

    out: List[Dict] = []
    for row in rows:
        out.append(
            {
                "id": int(row["id"]),
                "topic": row["topic"],
                "email": row["email"] or "",
                "delivered": bool(row["delivered"]),
                "delivery_message": row["delivery_message"] or "",
                "elapsed_seconds": float(row["elapsed_seconds"] or 0.0),
                "created_at": row["created_at"],
            }
        )
    return out


def get_history_entry(entry_id: int) -> Optional[Dict]:
    init_history_store()
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT
                id, topic, email, delivered, delivery_message, elapsed_seconds, html, created_at
            FROM briefing_history
            WHERE id = ?
            """,
            (int(entry_id),),
        ).fetchone()

    if not row:
        return None

    return {
        "id": int(row["id"]),
        "topic": row["topic"],
        "email": row["email"] or "",
        "delivered": bool(row["delivered"]),
        "delivery_message": row["delivery_message"] or "",
        "elapsed_seconds": float(row["elapsed_seconds"] or 0.0),
        "html": row["html"] or "",
        "created_at": row["created_at"],
    }
