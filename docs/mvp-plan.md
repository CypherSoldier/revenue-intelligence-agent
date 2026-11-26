# Revenue Investigation Agent — MVP Plan

## Purpose

Build a small, credible demo that lets someone ask a revenue question and receive a concise answer supported by executed queries and visible evidence. The MVP should prove the core product loop—not imitate the entire production architecture in `design.md`.

The target experience is one analyst, one curated dataset, and one complete investigation from question to evidence-backed report. Keep the implementation replaceable and modular so successful parts can grow into the larger design.

## MVP promise

> Ask a question about the demo revenue data. Review what the agent investigated and the evidence behind its answer.

The demo will be explicit about its limits: it is not a general-purpose data analyst, does not establish causation, and does not send messages or change business data.

## First vertical slice

1. The user enters a question about revenue and submits it.
2. The agent interprets the comparison and creates a short, bounded plan.
3. The agent consults the demo metric definitions and approved schema.
4. It runs read-only queries against seeded sales data, validates the returned results, and may retry a failed step within a small fixed budget.
5. The UI displays the plan, step outcomes, relevant SQL, evidence, answer, and caveats.
6. If the input is ambiguous or the data cannot answer it, the agent says so rather than inventing a conclusion.

The user can start another investigation. Runs are stored locally so the current demo can be inspected and reloaded.

## Proposed minimum architecture

Use a small modular monolith:

| Part | MVP choice | Boundary to preserve |
|---|---|---|
| Web UI | React + TypeScript, single-page Vite app | Keep investigation and report views in separable features |
| API and orchestration | FastAPI with Pydantic models | Keep HTTP handlers separate from workflow and tool code |
| Agent | Gemini Developer API (`google-genai`) with structured tool calls | Keep provider-specific calls behind a small model adapter; Day 1 model and question decisions are in [mvp-day-1-decisions.md](./mvp-day-1-decisions.md) |
| Demo analytics data | Seeded SQLite database, opened read-only by the query tool | Put query execution behind a repository/tool interface that can later target PostgreSQL |
| Run metadata | Local SQLite tables for runs and step/evidence summaries | Keep metadata access separate from the analytics query connection |
| Runtime | One local API process; no queue or separate worker | Keep run execution callable as a service so it can later move to a worker |
| Delivery | Local development setup and seed command | Add containerized deployment when the demo workflow is stable |

No external Slack integration, hosted database, Redis, Celery, authentication system, or production deployment is required for this first slice. The model API key is supplied through local environment configuration, never committed or exposed to the browser. If model configuration is missing or a request fails, show a clear error; do not silently substitute a fabricated answer.

## Product and safety boundaries

- Support one curated revenue dataset and a small documented metric catalog.
- Keep a finite workflow plan, tool-call budget, query timeout, result-row limit, and retry limit.
- Only permit one read-only query per execution against explicitly approved tables/views.
- Enforce read-only access at the database connection as well as in query validation.
- Do not let the model choose database credentials, connection details, or arbitrary destinations.
- Do not execute generated SQL until it passes server-side policy checks.
- Show evidence and caveats alongside conclusions. Phrase observed contributors as associations, not proven causes.
- Do not expose hidden model reasoning; show the actionable plan, tool activity, SQL, results, and concise rationale.
- This is a local single-user demo, not a multi-user or production security boundary.

## Intentionally deferred

These remain candidates for later work if the MVP demonstrates value:

- PostgreSQL analytics and application stores with separate roles
- Background job queue, resumable runs, live progress events, and run-history management
- Authentication, authorization, and multi-user workspaces
- Slack preview and explicitly approved publishing
- Broader metrics, datasets, filters, and warehouse connectors
- Production deployment, observability, and operational controls
- Larger automated evaluation suite and quality/cost dashboards

Deferring a feature is not a claim that it is unnecessary in production. In particular, the demo's SQLite setup and single-user assumptions must not be carried into a production deployment unchanged.

## Build sequence after approval

1. **Foundation:** establish the frontend and FastAPI app, configuration validation, seeded demo dataset, and local run instructions.
2. **Safe analysis path:** add the metric/schema catalog, read-only SQL tool, policy limits, and focused tests for accepted and rejected queries.
3. **Agent workflow:** implement bounded interpretation, planning, tool execution, validation, retry/stop behavior, and evidence-backed report generation.
4. **Demo UI:** build the question form and a polished investigation/report view with clear loading, ambiguity, success, and failure states.
5. **Verification:** add representative golden questions and tests for SQL safety, evidence linkage, failure handling, and expected demo facts; verify the documented local setup from a clean state.

Keep each phase runnable and demonstrable. Avoid adding deferred infrastructure until a concrete MVP need justifies it.

## MVP acceptance criteria

- A new user can start the demo locally by following the README and can load the seeded dataset.
- A revenue-comparison question completes the full question → plan → bounded tool use → evidence-backed report flow.
- The UI shows the metric and periods used, the plan and step status, supporting result evidence, SQL, and relevant caveats.
- At least one ambiguous question prompts for clarification or reports the limitation instead of making up a period.
- Unsafe or over-budget SQL is rejected before execution; query errors and exhausted retries are visible failures, not successful-looking reports.
- Tests verify known answers against seeded facts and verify policy rejection and failure behavior.
- The MVP has no write path to the demo analytics data and performs no external publication.

## Decision requested

Approve this scope to begin implementation, or identify changes to the MVP promise, stack, data source, or deferred features first. No application implementation is included in this proposal.
