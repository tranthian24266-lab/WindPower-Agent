from __future__ import annotations

from collections.abc import Iterable
import importlib
import os
from pathlib import Path
import sqlite3
from typing import Any

from app.db.migration_runner import MigrationRunner
from app.db.models import SCHEMA_STATEMENTS


def _rewrite_qmark_to_percent_s(sql: str) -> str:
    buffer: list[str] = []
    in_single = False
    in_double = False
    index = 0
    while index < len(sql):
        char = sql[index]
        if char == "'" and not in_double:
            in_single = not in_single
            buffer.append(char)
        elif char == '"' and not in_single:
            in_double = not in_double
            buffer.append(char)
        elif char == "?" and not in_single and not in_double:
            buffer.append("%s")
        else:
            buffer.append(char)
        index += 1
    return "".join(buffer)


class DatabaseConnection:
    """Unified connection wrapper for SQLite and PostgreSQL."""

    def __init__(self, inner: Any, *, backend_name: str):
        self._inner = inner
        self.backend_name = backend_name

    def execute(self, sql: str, parameters: Iterable[Any] = ()) -> Any:
        normalized_sql = _rewrite_qmark_to_percent_s(sql) if self.backend_name == "postgresql" else sql
        return self._inner.execute(normalized_sql, tuple(parameters))

    def executemany(self, sql: str, parameters: list[tuple[Any, ...]]) -> Any:
        normalized_sql = _rewrite_qmark_to_percent_s(sql) if self.backend_name == "postgresql" else sql
        return self._inner.executemany(normalized_sql, parameters)

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()

    def close(self) -> None:
        self._inner.close()

    def __enter__(self) -> DatabaseConnection:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()


class Database:
    _default_database_url: str | None = None

    def __init__(self, database_path: Path, database_url: str | None = None):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_database_url = database_url or self._default_database_url or os.getenv("WINDPOWER_DATABASE_URL")
        self.database_url = (resolved_database_url or "").strip() or None
        self.backend_name = "postgresql" if self.database_url and self.database_url.startswith("postgresql://") else "sqlite"
        self.migration_runner = MigrationRunner(Path(__file__).resolve().parent / "migrations")

    @classmethod
    def configure_default_database_url(cls, database_url: str | None) -> None:
        cls._default_database_url = (database_url or "").strip() or None

    def connect(self) -> DatabaseConnection:
        if self.backend_name == "postgresql":
            psycopg2 = importlib.import_module("psycopg2")
            extras = importlib.import_module("psycopg2.extras")
            connection = psycopg2.connect(self.database_url, cursor_factory=extras.RealDictCursor)
            return DatabaseConnection(connection, backend_name="postgresql")
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return DatabaseConnection(connection, backend_name="sqlite")

    def initialize(self) -> None:
        with self.connect() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            self.migration_runner.apply_pending(connection)
