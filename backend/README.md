# Backend

## Local setup

From the repository root, install the backend dependencies and create a local environment file:

```powershell
uv sync --project backend
Copy-Item backend\.env.example backend\.env
```

Set `GEMINI_API_KEY` in `backend\.env`. The default model is `gemini-3.6-flash`; override it with `GEMINI_MODEL` if needed. The API key is read only by the backend and is excluded from Git.

Start the API from the repository root:

```powershell
uv run --project backend uvicorn app.main:app --app-dir backend --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`. It reports whether a non-empty model key is configured but never returns the key.

Run backend tests:

```powershell
uv run --project backend --directory backend pytest
```

The current API is a foundation only; investigation and data endpoints are added in subsequent MVP steps.
