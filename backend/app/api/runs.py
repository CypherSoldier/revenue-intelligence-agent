from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.schemas.runs import RunCreateRequest, RunResponse
from app.providers.errors import ProviderConfigurationError
from app.providers.factory import validate_provider_configuration
from app.services.run_service import create_run, get_run
from app.services.investigation_workflow import process_run


router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_run(request: RunCreateRequest, background_tasks: BackgroundTasks) -> RunResponse:
    try:
        validate_provider_configuration(require_credentials=True)
    except ProviderConfigurationError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": error.code,
                "message": error.message,
            },
        ) from error
    run = create_run(request.question)
    background_tasks.add_task(process_run, run.id)
    return run


@router.get("/{run_id}", response_model=RunResponse)
def read_run(run_id: UUID) -> RunResponse:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": "No run exists with that ID."},
        )
    return run
