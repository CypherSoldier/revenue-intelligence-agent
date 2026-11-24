import re
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.data.seed import seed_analytics_database
from app.main import app
from app.agent.contracts import ModelResponse, ModelToolCall
from app.providers.errors import ModelProviderError
from app.database.analytics_repository import QueryResult


class FakeProvider:
    provider_name = "test"
    model_name = "fake"

    def __init__(self, mode="success"):
        self.mode = mode

    def generate(self, request):
        if self.mode == "failure":
            raise ModelProviderError(
                "provider_unavailable", "The fake provider failed.", provider="test"
            )
        if self.mode == "timeout":
            raise ModelProviderError(
                "provider_timeout", "The fake provider timed out.",
                provider="test", retryable=True,
            )

        if request.tools:
            if self.mode == "tool_budget":
                call = ModelToolCall(
                    id="query-budget",
                    name="run_read_only_query",
                    arguments={"sql": "SELECT 1", "parameters": []},
                )
                return ModelResponse(
                    provider=self.provider_name,
                    model=self.model_name,
                    tool_calls=[call] * 13,
                )
            if self.mode == "invalid_arguments":
                return ModelResponse(
                    provider=self.provider_name,
                    model=self.model_name,
                    tool_calls=[ModelToolCall(
                        id="query-invalid",
                        name="run_read_only_query",
                        arguments={"sql": "SELECT 1", "parameters": "not-a-list"},
                    )],
                )
            sql = (
                "SELECT SUM(net_revenue_usd) AS total_usd FROM monthly_sales WHERE month_start >= ? AND month_start < ? AND readfile('secret') IS NULL"
                if self.mode == "unsafe_query"
                else "SELECT SUM(net_revenue_usd) AS total_usd FROM monthly_sales WHERE month_start >= ? AND month_start < ?"
            )
            return ModelResponse(
                provider=self.provider_name,
                model=self.model_name,
                tool_calls=[ModelToolCall(
                    id="query-1",
                    name="run_read_only_query",
                    arguments={
                        "sql": sql,
                        "parameters": ["2025-01-01", "2025-04-01"],
                    },
                )],
            )

        properties = (request.response_schema or {}).get("properties", {})
        if "decision" in properties:
            if self.mode == "clarification":
                output = {
                    "decision": "needs_input",
                    "message": "Which year should I use for Q1?",
                    "metric_id": None,
                    "periods": [],
                    "dimensions": [],
                    "steps": [],
                }
            else:
                output = {
                    "decision": "ready",
                    "message": "Sum net revenue for Q1 2025.",
                    "metric_id": "net_revenue_usd",
                    "periods": [{
                        "label": "Q1 2025",
                        "start": "2025-01-01",
                        "end_exclusive": "2025-04-01",
                    }],
                    "dimensions": [],
                    "steps": [{
                        "step_id": "step_1",
                        "title": "Calculate Q1 revenue",
                        "summary": "Sum monthly net revenue for Q1 2025.",
                    }],
                }
            return ModelResponse(
                provider=self.provider_name,
                model=self.model_name,
                structured_output=output,
            )

        user_content = request.messages[-1].content or ""
        evidence_id = re.search(r"['\"]id['\"]:\s*['\"]([0-9a-f-]{36})", user_content)
        findings = []
        if evidence_id:
            findings = [{
                "text": "Q1 net revenue totals $1.2 million.",
                "evidence_ids": [str(UUID(evidence_id.group(1)))],
            }]
        return ModelResponse(
            provider=self.provider_name,
            model=self.model_name,
            structured_output={
                "answer": "Net revenue for Q1 2025 was $1.2 million.",
                "findings": findings,
                "caveats": [],
            },
        )

    def close(self):
        pass


@pytest.fixture
def configured_app(tmp_path, monkeypatch):
    analytics_path = tmp_path / "analytics.sqlite3"
    metadata_path = tmp_path / "run-metadata.sqlite3"
    seed_analytics_database(analytics_path)
    monkeypatch.setenv("ANALYTICS_DB_PATH", str(analytics_path))
    monkeypatch.setenv("RUN_METADATA_DB_PATH", str(metadata_path))
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-configured-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("mode", "question", "expected_status"),
    [
        ("success", "How much net revenue in Q1 2025?", "completed"),
        ("clarification", "How much net revenue in Q1?", "needs_input"),
        ("failure", "How much net revenue in Q1 2025?", "failed"),
    ],
)
def test_api_persists_success_clarification_and_failure(
    configured_app, monkeypatch, mode, question, expected_status
):
    monkeypatch.setattr(
        "app.services.investigation_workflow.get_model_provider",
        lambda: FakeProvider(mode),
    )

    with TestClient(app) as client:
        submitted = client.post("/runs", json={"question": question})
        assert submitted.status_code == 202
        run_id = submitted.json()["id"]
        reloaded = client.get(f"/runs/{run_id}")

    assert reloaded.status_code == 200
    run = reloaded.json()
    assert run["status"] == expected_status

    if mode == "success":
        assert run["report"]["answer"]
        assert run["steps"][0]["status"] == "completed"
        assert run["query_references"][0]["status"] == "completed"
        evidence = run["evidence_references"]
        assert evidence
        assert evidence[0]["query_id"] == run["query_references"][0]["id"]
        assert evidence[0]["metric"] == "Net revenue"
        assert evidence[0]["period"] == "Q1 2025"
        assert evidence[0]["values"] == {"total_usd": 1_200_000}
        assert run["report"]["findings"][0]["evidence_ids"] == [evidence[0]["id"]]
        assert any("causal" in caveat.casefold() for caveat in run["report"]["caveats"])
    elif mode == "clarification":
        assert "Which year" in run["clarification"]
        assert run["report"] is None
        assert run["query_references"] == []
    else:
        assert run["failure"]["code"] == "provider_unavailable"
        assert run["report"] is None


def test_api_retries_rejected_query_once_then_persists_failure(configured_app, monkeypatch):
    monkeypatch.setattr(
        "app.services.investigation_workflow.get_model_provider",
        lambda: FakeProvider("unsafe_query"),
    )

    with TestClient(app) as client:
        submitted = client.post("/runs", json={"question": "How much net revenue in Q1 2025?"})
        run = client.get(f"/runs/{submitted.json()['id']}").json()

    assert submitted.status_code == 202
    assert run["status"] == "failed"
    assert run["report"] is None
    assert run["failure"]["code"] == "function_not_allowed"
    assert [query["status"] for query in run["query_references"]] == ["rejected", "rejected"]
    assert len(run["query_references"]) == 2


def test_api_enforces_tool_call_budget(configured_app, monkeypatch):
    monkeypatch.setattr(
        "app.services.investigation_workflow.get_model_provider",
        lambda: FakeProvider("tool_budget"),
    )

    with TestClient(app) as client:
        submitted = client.post("/runs", json={"question": "How much net revenue in Q1 2025?"})
        run = client.get(f"/runs/{submitted.json()['id']}").json()

    assert run["status"] == "failed"
    assert run["failure"]["code"] == "tool_call_limit"
    assert run["report"] is None
    assert run["query_references"] == []


@pytest.mark.parametrize(
    ("payload", "status"),
    [({"question": "   "}, 422), ({"question": "x" * 2001}, 422), ({}, 422)],
)
def test_api_rejects_malformed_questions(configured_app, payload, status):
    response = TestClient(app).post("/runs", json=payload)
    assert response.status_code == status


@pytest.mark.parametrize(
    ("mode", "code"),
    [("timeout", "provider_timeout"), ("invalid_arguments", "invalid_tool_arguments")],
)
def test_api_keeps_timeout_and_invalid_tool_arguments_visible(
    configured_app, monkeypatch, mode, code
):
    monkeypatch.setattr(
        "app.services.investigation_workflow.get_model_provider",
        lambda: FakeProvider(mode),
    )

    with TestClient(app) as client:
        submitted = client.post("/runs", json={"question": "How much net revenue in Q1 2025?"})
        run = client.get(f"/runs/{submitted.json()['id']}").json()

    assert run["status"] == "failed"
    assert run["failure"]["code"] == code
    assert run["report"] is None


def test_api_repeated_submits_create_independent_runs(configured_app, monkeypatch):
    monkeypatch.setattr(
        "app.services.investigation_workflow.get_model_provider",
        lambda: FakeProvider("success"),
    )

    with TestClient(app) as client:
        first = client.post("/runs", json={"question": "How much net revenue in Q1 2025?"})
        second = client.post("/runs", json={"question": "How much net revenue in Q1 2025?"})
        first_run = client.get(f"/runs/{first.json()['id']}").json()
        second_run = client.get(f"/runs/{second.json()['id']}").json()

    assert first.status_code == second.status_code == 202
    assert first_run["id"] != second_run["id"]
    assert first_run["status"] == second_run["status"] == "completed"
    assert first_run["evidence_references"][0]["id"] != second_run["evidence_references"][0]["id"]


def test_api_surfaces_missing_analytics_database(configured_app, monkeypatch, tmp_path):
    monkeypatch.setenv("ANALYTICS_DB_PATH", str(tmp_path / "missing.sqlite3"))
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.investigation_workflow.get_model_provider",
        lambda: FakeProvider("success"),
    )

    with TestClient(app) as client:
        submitted = client.post("/runs", json={"question": "How much net revenue in Q1 2025?"})
        run = client.get(f"/runs/{submitted.json()['id']}").json()

    assert run["status"] == "failed"
    assert run["failure"]["code"] == "analytics_database_unavailable"
    assert run["report"] is None


def test_empty_query_result_cannot_become_a_revenue_claim(configured_app, monkeypatch):
    monkeypatch.setattr(
        "app.services.investigation_workflow.get_model_provider",
        lambda: FakeProvider("success"),
    )
    monkeypatch.setattr(
        "app.agent.execution.AnalyticsRepository.execute_query",
        lambda self, sql, parameters=(): QueryResult(columns=["total_usd"], rows=[]),
    )

    with TestClient(app) as client:
        submitted = client.post("/runs", json={"question": "How much net revenue in Q1 2025?"})
        run = client.get(f"/runs/{submitted.json()['id']}").json()

    assert run["status"] == "completed"
    assert run["report"]["answer"] == (
        "No rows were returned for the requested period, so this run "
        "cannot support a revenue conclusion."
    )
    assert run["report"]["findings"] == []
    assert run["evidence_references"] == []
    assert any("empty" in caveat.casefold() for caveat in run["report"]["caveats"])
