# Revenue Investigation Agent

A local demo for asking questions about synthetic monthly revenue and reviewing the investigation plan, read-only SQL, result evidence, and caveats.

## Requirements

- Windows PowerShell (commands below use PowerShell syntax)
- Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/)
- Node.js and [`pnpm`](https://pnpm.io/)
- A Gemini Developer API key for investigations (health checks work without one)

## Clean setup

Run these commands from the repository root:

```powershell
uv sync --project backend
Copy-Item backend\.env.example backend\.env
```

Open `backend\.env` and set `GEMINI_API_KEY` to your key. The default model is configured by `GEMINI_MODEL`; `LLM_PROVIDER` defaults to `gemini`. Keep the key in this backend-only file. Do not paste it into the browser or commit it.

Create or reset the synthetic January–June 2025 data (18 monthly-by-region rows):

```powershell
uv run --project backend --directory backend python -m app.data.seed
```

Configure and install the frontend:

```powershell
Copy-Item frontend\.env.example frontend\.env.local
pnpm --dir frontend install
```

The default `NEXT_PUBLIC_API_BASE_URL` is `http://127.0.0.1:8000`. Change it in `frontend\.env.local` only if the API uses a different address.

## Run the app

Open two PowerShell terminals at the repository root.

Terminal 1, start the API:

```powershell
uv run --project backend uvicorn app.main:app --app-dir backend --reload
```

Terminal 2, start the frontend:

```powershell
pnpm --dir frontend dev
```

Open [http://localhost:3000](http://localhost:3000). Confirm the header reports **API online · Gemini ready**, then follow [the demo script](demo/demo-script.md). The API health and metric catalog are available at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) and [http://127.0.0.1:8000/catalog](http://127.0.0.1:8000/catalog).

## Verify changes

Run backend tests from the repository root:

```powershell
uv run --project backend --directory backend pytest
```

Build the frontend:

```powershell
pnpm --dir frontend build
```

## Configuration and local data

| Setting | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | unset | Server-side credential required to submit an investigation |
| `LLM_PROVIDER` | `gemini` | Provider adapter selection |
| `GEMINI_MODEL` | `gemini-3.6-flash` | Gemini model ID |
| `ANALYTICS_DB_PATH` | `backend/data/analytics.sqlite3` | Seeded synthetic revenue data |
| `RUN_METADATA_DB_PATH` | `backend/data/run-metadata.sqlite3` | Saved investigation runs |
| `QUERY_TIMEOUT_SECONDS` | `5` | Maximum database query time; allowed range is greater than 0 to 60 seconds |
| `QUERY_ROW_LIMIT` | `100` | Maximum result rows; allowed range is 1 to 1,000 |
| `NEXT_PUBLIC_API_BASE_URL` | `http://127.0.0.1:8000` | API address used by the browser |

The backend reads its settings from `backend/.env`; the frontend reads its public API address from `frontend/.env.local`. SQLite files are local and ignored by Git. Re-running the seed command replaces the `monthly_sales` contents with the documented demo facts; it does not clear saved runs. To clear run history, stop the API and remove `backend/data/run-metadata.sqlite3`.

## Troubleshooting

- **Gemini key missing:** the API can start and `/health` remains available, but submitting a run needs a non-empty `GEMINI_API_KEY` in `backend/.env`. Restart the API after changing the file.
- **API unavailable in the UI:** make sure the backend is running at the URL in `frontend/.env.local`. The API allows the default `http://localhost:3000` frontend origin.
- **No analytics database:** run the seed command from the repository root and check that `ANALYTICS_DB_PATH` points to the same file used by the API.
- **Port is already in use:** stop the process using port 8000 or 3000, or choose another port and update `NEXT_PUBLIC_API_BASE_URL` to match the API.
- **A run fails:** read the failure message shown in the report panel. Provider/network errors can be retried with a new investigation; rejected SQL and exhausted retries remain visible failures and do not produce a report.
- **Run history is missing:** the browser stores the latest ten run IDs in local storage; run records themselves are stored in the backend metadata database. Use the same browser and metadata file to reload them.

## Scope and limitations

- This is a local, single-user demo that uses synthetic data, not a production security boundary.
- The dataset covers January through June 2025, in whole USD, by North, South, and West region. Net revenue is after discounts and excludes tax, shipping, and refunds.
- Results support descriptive comparisons only. The data has no customer, product, or causal-driver detail and cannot explain why revenue changed.
- The query tool is read-only and restricted to the approved `monthly_sales` table, with a timeout, row cap, finite tool-call budget, and one correction retry per step.
- Run history is local. There is no authentication, external publishing, Slack integration, or real client data support.

See [the MVP plan](docs/mvp-plan.md), [the Day 1 data and question contract](docs/mvp-day-1-decisions.md), and [the delivery plan](docs/mvp-3-week-delivery-plan.md) for detailed acceptance criteria and known facts.
