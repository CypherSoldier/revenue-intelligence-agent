from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RunStatus(StrEnum):
    QUEUED = "queued"
    INTERPRETING = "interpreting"
    PLANNING = "planning"
    RUNNING = "running"
    VALIDATING = "validating"
    COMPLETED = "completed"
    NEEDS_INPUT = "needs_input"
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


class RunResponse(BaseModel):
    id: UUID
    question: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None
    error_message: str | None = None
