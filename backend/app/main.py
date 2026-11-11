from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api.runs import router as runs_router
from app.data.catalog import get_catalog
from app.database.run_store import initialize_run_store
from app.schemas.catalog import DataCatalog


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_run_store()
    yield

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

@app.get("/health", tags=["health"])
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "model_provider": "gemini",
        "model": settings.gemini_model,
        "model_configured": settings.gemini_configured,
    }


@app.get("/catalog", tags=["analytics"], response_model=DataCatalog)
def catalog() -> DataCatalog:
    return get_catalog()
