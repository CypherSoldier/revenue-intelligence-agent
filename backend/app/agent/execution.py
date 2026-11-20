"""Bounded tool execution for an already validated analysis plan."""

import hashlib
import json
import math
from datetime import UTC, datetime
from uuid import uuid4

from pydantic import ValidationError
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError

from app.agent.contracts import ModelMessage, ModelRequest
from app.agent.planning import PlanningResult, interpret_and_plan
from app.agent.tool_contracts import MODEL_TOOLS, RunReadOnlyQueryArguments
from app.data.catalog import get_catalog
from app.database.analytics_repository import (
    AnalyticsQueryError,
    AnalyticsRepository,
    QueryResult,
)
from app.policies.sql_policy import QueryPolicyError
from app.providers.base import ModelProvider
from app.providers.errors import ModelProviderError
from app.schemas.catalog import DataCatalog
from app.schemas.runs import (
    EvidenceReference,
    QueryReference,
    QueryReferenceStatus,
)


MAX_PLAN_STEPS = 6
MAX_TOOL_CALLS = 12
MAX_RETRIES_PER_STEP = 1
MAX_RESULT_COLUMNS = 20
MAX_EVIDENCE_ITEMS = 200


class PlanExecutionError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        step_id: str | None = None,
        queries: list[QueryReference] | None = None,
        evidence: list[EvidenceReference] | None = None,
        retryable: bool = False,
    ):
        self.code = code
        self.step_id = step_id
        self.queries = queries or []
        self.evidence = evidence or []
        self.retryable = retryable
        super().__init__(message)


class PlanExecutionResult:
    def __init__(self, queries: list[QueryReference], evidence: list[EvidenceReference]):
        self.queries = queries
        self.evidence = evidence


class InvestigationExecutionResult:
    def __init__(self, plan: PlanningResult, execution: PlanExecutionResult | None):
        self.plan = plan
        self.execution = execution


def investigate_and_execute(
    question: str,
    provider: ModelProvider,
    repository: AnalyticsRepository | None = None,
    catalog: DataCatalog | None = None,
) -> InvestigationExecutionResult:
    """Interpret first; never start a query when input or scope is unresolved."""
    catalog = catalog or get_catalog()
    plan = interpret_and_plan(question, provider, catalog)
    if plan.decision != "ready":
        return InvestigationExecutionResult(plan, None)
    return InvestigationExecutionResult(
        plan,
        execute_plan(question, plan, provider, repository, catalog),
    )


def execute_plan(
    question: str,
    plan: PlanningResult,
    provider: ModelProvider,
    repository: AnalyticsRepository | None = None,
    catalog: DataCatalog | None = None,
) -> PlanExecutionResult:
    """Generate and execute at most one approved query for each planned step.

    QueryPolicyError and the repository's read-only, timeout, and row-limit
    enforcement remain authoritative. The model gets one correction attempt after
    a rejected query; no retry is made after a successful query.
    """
    if plan.decision != "ready" or plan.metric_id is None:
        raise PlanExecutionError("plan_not_ready", "Only a ready plan can be executed.")
    if not 1 <= len(plan.steps) <= MAX_PLAN_STEPS:
        raise PlanExecutionError("plan_step_limit", "The plan exceeds the step limit.")

    catalog = catalog or get_catalog()
    repository = repository or AnalyticsRepository()
    metric = next((item for item in catalog.metrics if item.id == plan.metric_id), None)
    if metric is None or not set(plan.dimensions).issubset(metric.supported_dimensions):
        raise PlanExecutionError("invalid_plan_scope", "The plan is outside the metric catalog.")

    queries: list[QueryReference] = []
    evidence: list[EvidenceReference] = []
    tool_calls_used = 0

    for step in plan.steps:
        messages = [
            ModelMessage(role="user", content=(
                f"Original question: {question}\n"
                f"Approved metric: {metric.model_dump_json()}\n"
                f"Approved periods: {[period.model_dump(mode='json') for period in plan.periods]}\n"
                f"Approved dimensions: {plan.dimensions}\n"
                f"Current step: {step.title}. {step.summary}\n"
                "Call run_read_only_query exactly once for this step. Use positional ? "
                "placeholders and provide all values in parameters. Query only the "
                "approved metric, periods, and dimensions."
            ))
        ]
        executed = False
        for attempt in range(MAX_RETRIES_PER_STEP + 1):
            arguments = None
            if tool_calls_used >= MAX_TOOL_CALLS:
                raise PlanExecutionError(
                    "tool_call_limit", "The investigation reached its tool-call limit.",
                    step_id=step.step_id, queries=queries, evidence=evidence,
                )
            try:
                response = provider.generate(ModelRequest(
                    system_instruction=_execution_instruction(catalog),
                    messages=messages,
                    tools=[tool for tool in MODEL_TOOLS if tool.name == "run_read_only_query"],
                    temperature=0,
                    max_output_tokens=2048,
                ))
            except ModelProviderError as error:
                raise PlanExecutionError(
                    error.code, error.message, step_id=step.step_id,
                    queries=queries, evidence=evidence, retryable=error.retryable,
                ) from error
            tool_calls_used += len(response.tool_calls)
            if tool_calls_used > MAX_TOOL_CALLS:
                raise PlanExecutionError(
                    "tool_call_limit", "The investigation reached its tool-call limit.",
                    step_id=step.step_id, queries=queries, evidence=evidence,
                )
            if len(response.tool_calls) != 1 or response.tool_calls[0].name != "run_read_only_query":
                raise PlanExecutionError(
                    "invalid_tool_call", "The model must request exactly one read-only query per step.",
                    step_id=step.step_id, queries=queries, evidence=evidence,
                )

            call = response.tool_calls[0]
            call_id = call.id or f"{step.step_id}-{attempt + 1}"
            messages.append(ModelMessage(
                role="assistant", content=response.text or "Query request.",
                provider_context=response.provider_context,
            ))
            try:
                arguments = RunReadOnlyQueryArguments.model_validate(call.arguments)
                validate_plan_query(arguments.sql, arguments.parameters, plan, metric.id)
                query_result = repository.execute_query(arguments.sql, arguments.parameters)
                validate_query_result(query_result, repository.max_rows)
                if len(evidence) + query_result.row_count > MAX_EVIDENCE_ITEMS:
                    raise ValueError("The investigation exceeded the 200-item evidence limit.")
                query_ref = _query_reference(
                    step.step_id, arguments.sql, arguments.parameters,
                    QueryReferenceStatus.COMPLETED, query_result.row_count,
                )
                queries.append(query_ref)
                evidence.extend(_evidence_for_result(
                    step.step_id, query_ref, metric.name,
                    " and ".join(period.label for period in plan.periods), query_result,
                ))
                messages.append(ModelMessage(
                    role="tool", tool_name=call.name, tool_call_id=call_id,
                    tool_result={
                        "ok": True, "query_id": str(query_ref.id),
                        "columns": query_result.columns, "rows": query_result.rows,
                    },
                ))
                executed = True
                break
            except (ValidationError, QueryPolicyError, AnalyticsQueryError, ValueError) as error:
                if isinstance(error, QueryPolicyError):
                    code, message = error.code, error.message
                elif isinstance(error, AnalyticsQueryError):
                    code, message = error.code, error.message
                else:
                    code, message = "invalid_tool_arguments", "The query arguments or result were invalid."
                if isinstance(arguments, RunReadOnlyQueryArguments):
                    query_status = (
                        QueryReferenceStatus.REJECTED
                        if isinstance(error, QueryPolicyError)
                        else QueryReferenceStatus.FAILED
                    )
                    query_ref = _query_reference(
                        step.step_id, arguments.sql, arguments.parameters,
                        query_status, None,
                    )
                    queries.append(query_ref)
                messages.append(ModelMessage(
                    role="tool", tool_name=call.name, tool_call_id=call_id,
                    tool_result={"ok": False, "code": code, "message": message},
                ))
                if attempt >= MAX_RETRIES_PER_STEP:
                    raise PlanExecutionError(
                        code, message, step_id=step.step_id,
                        queries=queries, evidence=evidence,
                    ) from error
        if not executed:
            raise PlanExecutionError(
                "step_not_executed", "A planned step did not produce a validated result.",
                step_id=step.step_id, queries=queries, evidence=evidence,
            )
    return PlanExecutionResult(queries, evidence)


def validate_query_result(result: QueryResult, max_rows: int) -> None:
    if not result.columns or len(result.columns) > MAX_RESULT_COLUMNS:
        raise ValueError("Query results must contain between 1 and 20 columns.")
    if len(set(result.columns)) != len(result.columns):
        raise ValueError("Query result column names must be unique.")
    if result.row_count > max_rows:
        raise ValueError("Query result exceeded the configured row limit.")
    for row in result.rows:
        if len(row) != len(result.columns):
            raise ValueError("A result row does not match its declared columns.")
        for value in row:
            if not (value is None or isinstance(value, (str, int, float, bool))):
                raise ValueError("Query results may contain only JSON scalar values.")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError("Query results cannot contain non-finite numbers.")


def validate_plan_query(sql: str, parameters: list, plan: PlanningResult, metric_id: str) -> None:
    """Reject catalog-valid SQL that does not answer the approved plan."""
    try:
        statement = parse_one(sql, read="sqlite")
    except ParseError as error:
        raise QueryPolicyError("invalid_sql", "The SQL could not be parsed.") from error

    metric_column = metric_id.casefold()
    has_metric = any(
        isinstance(node, exp.Sum)
        and any(
            isinstance(column, exp.Column)
            and column.name.casefold() == metric_column
            for column in node.find_all(exp.Column)
        )
        for node in statement.walk()
    )
    has_time_column = any(
        isinstance(column, exp.Column)
        and column.name.casefold() == "month_start"
        for column in statement.find_all(exp.Column)
    )
    placeholder_count = sum(1 for _ in statement.find_all(exp.Placeholder))
    required_dates = {
        boundary
        for period in plan.periods
        for boundary in (period.start.isoformat(), period.end_exclusive.isoformat())
    }
    bound_dates = {value for value in parameters if isinstance(value, str)}
    if (
        not has_metric
        or not has_time_column
        or placeholder_count < len(required_dates)
        or not required_dates.issubset(bound_dates)
    ):
        raise QueryPolicyError(
            "plan_scope_mismatch",
            "The query must aggregate the approved metric and bind every approved period boundary.",
        )

    selected_columns = {
        column.name.casefold()
        for selected in statement.expressions
        for column in selected.find_all(exp.Column)
    }
    if "region" not in plan.dimensions and "region" in selected_columns:
        raise QueryPolicyError(
            "plan_scope_mismatch", "The query selected a region breakdown not present in the plan."
        )


def _query_reference(
    step_id: str,
    sql: str,
    parameters: list | tuple,
    status: QueryReferenceStatus,
    row_count: int | None,
) -> QueryReference:
    digest_input = json.dumps(
        {"sql": sql, "parameters": parameters}, sort_keys=True,
        separators=(",", ":"), ensure_ascii=False,
    )
    return QueryReference(
        id=uuid4(), step_id=step_id,
        query_hash=hashlib.sha256(digest_input.encode("utf-8")).hexdigest(),
        sql=sql, status=status, row_count=row_count,
        executed_at=(datetime.now(UTC) if status == QueryReferenceStatus.COMPLETED else None),
    )


def _evidence_for_result(
    step_id: str,
    query: QueryReference,
    metric: str,
    period: str,
    result: QueryResult,
) -> list[EvidenceReference]:
    items = []
    for index, row in enumerate(result.rows, start=1):
        values = dict(zip(result.columns, row, strict=True))
        items.append(EvidenceReference(
            id=uuid4(), step_id=step_id, query_id=query.id,
            label=f"{metric} result row {index}", metric=metric, period=period,
            summary="Executed query result: " + json.dumps(values, ensure_ascii=False),
            values=values,
        ))
    return items


def _execution_instruction(catalog: DataCatalog) -> str:
    return f"""You produce SQL for one approved plan step. The only available schema is:
{catalog.model_dump_json(indent=2)}
Use only run_read_only_query, exactly once. The server enforces read-only SQL,
approved tables, bound parameters, timeout, and row limits. Never query outside the
approved metric, dates, or dimensions supplied with the step. Return no SQL in text.
If a query is rejected, correct it using the tool error. Do not claim results that
the tool did not return."""
