import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from app.config import get_settings
from app.policies.sql_policy import APPROVED_TABLES, QueryPolicyError, validate_query

SQLiteParameter = str | int | float | bytes | None


class AnalyticsQueryError(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class QueryTimeoutError(AnalyticsQueryError):
    pass


class QueryResultLimitExceeded(AnalyticsQueryError):
    pass


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]

    @property
    def row_count(self) -> int:
        return len(self.rows)


class AnalyticsRepository:
    """Executes policy-checked SELECT queries on the read-only analytics file."""

    def __init__(
        self,
        database_path: Path | None = None,
        *,
        timeout_seconds: float | None = None,
        max_rows: int | None = None,
    ) -> None:
        settings = get_settings()
        configured_path = (
            settings.analytics_db_path if database_path is None else database_path
        )
        self.database_path = Path(configured_path).expanduser().resolve()
        metadata_path = settings.run_metadata_db_path.expanduser().resolve()
        if self.database_path == metadata_path:
            raise ValueError("Analytics and run metadata databases must be separate files.")
        self.timeout_seconds = settings.query_timeout_seconds
        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds
        self.max_rows = settings.query_row_limit if max_rows is None else max_rows
        if self.timeout_seconds <= 0:
            raise ValueError("Query timeout must be greater than zero.")
        if self.max_rows < 1:
            raise ValueError("Query row limit must be at least one.")

    def execute_query(
        self,
        sql: str,
        parameters: Sequence[SQLiteParameter] = (),
    ) -> QueryResult:
        validated = validate_query(sql, max_rows=self.max_rows)
        if not self.database_path.is_file():
            raise AnalyticsQueryError(
                "analytics_database_unavailable",
                "The analytics database is not seeded. Run the documented seed command first.",
            )

        deadline = time.monotonic() + self.timeout_seconds
        database_uri = f"{self.database_path.as_uri()}?mode=ro"
        try:
            with closing(
                sqlite3.connect(
                    database_uri,
                    uri=True,
                    timeout=self.timeout_seconds,
                )
            ) as connection:
                connection.execute("PRAGMA query_only = ON")
                connection.set_authorizer(self._authorize)
                connection.set_progress_handler(
                    lambda: int(time.monotonic() >= deadline), 1000
                )
                cursor = connection.execute(validated.sql, tuple(parameters))
                columns = [description[0] for description in cursor.description or ()]
                rows = [list(row) for row in cursor.fetchmany(self.max_rows + 1)]
        except sqlite3.OperationalError as error:
            message = str(error).casefold()
            if "interrupted" in message or time.monotonic() >= deadline:
                raise QueryTimeoutError(
                    "query_timeout",
                    f"The query exceeded the {self.timeout_seconds:g}-second time limit.",
                ) from error
            if "not authorized" in message or "readonly" in message:
                raise AnalyticsQueryError(
                    "read_only_enforcement", "SQLite rejected a non-read-only operation."
                ) from error
            raise AnalyticsQueryError(
                "query_execution_failed",
                "SQLite could not execute the validated query against the analytics database.",
            ) from error
        except sqlite3.ProgrammingError as error:
            raise AnalyticsQueryError(
                "invalid_query_parameters",
                "The query parameters do not match its positional placeholders.",
            ) from error
        except sqlite3.DatabaseError as error:
            message = str(error).casefold()
            if (
                "not authorized" in message
                or "readonly" in message
                or "read-only" in message
            ):
                raise AnalyticsQueryError(
                    "read_only_enforcement", "SQLite rejected a non-read-only operation."
                ) from error
            raise AnalyticsQueryError(
                "query_execution_failed",
                "SQLite could not execute the validated query against the analytics database.",
            ) from error

        if len(rows) > self.max_rows:
            raise QueryResultLimitExceeded(
                "result_row_limit_exceeded",
                f"The query returned more than the configured {self.max_rows}-row result cap.",
            )
        return QueryResult(columns=columns, rows=rows)

    @staticmethod
    def _authorize(
        action: int,
        first_argument: str | None,
        second_argument: str | None,
        database_name: str | None,
        _trigger_name: str | None,
    ) -> int:
        if action == sqlite3.SQLITE_READ:
            if (
                (first_argument or "").casefold() in APPROVED_TABLES
                and database_name == "main"
            ):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY

        allowed_actions = {
            sqlite3.SQLITE_SELECT,
            sqlite3.SQLITE_FUNCTION,
            getattr(sqlite3, "SQLITE_RECURSIVE", -1),
        }
        if action == sqlite3.SQLITE_FUNCTION:
            function_name = (second_argument or first_argument or "").casefold()
            if function_name in {"load_extension", "readfile", "writefile"}:
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK if action in allowed_actions else sqlite3.SQLITE_DENY
