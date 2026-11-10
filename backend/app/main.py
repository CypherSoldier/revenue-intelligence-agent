from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(title="Revenue Investigation Agent", version="0.1.0")


@app.get("/health", tags=["health"])
def health() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "status": "ok",
        "model_provider": "gemini",
        "model": settings.gemini_model,
        "model_configured": settings.gemini_configured,
    }
