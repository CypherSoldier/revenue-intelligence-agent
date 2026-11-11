from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.database.run_store import create_run, get_run
from app.schemas.runs import RunCreateRequest, RunResponse


router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunResponse, status_code=status.HTTP_202_ACCEPTED)
def submit_run(request: RunCreateRequest) -> RunResponse:
    if not get_settings().gemini_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "model_not_configured",
                "message": (
                    "Set GEMINI_API_KEY in backend/.env before submitting an "
                    "investigation. The API can still be used for health checks."
                ),
            },
        )
    return create_run(request.question)


@router.get("/{run_id}", response_model=RunResponse)
def read_run(run_id: UUID) -> RunResponse:
    run = get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": "No run exists with that ID."},
        )
    return run
