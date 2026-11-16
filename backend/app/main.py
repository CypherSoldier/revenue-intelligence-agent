from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.api.runs import router as runs_router
from app.data.catalog import get_catalog
from app.database.run_store import initialize_run_store
from app.schemas.catalog import DataCatalog
from app.providers.errors import ModelProviderError, ProviderConfigurationError
from app.providers.factory import close_model_providers, validate_provider_configuration


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    validate_provider_configuration(settings)
    initialize_run_store()
    try:
        yield
    finally:
        close_model_providers()

app = FastAPI(
    title="Revenue Investigation Agent",
    version="0.1.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router)


@app.exception_handler(ModelProviderError)
async def model_provider_error_handler(
    _request: Request, error: ModelProviderError
) -> JSONResponse:
    return JSONResponse(
        status_code=(
            503
            if error.retryable or isinstance(error, ProviderConfigurationError)
            else 502
        ),
        content={
            "detail": {
                "code": error.code,
                "message": error.message,
                "provider": error.provider,
                "retryable": error.retryable,
            }
        },
    )

@app.get("/health", tags=["health"])
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "model_provider": settings.llm_provider,
        "model": settings.gemini_model,
        "model_configured": settings.gemini_configured,
    }


@app.get("/catalog", tags=["analytics"], response_model=DataCatalog)
def catalog() -> DataCatalog:
    return get_catalog()
