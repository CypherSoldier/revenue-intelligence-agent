# Backend

## Local setup

From the repository root, install the backend dependencies and create a local environment file:

```powershell
uv sync --project backend
Copy-Item backend\.env.example backend\.env
```

Set `GEMINI_API_KEY` in `backend\.env`. The default model is `gemini-3.6-flash`; override it with `GEMINI_MODEL` if needed. The API key is read only by the backend and is excluded from Git.

## Seed the analytics data

From the repository root, create or reset the deterministic January–June 2025 synthetic revenue dataset:

```powershell
uv run --project backend --directory backend python -m app.data.seed
```

This writes 18 rows to `backend/data/analytics.sqlite3`. The seed is repeatable and resets that demo analytics table to the documented facts. Run metadata is stored separately in `backend/data/run-metadata.sqlite3`. Both paths can be overridden with `ANALYTICS_DB_PATH` and `RUN_METADATA_DB_PATH`; relative paths are resolved from `backend/`.

The catalog contract is available at `GET /catalog`. It describes the single `monthly_sales` table and the net revenue definition.

Start the API from the repository root:

```powershell
uv run --project backend uvicorn app.main:app --app-dir backend --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`. It reports whether a non-empty model key is configured but never returns the key. `POST /runs` accepts `{ "question": "..." }` and returns a persisted queued run when the Gemini key is configured; `GET /runs/{id}` reloads it. The run endpoints validate nonblank questions up to 2,000 characters and return a structured `503 model_not_configured` error when the key is absent. The agent workflow is added in a later delivery step, so a queued record is not yet an executed investigation.

Run backend tests:

```powershell
uv run --project backend --directory backend pytest
```

The current API is a foundation only; investigation and data endpoints are added in subsequent MVP steps.
