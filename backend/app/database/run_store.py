import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.config import get_settings
from app.schemas.runs import RunResponse, RunStatus


_ADDITIVE_COLUMNS = {
    "plan_summary": "TEXT",
    "steps_json": "TEXT NOT NULL DEFAULT '[]'",
    "query_references_json": "TEXT NOT NULL DEFAULT '[]'",
    "evidence_references_json": "TEXT NOT NULL DEFAULT '[]'",
    "report_json": "TEXT",
    "failure_json": "TEXT",
}


def _database_paths() -> tuple[Path, Path]:
    settings = get_settings()
    analytics_path = settings.analytics_db_path.expanduser().resolve()
    metadata_path = settings.run_metadata_db_path.expanduser().resolve()
    if analytics_path == metadata_path:
        raise ValueError("Analytics and run metadata databases must be separate files.")
    return analytics_path, metadata_path


def _connect_metadata() -> sqlite3.Connection:
    _, metadata_path = _database_paths()
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(metadata_path)


def initialize_run_store() -> None:
    with closing(_connect_metadata()) as connection, connection:
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
        existing_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(analysis_runs)").fetchall()
        }
        for column, definition in _ADDITIVE_COLUMNS.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE analysis_runs ADD COLUMN {column} {definition}"
                )


def create_run(question: str) -> RunResponse:
    run_id = uuid4()
    timestamp = datetime.now(UTC)
    with closing(_connect_metadata()) as connection, connection:
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
                timestamp.isoformat(),
                timestamp.isoformat(),
            ),
        )
    return RunResponse(
        id=run_id,
        question=question,
        status=RunStatus.QUEUED,
        created_at=timestamp,
        updated_at=timestamp,
    )


def save_run(run: RunResponse) -> RunResponse | None:
    with closing(_connect_metadata()) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE analysis_runs
            SET status = ?, updated_at = ?, plan_summary = ?, steps_json = ?,
                query_references_json = ?, evidence_references_json = ?,
                report_json = ?, failure_json = ?, error_code = ?, error_message = ?
            WHERE id = ?
            """,
            (
                run.status.value,
                run.updated_at.isoformat(),
                run.plan_summary,
                _json_for_models(run.steps),
                _json_for_models(run.query_references),
                _json_for_models(run.evidence_references),
                run.report.model_dump_json() if run.report else None,
                run.failure.model_dump_json() if run.failure else None,
                run.error_code,
                run.error_message,
                str(run.id),
            ),
        )
        if cursor.rowcount == 0:
            return None
    return run


def get_run(run_id: UUID) -> RunResponse | None:
    _, metadata_path = _database_paths()
    if not metadata_path.exists():
        return None
    with closing(sqlite3.connect(metadata_path)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT id, question, status, created_at, updated_at,
                   error_code, error_message, plan_summary, steps_json,
                   query_references_json, evidence_references_json,
                   report_json, failure_json
            FROM analysis_runs
            WHERE id = ?
            """,
            (str(run_id),),
        ).fetchone()
    if row is None:
        return None

    failure = _load_model(row["failure_json"])
    if failure is None and (row["error_code"] or row["error_message"]):
        failure = {
            "code": row["error_code"] or "run_failed",
            "message": row["error_message"] or "The run failed.",
            "retryable": False,
        }

    return RunResponse(
        id=row["id"],
        question=row["question"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        plan_summary=row["plan_summary"],
        steps=_load_models(row["steps_json"]),
        query_references=_load_models(row["query_references_json"]),
        evidence_references=_load_models(row["evidence_references_json"]),
        report=_load_model(row["report_json"]),
        failure=failure,
        error_code=row["error_code"],
        error_message=row["error_message"],
    )


def _json_for_models(models: list) -> str:
    return json.dumps(
        [model.model_dump(mode="json") for model in models],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _load_models(value: str | None) -> list[dict]:
    return json.loads(value) if value else []


def _load_model(value: str | None) -> dict | None:
    return json.loads(value) if value else None
