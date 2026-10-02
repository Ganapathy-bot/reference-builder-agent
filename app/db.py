"""SQLite cache, traces, candidate snapshots, and the research library."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def init(self) -> None:
        with self._lock:
            self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS cache (
                    cache_key TEXT PRIMARY KEY,
                    body TEXT NOT NULL,
                    stored_at REAL NOT NULL,
                    ttl INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS traces (
                    request_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    input TEXT,
                    status TEXT,
                    trace_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS library (
                    id TEXT PRIMARY KEY,
                    collection TEXT NOT NULL,
                    title TEXT,
                    year INTEGER,
                    doi TEXT,
                    confidence REAL,
                    record_json TEXT NOT NULL,
                    citations_json TEXT,
                    bibtex TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS duplicate_ignores (
                    pair_key TEXT PRIMARY KEY
                );
                """
            )
            self.conn.commit()

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def cache_get(self, key: str) -> Any:
        now = time.time()
        with self._lock:
            row = self.conn.execute(
                "SELECT body, stored_at, ttl FROM cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            if now - row["stored_at"] > row["ttl"]:
                self.conn.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
                self.conn.commit()
                return None
            return json.loads(row["body"])

    def cache_set(self, key: str, payload: Any, ttl: int) -> None:
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO cache (cache_key, body, stored_at, ttl)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    body = excluded.body,
                    stored_at = excluded.stored_at,
                    ttl = excluded.ttl
                """,
                (key, json.dumps(payload), time.time(), ttl),
            )
            self.conn.commit()

    def save_trace(self, request_id: str, raw_input: str, status: str, trace: list[dict]) -> None:
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO traces (request_id, created_at, input, status, trace_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    status = excluded.status,
                    trace_json = excluded.trace_json
                """,
                (request_id, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), raw_input, status, json.dumps(trace)),
            )
            self.conn.commit()

    def get_trace(self, request_id: str) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM traces WHERE request_id = ?", (request_id,)).fetchone()
        if row is None:
            return None
        return {
            "request_id": row["request_id"],
            "created_at": row["created_at"],
            "input": row["input"],
            "status": row["status"],
            "trace": json.loads(row["trace_json"]),
        }

    def save_candidate(self, record: dict) -> str:
        candidate_id = uuid.uuid4().hex[:12]
        with self._lock:
            self.conn.execute(
                "INSERT INTO candidates (candidate_id, record_json, created_at) VALUES (?, ?, ?)",
                (candidate_id, json.dumps(record), time.time()),
            )
            self.conn.commit()
        return candidate_id

    def get_candidate(self, candidate_id: str, ttl: int) -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT record_json, created_at FROM candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        if row is None:
            return None
        if time.time() - row["created_at"] > ttl:
            return None
        return json.loads(row["record_json"])

    def library_add(self, record: dict, collection: str, citations: dict | None, bibtex: str | None) -> dict:
        item_id = uuid.uuid4().hex[:12]
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        title = record.get("title") or ""
        year = record.get("year")
        doi = record.get("doi")
        confidence = record.get("confidence") or 0
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO library (
                    id, collection, title, year, doi, confidence, record_json, citations_json, bibtex, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    (collection or "Inbox").strip() or "Inbox",
                    title,
                    year,
                    doi,
                    confidence,
                    json.dumps(record),
                    json.dumps(citations or {}),
                    bibtex,
                    created,
                ),
            )
            self.conn.commit()
        return self.library_get(item_id) or {"id": item_id}

    def library_get(self, item_id: str) -> dict | None:
        with self._lock:
            row = self.conn.execute("SELECT * FROM library WHERE id = ?", (item_id,)).fetchone()
        return _library_row(row) if row else None

    def library_list(self, collection: str | None = None) -> list[dict]:
        with self._lock:
            if collection:
                rows = self.conn.execute(
                    "SELECT * FROM library WHERE collection = ? ORDER BY created_at DESC",
                    (collection,),
                ).fetchall()
            else:
                rows = self.conn.execute("SELECT * FROM library ORDER BY created_at DESC").fetchall()
        return [_library_row(row) for row in rows]

    def library_delete(self, item_id: str) -> bool:
        with self._lock:
            cur = self.conn.execute("DELETE FROM library WHERE id = ?", (item_id,))
            self.conn.commit()
            return cur.rowcount > 0

    def library_get_many(self, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self._lock:
            rows = self.conn.execute(
                f"SELECT * FROM library WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
        by_id = {row["id"]: _library_row(row) for row in rows}
        return [by_id[item_id] for item_id in ids if item_id in by_id]

    def ignore_pair(self, pair_key: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR IGNORE INTO duplicate_ignores (pair_key) VALUES (?)",
                (pair_key,),
            )
            self.conn.commit()

    def ignored_pairs(self) -> set[str]:
        with self._lock:
            rows = self.conn.execute("SELECT pair_key FROM duplicate_ignores").fetchall()
        return {row["pair_key"] for row in rows}


def _library_row(row: sqlite3.Row) -> dict:
    record = json.loads(row["record_json"])
    return {
        "id": row["id"],
        "collection": row["collection"],
        "title": row["title"],
        "year": row["year"],
        "doi": row["doi"],
        "confidence": row["confidence"],
        "record": record,
        "citations": json.loads(row["citations_json"] or "{}"),
        "bibtex": row["bibtex"],
        "created_at": row["created_at"],
    }
