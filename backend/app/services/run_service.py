from datetime import UTC, datetime
from uuid import UUID

from app.database import run_store
from app.schemas.runs import RunResponse, RunStatus, RunUpdate, StepStatus


class RunNotFoundError(LookupError):
    pass


class InvalidRunTransitionError(ValueError):
    pass


_ALLOWED_TRANSITIONS = {
    RunStatus.QUEUED: {
        RunStatus.INTERPRETING,
        RunStatus.PLANNING,
        RunStatus.RUNNING,
        RunStatus.NEEDS_INPUT,
        RunStatus.FAILED,
    },
    RunStatus.INTERPRETING: {
        RunStatus.PLANNING,
        RunStatus.NEEDS_INPUT,
        RunStatus.FAILED,
    },
    RunStatus.PLANNING: {
        RunStatus.RUNNING,
        RunStatus.NEEDS_INPUT,
        RunStatus.FAILED,
    },
    RunStatus.RUNNING: {
        RunStatus.PLANNING,
        RunStatus.VALIDATING,
        RunStatus.NEEDS_INPUT,
        RunStatus.FAILED,
    },
    RunStatus.VALIDATING: {
        RunStatus.RUNNING,
        RunStatus.PLANNING,
        RunStatus.NEEDS_INPUT,
        RunStatus.COMPLETED,
        RunStatus.FAILED,
    },
    RunStatus.NEEDS_INPUT: {
        RunStatus.INTERPRETING,
        RunStatus.PLANNING,
        RunStatus.RUNNING,
        RunStatus.FAILED,
    },
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
}


def create_run(question: str) -> RunResponse:
    return run_store.create_run(question)


def get_run(run_id: UUID) -> RunResponse | None:
    return run_store.get_run(run_id)


def update_run(run_id: UUID, update: RunUpdate) -> RunResponse:
    current = run_store.get_run(run_id)
    if current is None:
        raise RunNotFoundError(f"No run exists with ID {run_id}.")

    payload = current.model_dump()
    payload.update(update.model_dump(exclude_unset=True))
    failure = payload.get("failure")
    status = payload.get("status")

    if status is None:
        raise InvalidRunTransitionError("Run status cannot be null.")
    if status != current.status and status not in _ALLOWED_TRANSITIONS[current.status]:
        raise InvalidRunTransitionError(
            f"A run cannot move from '{current.status.value}' to '{status.value}'."
        )

    if status == RunStatus.COMPLETED:
        if payload.get("report") is None:
            raise InvalidRunTransitionError("A completed run must include a report.")
        proposed_steps = payload.get("steps", [])
        if not proposed_steps or any(
            step.get("status") != StepStatus.COMPLETED for step in proposed_steps
        ):
            raise InvalidRunTransitionError(
                "A completed run must have all plan steps completed."
            )
    if status == RunStatus.FAILED and failure is None:
        raise InvalidRunTransitionError("A failed run must include failure details.")
    if status != RunStatus.FAILED and failure is not None:
        raise InvalidRunTransitionError(
            "Failure details can only be stored on a failed run."
        )

    candidate = RunResponse.model_validate(
        {
            **payload,
            "updated_at": datetime.now(UTC),
            "error_code": failure.get("code") if failure else None,
            "error_message": failure.get("message") if failure else None,
        }
    )
    _validate_references(candidate)

    saved = run_store.save_run(candidate)
    if saved is None:
        raise RunNotFoundError(f"No run exists with ID {run_id}.")
    return saved


def _validate_references(run: RunResponse) -> None:
    step_ids = {step.step_id for step in run.steps}
    query_by_id = {query.id: query for query in run.query_references}
    evidence_ids = {item.id for item in run.evidence_references}

    if len(query_by_id) != len(run.query_references):
        raise InvalidRunTransitionError("Query reference IDs must be unique.")
    if len(evidence_ids) != len(run.evidence_references):
        raise InvalidRunTransitionError("Evidence reference IDs must be unique.")

    for query in run.query_references:
        if query.step_id not in step_ids:
            raise InvalidRunTransitionError(
                f"Query reference {query.id} refers to unknown step '{query.step_id}'."
            )

    for evidence in run.evidence_references:
        query = query_by_id.get(evidence.query_id)
        if query is None:
            raise InvalidRunTransitionError(
                f"Evidence reference {evidence.id} refers to unknown query {evidence.query_id}."
            )
        if evidence.step_id not in step_ids or evidence.step_id != query.step_id:
            raise InvalidRunTransitionError(
                f"Evidence reference {evidence.id} must use the step of its query."
            )

    if run.report is not None:
        for finding in run.report.findings:
            missing_ids = set(finding.evidence_ids) - evidence_ids
            if missing_ids:
                missing_id = sorted(str(item) for item in missing_ids)[0]
                raise InvalidRunTransitionError(
                    f"Report finding refers to unknown evidence {missing_id}."
                )

    if run.failure and run.failure.step_id and run.failure.step_id not in step_ids:
        raise InvalidRunTransitionError(
            f"Failure details refer to unknown step '{run.failure.step_id}'."
        )
