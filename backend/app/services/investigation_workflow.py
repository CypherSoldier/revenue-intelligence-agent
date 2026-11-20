"""Background orchestration and persistence for one investigation run."""

from app.agent.execution import PlanExecutionError, execute_plan
from app.agent.planning import PlanningOutputError, PlanningResult, interpret_and_plan
from app.agent.reporting import ReportAssemblyError, assemble_report
from app.data.catalog import get_catalog
from app.providers.errors import ModelProviderError
from app.providers.factory import get_model_provider
from app.schemas.runs import (
    FailureDetails,
    PlanStepSummary,
    RunStatus,
    RunUpdate,
    StepStatus,
)
from app.services.run_service import get_run, update_run


def process_run(run_id) -> None:
    """Advance a saved run to completed, needs_input, or failed and persist it."""
    run = get_run(run_id)
    if run is None or run.status != RunStatus.QUEUED:
        return

    plan: PlanningResult | None = None
    steps: list[PlanStepSummary] = []
    queries = []
    evidence = []
    current_step: str | None = None
    try:
        update_run(run_id, RunUpdate(status=RunStatus.INTERPRETING))
        provider = get_model_provider()
        catalog = get_catalog()
        plan = interpret_and_plan(run.question, provider, catalog)
        if plan.decision != "ready":
            update_run(
                run_id,
                RunUpdate(
                    status=RunStatus.NEEDS_INPUT,
                    clarification=plan.message,
                    plan_summary="The question could not be safely planned.",
                ),
            )
            return

        metric = next(item for item in catalog.metrics if item.id == plan.metric_id)
        period_text = " vs ".join(
            f"{period.label} ({period.start} to {period.end_exclusive})"
            for period in plan.periods
        )
        steps = [
            PlanStepSummary(
                step_id=step.step_id,
                sequence=index,
                title=step.title,
                summary=step.summary,
                status=StepStatus.QUEUED,
            )
            for index, step in enumerate(plan.steps, start=1)
        ]
        plan_summary = (
            f"{metric.name} ({metric.unit}); {period_text}. "
            f"{plan.message}"
        )[:4000]
        update_run(
            run_id,
            RunUpdate(
                status=RunStatus.PLANNING,
                plan_summary=plan_summary,
                steps=steps,
            ),
        )
        current_step = steps[0].step_id
        update_run(
            run_id,
            RunUpdate(
                status=RunStatus.RUNNING,
                steps=[step.model_copy(update={"status": StepStatus.RUNNING}) for step in steps],
            ),
        )

        execution = execute_plan(run.question, plan, provider, catalog=catalog)
        queries, evidence = execution.queries, execution.evidence
        steps = [step.model_copy(update={"status": StepStatus.COMPLETED}) for step in steps]
        update_run(
            run_id,
            RunUpdate(
                status=RunStatus.VALIDATING,
                steps=steps,
                query_references=queries,
                evidence_references=evidence,
            ),
        )
        current_step = None
        report = assemble_report(run.question, plan, evidence, provider, catalog)
        update_run(
            run_id,
            RunUpdate(status=RunStatus.COMPLETED, report=report),
        )
    except PlanExecutionError as error:
        queries, evidence = error.queries, error.evidence
        current_step = error.step_id
        _persist_failure(
            run_id, error.code, str(error), current_step,
            steps, queries, evidence, retryable=error.retryable,
        )
    except ModelProviderError as error:
        _persist_failure(
            run_id, error.code, error.message, current_step,
            steps, queries, evidence, retryable=error.retryable,
        )
    except (PlanningOutputError, ReportAssemblyError) as error:
        _persist_failure(
            run_id, "invalid_model_output", str(error), current_step,
            steps, queries, evidence,
        )
    except Exception:
        _persist_failure(
            run_id,
            "investigation_failed",
            "The investigation stopped unexpectedly before a report was completed.",
            current_step,
            steps,
            queries,
            evidence,
        )


def _persist_failure(
    run_id,
    code: str,
    message: str,
    step_id: str | None,
    steps: list[PlanStepSummary],
    queries: list,
    evidence: list,
    *,
    retryable: bool = False,
) -> None:
    completed_step_ids = {
        query.step_id for query in queries if query.status.value == "completed"
    }
    updated_steps = []
    for step in steps:
        if step.step_id in completed_step_ids:
            status = StepStatus.COMPLETED
        elif step.step_id == step_id:
            status = StepStatus.FAILED
        else:
            status = StepStatus.QUEUED
        updated_steps.append(step.model_copy(update={"status": status}))

    update_run(
        run_id,
        RunUpdate(
            status=RunStatus.FAILED,
            steps=updated_steps,
            query_references=queries,
            evidence_references=evidence,
            report=None,
            clarification=None,
            failure=FailureDetails(
                code=code[:100],
                message=message[:2000] or "The investigation failed.",
                step_id=step_id,
                retryable=retryable,
            ),
        ),
    )
