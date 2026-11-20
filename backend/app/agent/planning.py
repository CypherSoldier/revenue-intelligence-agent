"""Bounded question interpretation and plan generation.

This module deliberately stops before query generation or execution. Model output
is treated as untrusted and must fit both the response schema and data catalog.
"""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.agent.contracts import ModelMessage, ModelRequest
from app.data.catalog import get_catalog
from app.providers.base import ModelProvider
from app.schemas.catalog import DataCatalog


class Period(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    start: date
    end_exclusive: date

    @field_validator("end_exclusive")
    @classmethod
    def period_must_be_ordered(cls, value: date, info):
        start = info.data.get("start")
        if start is not None and value <= start:
            raise ValueError("A period end must be later than its start.")
        return value


class PlannedStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(pattern=r"^step_[1-6]$")
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1000)


class Interpretation(BaseModel):
    """Strict provider output; non-ready decisions must not carry query scope."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["ready", "needs_input", "unsupported"]
    message: str = Field(min_length=1, max_length=2000)
    metric_id: str | None = Field(default=None, max_length=100)
    periods: list[Period] = Field(default_factory=list, max_length=2)
    dimensions: list[str] = Field(default_factory=list, max_length=4)
    steps: list[PlannedStep] = Field(default_factory=list, max_length=6)


class PlanningResult(BaseModel):
    decision: Literal["ready", "needs_input", "unsupported"]
    message: str
    metric_id: str | None = None
    periods: list[Period] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    steps: list[PlannedStep] = Field(default_factory=list)


class PlanningOutputError(ValueError):
    """The model returned a plan that cannot safely be used."""


def interpret_and_plan(
    question: str,
    provider: ModelProvider,
    catalog: DataCatalog | None = None,
) -> PlanningResult:
    catalog = catalog or get_catalog()
    request = ModelRequest(
        system_instruction=_system_instruction(catalog),
        messages=[ModelMessage(role="user", content=question)],
        response_schema=Interpretation.model_json_schema(),
        temperature=0,
        max_output_tokens=2048,
    )
    response = provider.generate(request)
    if response.tool_calls or response.structured_output is None:
        raise PlanningOutputError("The model did not return a structured interpretation.")
    try:
        interpretation = Interpretation.model_validate(response.structured_output)
    except ValidationError as error:
        raise PlanningOutputError("The model returned an invalid interpretation.") from error
    return validate_interpretation(interpretation, catalog)


def validate_interpretation(
    interpretation: Interpretation, catalog: DataCatalog
) -> PlanningResult:
    if interpretation.decision != "ready":
        if interpretation.metric_id or interpretation.periods or interpretation.dimensions or interpretation.steps:
            raise PlanningOutputError("A non-ready interpretation cannot include an executable plan.")
        return PlanningResult(
            decision=interpretation.decision,
            message=interpretation.message,
        )

    metric = next(
        (item for item in catalog.metrics if item.id == interpretation.metric_id), None
    )
    if metric is None:
        raise PlanningOutputError("The plan selected a metric outside the catalog.")
    if not interpretation.periods:
        raise PlanningOutputError("A ready plan must specify at least one period.")
    if len(interpretation.periods) not in (1, 2):
        raise PlanningOutputError("Plans support one period or a two-period comparison.")
    supported_dimensions = set(metric.supported_dimensions)
    if len(set(interpretation.dimensions)) != len(interpretation.dimensions) or not set(
        interpretation.dimensions
    ).issubset(supported_dimensions):
        raise PlanningOutputError("The plan selected a dimension outside the metric catalog.")

    coverage_start = date.fromisoformat(catalog.coverage_start)
    coverage_end_exclusive = date.fromisoformat(catalog.coverage_end) + timedelta(days=1)
    for period in interpretation.periods:
        if period.start < coverage_start or period.end_exclusive > coverage_end_exclusive:
            return PlanningResult(
                decision="unsupported",
                message=(
                    f"The requested period {period.label} is outside available data "
                    f"({catalog.coverage_start} through {catalog.coverage_end})."
                ),
            )

    steps = interpretation.steps
    if not 1 <= len(steps) <= 6:
        raise PlanningOutputError("A ready plan must contain between one and six steps.")
    expected_ids = [f"step_{index}" for index in range(1, len(steps) + 1)]
    if [step.step_id for step in steps] != expected_ids:
        raise PlanningOutputError("Plan steps must have unique, sequential IDs.")
    return PlanningResult(
        decision="ready",
        message=interpretation.message,
        metric_id=metric.id,
        periods=interpretation.periods,
        dimensions=interpretation.dimensions,
        steps=steps,
    )


def _system_instruction(catalog: DataCatalog) -> str:
    catalog_json = catalog.model_dump_json(indent=2)
    return f"""You interpret revenue questions and draft a small analysis plan.
Use only the metric IDs, dimensions, date coverage, and schema in this catalog:
{catalog_json}

Return the required JSON object only. Do not write SQL or call tools.
Choose decision=needs_input when the metric or period is ambiguous; ask one concise
clarifying question in message. Never infer a missing year, comparison period, or
metric. Choose decision=unsupported when the requested metric, dimension, causal
claim, or dates are not supported; explain the limitation in message. For ready,
use one period for a single-period request and exactly two periods for a comparison.
Periods use ISO dates with end_exclusive. Include only supported dimensions.
Create 1 to 6 concise steps, ordered and named step_1 through step_N. Plans may
describe descriptive aggregations and comparisons only; this dataset cannot explain
causation. The inclusive coverage ends at {catalog.coverage_end}; all periods must
fall within that coverage."""
