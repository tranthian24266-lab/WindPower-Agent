from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class MigrationError(RuntimeError):
    """Raised when a schema migration cannot be applied safely."""


class MigrationRunner:
    def __init__(self, migrations_path: Path):
        self.migrations_path = Path(migrations_path)

    def apply_pending(self, connection: Any) -> list[str]:
        self._ensure_schema_migrations_table(connection)
        applied_versions = self._load_applied_versions(connection)
        executed_versions: list[str] = []

        for path in self._discover_migrations():
            version = path.stem
            if version in applied_versions:
                continue

            sql = path.read_text(encoding="utf-8").strip()
            if not sql:
                raise MigrationError(f"Migration file is empty: {path}")

            try:
                for statement in self._split_statements(sql):
                    connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO schema_migrations (version, filename, applied_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(version) DO NOTHING
                    """,
                    (version, path.name, datetime.now(timezone.utc).isoformat()),
                )
            except Exception as exc:  # pragma: no cover - backend-specific driver exception
                raise MigrationError(f"Failed to apply migration {path.name}: {exc}") from exc

            executed_versions.append(version)

        return executed_versions

    def _discover_migrations(self) -> list[Path]:
        if not self.migrations_path.exists():
            return []
        return sorted(path for path in self.migrations_path.glob("*.sql") if path.is_file())

    def _ensure_schema_migrations_table(self, connection: Any) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )

    def _load_applied_versions(self, connection: Any) -> set[str]:
        rows = connection.execute("SELECT version FROM schema_migrations").fetchall()
        versions: set[str] = set()
        for row in rows:
            if isinstance(row, dict):
                versions.add(str(row["version"]))
            else:
                versions.add(str(row["version"]))
        return versions

    def _split_statements(self, sql: str) -> list[str]:
        statements: list[str] = []
        buffer: list[str] = []
        in_single = False
        in_double = False
        for char in sql:
            if char == "'" and not in_double:
                in_single = not in_single
            elif char == '"' and not in_single:
                in_double = not in_double
            if char == ";" and not in_single and not in_double:
                statement = "".join(buffer).strip()
                buffer = []
                if statement and not statement.upper().startswith("PRAGMA "):
                    statements.append(statement)
                continue
            buffer.append(char)
        trailing = "".join(buffer).strip()
        if trailing and not trailing.upper().startswith("PRAGMA "):
            statements.append(trailing)
        return statements
