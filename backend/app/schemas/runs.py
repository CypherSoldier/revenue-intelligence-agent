from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RunStatus(StrEnum):
    QUEUED = "queued"
    INTERPRETING = "interpreting"
    PLANNING = "planning"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    FAILED = "failed"


class StepStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
    FAILED = "failed"


class QueryReferenceStatus(StrEnum):
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class RunCreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: Annotated[str, Field(min_length=1, max_length=2000)]

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("Question must not be blank.")
        return value


class PlanStepSummary(BaseModel):
    step_id: Annotated[str, Field(min_length=1, max_length=100)]
    sequence: int = Field(ge=1)
    title: Annotated[str, Field(min_length=1, max_length=200)]
    summary: Annotated[str, Field(min_length=1, max_length=2000)]
    status: StepStatus = StepStatus.QUEUED


class QueryReference(BaseModel):
    id: UUID
    step_id: Annotated[str, Field(min_length=1, max_length=100)]
    query_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    sql: Annotated[str, Field(min_length=1, max_length=64_000)]
    status: QueryReferenceStatus
    row_count: int | None = Field(default=None, ge=0)
    executed_at: datetime | None = None


JsonScalar = str | int | float | bool | None


class EvidenceReference(BaseModel):
    id: UUID
    step_id: Annotated[str, Field(min_length=1, max_length=100)]
    query_id: UUID
    label: Annotated[str, Field(min_length=1, max_length=200)]
    metric: Annotated[str, Field(min_length=1, max_length=200)]
    period: Annotated[str, Field(min_length=1, max_length=100)]
    summary: Annotated[str, Field(min_length=1, max_length=2000)]
    values: dict[str, JsonScalar] = Field(default_factory=dict, max_length=100)


class ReportFinding(BaseModel):
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    evidence_ids: list[UUID] = Field(default_factory=list)


class RunReport(BaseModel):
    answer: Annotated[str, Field(min_length=1, max_length=12_000)]
    findings: list[ReportFinding] = Field(default_factory=list, max_length=50)
    caveats: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(
        default_factory=list, max_length=20
    )


class FailureDetails(BaseModel):
    code: Annotated[str, Field(min_length=1, max_length=100)]
    message: Annotated[str, Field(min_length=1, max_length=2000)]
    step_id: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    retryable: bool = False


class RunUpdate(BaseModel):
    status: RunStatus | None = None
    plan_summary: Annotated[str, Field(max_length=4000)] | None = None
    steps: list[PlanStepSummary] | None = Field(default=None, max_length=12)
    query_references: list[QueryReference] | None = Field(default=None, max_length=50)
    evidence_references: list[EvidenceReference] | None = Field(
        default=None, max_length=200
    )
    report: RunReport | None = None
    failure: FailureDetails | None = None

    @model_validator(mode="after")
    def validate_unique_step_ids_and_sequences(self) -> "RunUpdate":
        if self.steps is not None:
            step_ids = [step.step_id for step in self.steps]
            sequences = [step.sequence for step in self.steps]
            if len(set(step_ids)) != len(step_ids):
                raise ValueError("Plan step IDs must be unique.")
            if len(set(sequences)) != len(sequences):
                raise ValueError("Plan step sequence numbers must be unique.")
        return self


class RunResponse(BaseModel):
    id: UUID
    question: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    plan_summary: str | None = None
    steps: list[PlanStepSummary] = Field(default_factory=list, max_length=12)
    query_references: list[QueryReference] = Field(default_factory=list, max_length=50)
    evidence_references: list[EvidenceReference] = Field(
        default_factory=list, max_length=200
    )
    report: RunReport | None = None
    failure: FailureDetails | None = None
    error_code: str | None = None
    error_message: str | None = None
