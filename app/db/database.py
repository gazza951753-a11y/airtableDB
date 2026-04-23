import sqlite3
import threading
from contextlib import contextmanager

from pathlib import Path
from typing import Any, Iterable


class Database:
    """Потокобезопасная обёртка над sqlite3 с единым подключением."""
    """Тонкая обёртка над sqlite3 с единым подключением и Row-доступом."""


    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._lock = threading.RLock()

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)

        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
        with self._lock:
            if self.conn:
                self.conn.close()
                self.conn = None


    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        if not self.conn:
            raise RuntimeError("База данных не подключена")
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur
        with self._lock:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur


    def executemany(self, sql: str, params: Iterable[tuple[Any, ...]]) -> sqlite3.Cursor:
        if not self.conn:
            raise RuntimeError("База данных не подключена")
        cur = self.conn.cursor()
        cur.executemany(sql, params)
        return cur

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        return list(self.execute(sql, params).fetchall())

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        return self.execute(sql, params).fetchone()

    def transaction(self):
        if not self.conn:
            raise RuntimeError("База данных не подключена")
        return self.conn
        with self._lock:
            cur = self.conn.cursor()
            cur.executemany(sql, params)
            return cur

    def query_all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self.execute(sql, params).fetchall())

    def query_one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.execute(sql, params).fetchone()

    @contextmanager
    def transaction(self):
        if not self.conn:
            raise RuntimeError("База данных не подключена")
        with self._lock:
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()

