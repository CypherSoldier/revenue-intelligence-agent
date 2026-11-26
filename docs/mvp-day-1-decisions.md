# MVP Day 1 — Decisions and Backend Foundation

These decisions complete the non-frontend Day 1 work in the [delivery plan](./mvp-3-week-delivery-plan.md). The frontend scaffold and run are owned by Codex.

## Locked MVP choices

- **Product boundary:** local, single-user, non-production demo against synthetic data. No authentication, external publishing, real client data, or production hosting.
- **Model provider:** Gemini Developer API, accessed only by the backend through Google's `google-genai` Python SDK.
- **Default model:** `gemini-3.6-flash`. Google's model documentation currently lists it as a stable model and supports function calling and structured outputs. Keep the model ID configurable with `GEMINI_MODEL`; verify the selected model and tool-call behavior in the Day 6 integration smoke test.
- **Credential:** `GEMINI_API_KEY` in the backend's local `.env`; never send it to the browser or commit it. The API may start without a key so local setup and health checks work; analysis must later fail explicitly if the key is absent.
- **Analytics scope:** one synthetic monthly revenue dataset covering January–June 2025, in USD, split by region. These are demo facts, not claims about a real business.

Model references: [Gemini models](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash) and [function calling](https://ai.google.dev/gemini-api/docs/function-calling).

## Analytics data contract

The Day 2 seed command should create one row per month and region in `monthly_sales`:

| Column | Type | Meaning |
|---|---|---|
| `month_start` | ISO date text | First day of the reporting month; reporting periods use calendar months and quarters. |
| `region` | text | One of `North`, `South`, or `West`. |
| `net_revenue_usd` | integer | Revenue in whole USD, after discounts, excluding tax, shipping, and refunds. |

Use `(month_start, region)` as the unique key. All values are non-negative. The table contains aggregate monthly values and no customer, product, or causal-driver detail. Revenue comparisons may establish changes and associations in these data only; they cannot establish why revenue changed.

### Deterministic seed facts

| Month (2025) | North | South | West | Total |
|---|---:|---:|---:|---:|
| January | 130,000 | 150,000 | 110,000 | 390,000 |
| February | 130,000 | 150,000 | 120,000 | 400,000 |
| March | 140,000 | 150,000 | 120,000 | 410,000 |
| April | 120,000 | 130,000 | 80,000 | 330,000 |
| May | 120,000 | 135,000 | 80,000 | 335,000 |
| June | 120,000 | 135,000 | 80,000 | 335,000 |

The golden answers derived from those rows:

- Q1 total: **$1,200,000**; Q2 total: **$1,000,000**; change: **−$200,000 (−16.7%)** versus Q1.
- Q1 by region: North **$400,000**, South **$450,000**, West **$350,000**.
- Q2 by region: North **$360,000**, South **$400,000**, West **$240,000**.
- Largest absolute regional decline: West, **−$110,000** (−31.4% versus Q1). This is a descriptive comparison, not a causal explanation.
- South Q1→Q2 change: **−$50,000 (−11.1%)**.
- May total: **$335,000**.

## Golden questions

| User question | Expected behavior/result |
|---|---|
| “How did total revenue change in Q2 2025 compared with Q1 2025?” | Return the Q1/Q2 totals and −$200,000 (−16.7%), with evidence for both periods. |
| “Which region had the biggest dollar decline from Q1 to Q2 2025?” | Identify West and show its $350,000 and $240,000 totals and −$110,000 change. Do not call this the cause of the overall drop. |
| “Compare Q2 2025 revenue by region.” | Return North $360,000, South $400,000, and West $240,000, linked to query results. |
| “What was total revenue in May 2025?” | Return $335,000. |
| “How did South revenue change in Q2 versus Q1 2025?” | Return $450,000 versus $400,000 and −$50,000 (−11.1%). |
| “How did revenue change?” | Ask which periods the user wants compared; do not infer a comparison period or query. |
| “Why did revenue drop?” | Explain that a period must be specified if absent and that the demo data can describe changes, but cannot establish causal drivers. |
| “How did 2024 revenue compare with 2025?” | Explain that 2024 is outside this dataset's coverage; do not invent or query unsupported data. |

## Backend foundation

The backend project is under `backend/`. Its current entry points are `app.main:app` and `/health`; settings load `GEMINI_API_KEY` and `GEMINI_MODEL` from the backend environment file without exposing credential values. A root `.gitignore` excludes local environment files, virtual environments, and SQLite files. Existing generic auth starter files are not wired into the MVP flow.

Run from the repository root:

```powershell
uv sync --project backend
Copy-Item backend\.env.example backend\.env
uv run --project backend uvicorn app.main:app --app-dir backend --reload
uv run --project backend --directory backend pytest
```

The health response reports provider, model, and whether a non-empty key is configured. The API starts without a key, but analysis must not silently fall back to a fabricated result.
