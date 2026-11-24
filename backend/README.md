# Backend

The FastAPI backend validates and runs bounded investigations against the synthetic SQLite analytics dataset. For the complete clean setup and two-terminal walkthrough, see the [repository README](../README.md).

## Setup and run

From the repository root:

```powershell
uv sync --project backend
Copy-Item backend\.env.example backend\.env
```

Set `GEMINI_API_KEY` in `backend\.env`, seed the demo data, and start the API:

```powershell
uv run --project backend --directory backend python -m app.data.seed
uv run --project backend uvicorn app.main:app --app-dir backend --reload
```

The API listens at `http://127.0.0.1:8000`. `GET /health` reports provider readiness without revealing credentials; `GET /catalog` describes the approved metric and table; `POST /runs` starts an investigation; `GET /runs/{id}` reloads it.

## Settings

Settings are read from `backend/.env`. See [`.env.example`](.env.example) for all available options. The analytics and metadata databases are separate. Relative database paths are resolved from `backend/`. The query timeout defaults to 5 seconds (greater than 0 through 60); the result cap defaults to 100 rows (1 through 1,000).

The seed command is repeatable and replaces the `monthly_sales` table with 18 documented synthetic rows. It does not clear saved run metadata. Never commit `.env` files or SQLite databases.

## Safety and failure behavior

The analytics query path accepts a single approved `SELECT`, uses bound filter parameters, opens SQLite in read-only mode, and independently enforces read-only behavior with SQLite settings and an authorizer. Time, row, result-shape, plan-step, tool-call, and retry limits are enforced in application code. Provider errors, invalid tool calls, rejected SQL, missing data, and exhausted retries remain explicit failed or clarification states; they must not be presented as successful reports.

## Tests

From the repository root:

```powershell
uv run --project backend --directory backend pytest
```
