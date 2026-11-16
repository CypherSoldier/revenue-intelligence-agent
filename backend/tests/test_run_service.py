import sqlite3
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.data.seed import seed_analytics_database
from app.main import app
from app.schemas.runs import (
    EvidenceReference,
    FailureDetails,
    PlanStepSummary,
    QueryReference,
    QueryReferenceStatus,
    ReportFinding,
    RunReport,
    RunStatus,
    RunUpdate,
    StepStatus,
)
from app.services.run_service import (
    InvalidRunTransitionError,
    update_run,
)


@pytest.fixture
def database_paths(tmp_path, monkeypatch):
    analytics_path = tmp_path / "analytics.sqlite3"
    metadata_path = tmp_path / "run-metadata.sqlite3"
    seed_analytics_database(analytics_path)
    monkeypatch.setenv("ANALYTICS_DB_PATH", str(analytics_path))
    monkeypatch.setenv("RUN_METADATA_DB_PATH", str(metadata_path))
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-configured-key")
    get_settings.cache_clear()
    yield analytics_path, metadata_path
    get_settings.cache_clear()


def test_api_creates_and_reloads_run_after_app_restart(database_paths):
    _, metadata_path = database_paths
    with TestClient(app) as first_client:
        created = first_client.post(
            "/runs", json={"question": "Compare Q2 2025 with Q1 2025"}
        )

    assert created.status_code == 202
    run_id = created.json()["id"]
    assert created.json()["status"] == "queued"
    assert created.json()["steps"] == []
    assert created.json()["query_references"] == []
    assert created.json()["evidence_references"] == []

    with TestClient(app) as second_client:
        reloaded = second_client.get(f"/runs/{run_id}")

    assert reloaded.status_code == 200
    assert reloaded.json()["question"] == "Compare Q2 2025 with Q1 2025"
    assert reloaded.json()["status"] == "queued"
    assert metadata_path.exists()


def test_run_service_persists_plan_queries_evidence_and_report(database_paths):
    analytics_path, metadata_path = database_paths
    with TestClient(app):
        # The app lifespan initializes the metadata schema before service calls.
        from app.services.run_service import create_run, get_run

        run = create_run("Compare Q2 with Q1")
        step_id = "compare-periods"
        query_id = uuid4()
        evidence_id = uuid4()
        query_sql = "SELECT SUM(net_revenue_usd) AS total FROM monthly_sales"
        step = PlanStepSummary(
            step_id=step_id,
            sequence=1,
            title="Compare periods",
            summary="Compare total net revenue in Q1 and Q2 2025.",
            status=StepStatus.COMPLETED,
        )
        query = QueryReference(
            id=query_id,
            step_id=step_id,
            query_hash="a" * 64,
            sql=query_sql,
            status=QueryReferenceStatus.COMPLETED,
            row_count=2,
            executed_at=datetime.now(UTC),
        )
        evidence = EvidenceReference(
            id=evidence_id,
            step_id=step_id,
            query_id=query_id,
            label="Quarter totals",
            metric="net_revenue_usd",
            period="Q1 and Q2 2025",
            summary="Q1 was $1.2m and Q2 was $1.0m.",
            values={"q1_usd": 1_200_000, "q2_usd": 1_000_000},
        )
        report = RunReport(
            answer="Net revenue declined by $200,000, or 16.7%.",
            findings=[
                ReportFinding(
                    text="Q2 was $200,000 below Q1.", evidence_ids=[evidence_id]
                )
            ],
            caveats=["The comparison is descriptive and does not establish cause."],
        )

        update_run(
            run.id,
            RunUpdate(
                status=RunStatus.PLANNING,
                plan_summary="Compare the two calendar quarters.",
                steps=[step.model_copy(update={"status": StepStatus.QUEUED})],
            ),
        )
        update_run(
            run.id,
            RunUpdate(
                status=RunStatus.RUNNING,
                steps=[step],
                query_references=[query],
                evidence_references=[evidence],
            ),
        )
        update_run(run.id, RunUpdate(status=RunStatus.VALIDATING))
        completed = update_run(
            run.id,
            RunUpdate(status=RunStatus.COMPLETED, report=report),
        )
        reloaded = get_run(run.id)

    assert reloaded == completed
    assert reloaded is not None
    assert reloaded.status == RunStatus.COMPLETED
    assert reloaded.steps[0].step_id == step_id
    assert reloaded.query_references[0].sql == query_sql
    assert reloaded.evidence_references[0].query_id == query_id
    assert reloaded.report is not None
    assert reloaded.report.findings[0].evidence_ids == [evidence_id]

    with sqlite3.connect(metadata_path) as metadata:
        assert metadata.execute(
            "SELECT COUNT(*) FROM analysis_runs"
        ).fetchone()[0] == 1
        tables = {
            row[0]
            for row in metadata.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert tables == {"analysis_runs"}
    with sqlite3.connect(analytics_path) as analytics:
        assert analytics.execute(
            "SELECT COUNT(*) FROM monthly_sales"
        ).fetchone()[0] == 18
        tables = {
            row[0]
            for row in analytics.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert tables == {"monthly_sales"}


def test_failed_run_persists_failure_details_and_legacy_error_fields(database_paths):
    with TestClient(app):
        from app.services.run_service import create_run, get_run

        run = create_run("Compare Q2 with Q1")
        failed = update_run(
            run.id,
            RunUpdate(
                status=RunStatus.FAILED,
                failure=FailureDetails(
                    code="provider_timeout",
                    message="The model provider did not respond in time.",
                    retryable=True,
                ),
            ),
        )
        reloaded = get_run(run.id)

    assert reloaded == failed
    assert reloaded is not None
    assert reloaded.failure is not None
    assert reloaded.failure.code == "provider_timeout"
    assert reloaded.failure.retryable is True
    assert reloaded.error_code == "provider_timeout"


def test_run_service_rejects_skipping_directly_from_queued_to_completed(database_paths):
    with TestClient(app):
        from app.services.run_service import create_run, get_run

        run = create_run("Compare Q2 with Q1")
        with pytest.raises(InvalidRunTransitionError, match="cannot move"):
            update_run(
                run.id,
                RunUpdate(
                    status=RunStatus.COMPLETED,
                    report=RunReport(answer="Incomplete workflow."),
                ),
            )
        reloaded = get_run(run.id)

    assert reloaded is not None
    assert reloaded.status == RunStatus.QUEUED


def test_run_service_rejects_dangling_evidence_reference(database_paths):
    with TestClient(app):
        from app.services.run_service import create_run

        run = create_run("Compare Q2 with Q1")
        step = PlanStepSummary(
            step_id="compare",
            sequence=1,
            title="Compare periods",
            summary="Compare the periods.",
            status=StepStatus.COMPLETED,
        )
        report = RunReport(
            answer="The answer.",
            findings=[ReportFinding(text="Finding", evidence_ids=[uuid4()])],
        )

        with pytest.raises(InvalidRunTransitionError, match="unknown evidence"):
            update_run(
                run.id,
                RunUpdate(
                    status=RunStatus.PLANNING,
                    steps=[step],
                    report=report,
                ),
            )


def test_run_store_migrates_existing_day_two_database(tmp_path, monkeypatch):
    analytics_path = tmp_path / "analytics.sqlite3"
    metadata_path = tmp_path / "run-metadata.sqlite3"
    existing_run_id = str(uuid4())
    with sqlite3.connect(metadata_path) as connection:
        connection.execute(
            """
            CREATE TABLE analysis_runs (
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
        connection.execute(
            """
            INSERT INTO analysis_runs
                (id, question, status, created_at, updated_at)
            VALUES (?, ?, 'queued', '2026-11-13T00:00:00+00:00',
                    '2026-11-13T00:00:00+00:00')
            """,
            (existing_run_id, "Legacy run"),
        )
    monkeypatch.setenv("ANALYTICS_DB_PATH", str(analytics_path))
    monkeypatch.setenv("RUN_METADATA_DB_PATH", str(metadata_path))
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.get(f"/runs/{existing_run_id}")

    get_settings.cache_clear()
    assert response.status_code == 200
    assert response.json()["question"] == "Legacy run"
    assert response.json()["steps"] == []
    assert response.json()["report"] is None
