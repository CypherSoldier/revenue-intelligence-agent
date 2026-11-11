import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.config import get_settings
from app.schemas.runs import RunResponse, RunStatus


def _database_paths() -> tuple[Path, Path]:
    settings = get_settings()
    analytics_path = settings.analytics_db_path.expanduser().resolve()
    metadata_path = settings.run_metadata_db_path.expanduser().resolve()
    if analytics_path == metadata_path:
        raise ValueError("Analytics and run metadata databases must be separate files.")
    return analytics_path, metadata_path


def initialize_run_store() -> None:
    _, metadata_path = _database_paths()
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(metadata_path)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_code TEXT,
                    error_message TEXT
                )
                """
            )


def create_run(question: str) -> RunResponse:
    _, metadata_path = _database_paths()
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = uuid4()
    timestamp = datetime.now(UTC)
    timestamp_text = timestamp.isoformat()
    with closing(sqlite3.connect(metadata_path)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO analysis_runs
                    (id, question, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(run_id),
                    question,
                    RunStatus.QUEUED.value,
                    timestamp_text,
                    timestamp_text,
                ),
            )
    return RunResponse(
        id=run_id,
        question=question,
        status=RunStatus.QUEUED,
        created_at=timestamp,
        updated_at=timestamp,
    )


def get_run(run_id: UUID) -> RunResponse | None:
    _, metadata_path = _database_paths()
    if not metadata_path.exists():
        return None
    with closing(sqlite3.connect(metadata_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id, question, status, created_at, updated_at,
                   error_code, error_message
            FROM analysis_runs
            WHERE id = ?
            """,
            (str(run_id),),
        ).fetchone()
    if row is None:
        return None
    return RunResponse(
        id=row["id"],
        question=row["question"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error_code=row["error_code"],
        error_message=row["error_message"],
    )
