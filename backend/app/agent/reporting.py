"""Assemble a cited report from validated query evidence."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.contracts import ModelMessage, ModelRequest
from app.agent.planning import PlanningResult
from app.data.catalog import get_catalog
from app.providers.base import ModelProvider
from app.schemas.catalog import DataCatalog
from app.schemas.runs import EvidenceReference, ReportFinding, RunReport


class DraftFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=20)


class ReportDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1, max_length=12_000)
    findings: list[DraftFinding] = Field(default_factory=list, max_length=50)
    caveats: list[str] = Field(default_factory=list, max_length=19)


class ReportAssemblyError(ValueError):
    pass


def assemble_report(
    question: str,
    plan: PlanningResult,
    evidence: list[EvidenceReference],
    provider: ModelProvider,
    catalog: DataCatalog | None = None,
) -> RunReport:
    catalog = catalog or get_catalog()
    metric = next((item for item in catalog.metrics if item.id == plan.metric_id), None)
    if metric is None:
        raise ReportAssemblyError("The report metric is outside the catalog.")

    request = ModelRequest(
        system_instruction=_report_instruction(metric.name, metric.unit),
        messages=[ModelMessage(role="user", content=(
            f"Question: {question}\n"
            f"Metric: {metric.name} ({metric.id}), measured in {metric.unit}.\n"
            f"Periods: {[period.model_dump(mode='json') for period in plan.periods]}\n"
            f"Dimensions: {plan.dimensions}\n"
            f"Plan: {[step.model_dump() for step in plan.steps]}\n"
            f"Validated evidence records: {[item.model_dump(mode='json') for item in evidence]}"
        ))],
        response_schema=ReportDraft.model_json_schema(),
        temperature=0,
        max_output_tokens=4096,
    )
    response = provider.generate(request)
    if response.tool_calls or response.structured_output is None:
        raise ReportAssemblyError("The model did not return a structured report.")
    try:
        draft = ReportDraft.model_validate(response.structured_output)
    except ValidationError as error:
        raise ReportAssemblyError("The model returned an invalid report.") from error

    evidence_ids = {item.id for item in evidence}
    for finding in draft.findings:
        if not set(finding.evidence_ids).issubset(evidence_ids):
            raise ReportAssemblyError("A report finding cited evidence outside this run.")
    if not evidence and draft.findings:
        raise ReportAssemblyError("A finding cannot be produced without query evidence.")

    caveats = list(draft.caveats)
    if not any("caus" in caveat.casefold() for caveat in caveats):
        caveats.append("These descriptive results do not establish causal drivers.")
    return RunReport(
        answer=draft.answer,
        findings=[
            ReportFinding(text=item.text, evidence_ids=item.evidence_ids)
            for item in draft.findings
        ],
        caveats=caveats[:20],
    )


def _report_instruction(metric_name: str, unit: str) -> str:
    return f"""Write a concise, factual revenue investigation report in JSON.
Metric: {metric_name}, measured in {unit}. Use only the provided question, plan,
periods, and validated evidence records. State the metric and compared periods in
the answer. Do not infer causes, unsupported dimensions, or values absent from the
evidence. Every finding must cite one or more exact evidence_ids from the supplied
records; if evidence is empty, return no findings and clearly say that no rows were
returned. Include limitations as caveats. Do not write SQL or call tools."""
