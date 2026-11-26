# Revenue Investigation Agent — Three-Week MVP Delivery Plan

This schedule turns the scope in [mvp-plan.md](./mvp-plan.md) into a 15-working-day build and release plan. It assumes one developer working full-time, with product decisions made promptly and access to the selected model provider. The repository currently has a backend starter/auth scaffold, but not the investigation workflow or frontend; treat this as a build from foundation rather than a near-finished MVP.

## What “shipped” means for this plan

By the end of Week 3, a new analyst should be able to follow the README, configure a model API key locally, seed the demo data, run the app, complete an investigation, inspect its evidence, and reload the run. The release is a versioned, client-demo-ready local application—not a public hosted service or production security boundary.

Keep the MVP promise and limits in [mvp-plan.md](./mvp-plan.md). Do not add authentication, Slack, multi-user access, a job queue, extra datasets, or production hosting during these three weeks. Keep the existing generic auth scaffold out of the user path unless a concrete dependency requires it.

## Week 1 — Establish a safe, runnable analysis path

**Goal:** A local app runs end-to-end through the API and seeded data, with SQL execution bounded and testable.

| Day | Work | End-of-day evidence |
|---|---|---|
| 1 | Lock the MVP contract: define the synthetic revenue dataset and metric semantics, choose representative golden questions with known answers (including ambiguous and unsupported cases), and confirm Gemini. Set up backend structure and configuration; frontend setup is owned by Codex. | Data contract, golden questions, Gemini configuration, and runnable FastAPI health skeleton in [mvp-day-1-decisions.md](./mvp-day-1-decisions.md); frontend skeleton handled separately by Codex. |
| 2 | Define Pydantic request/response models and the API health/run contract. Build the deterministic seed command, curated schema/metric catalog, and separate SQLite files or connections for analytics data and run metadata. | A repeatable seed produces known facts; API validates requests and returns clear configuration errors. |
| 3 | Implement the analytics repository and query policy: read-only SQLite connection, approved tables/views, single-statement SELECT-only policy, timeout, row cap, and explicit rejection errors. | Focused tests accept allowed queries and reject writes, multiple statements, disallowed objects, and over-limit results before execution. |
| 4 | Add run metadata persistence and the run service boundary. Store run status, plan/step summaries, query/evidence references, report, and failure details. Add the initial create/read endpoints. | API can create, persist, and reload a run without mixing metadata writes with analytics access. |
| 5 | Build the first frontend shell: question form, submit/loading state, validation and API-error states. Connect it to the run API; add local CORS/configuration and a basic health check. | A user can submit a question in the UI and see a real run record/status; the full stack starts from documented commands. |

**Week 1 gate:** Seeded data and metadata are isolated; SQL policy tests pass; app starts locally from the documented setup; one request persists and reloads. If this gate slips, reduce UI polish—not safety controls or evidence linkage.

## Week 2 — Complete the agent-to-report vertical slice

**Goal:** A real question can be planned, analyzed within fixed limits, and returned with evidence and honest failure behavior.

| Day | Work | End-of-day evidence |
|---|---|---|
| 6 | Implement the provider adapter and structured model/tool contracts. Load credentials only on the server; validate configuration at startup/request time and report missing credentials or provider failures clearly. | Provider is swappable behind a small adapter; no secret is sent to or embedded in the browser. |
| 7 | Implement bounded interpretation and plan generation using the metric/schema catalog. Add ambiguity/unsupported-question handling before query execution. | Ambiguous or out-of-scope questions stop with a useful clarification/limitation rather than guessed periods or metrics. |
| 8 | Connect tool calls to the SQL policy and result validator. Enforce plan-step, tool-call, retry, timeout, and result limits in application code. Tie each finding to a specific executed result. | Successful test question produces a bounded plan, executed SQL, validated result, and traceable evidence. |
| 9 | Add report assembly: answer, metric and comparison periods, concise plan and step statuses, SQL/results, evidence references, and caveats. Persist final and failed outcomes; ensure failure never looks like a successful report. | API returns and reloads complete success, clarification, and failure responses. |
| 10 | Integrate the complete UI flow: show plan and progress/status, report, SQL and result evidence, caveats, errors, and a way to start another investigation. Add run reload/history for the local demo. | A non-technical tester can complete and inspect an investigation without developer tools. |

**Week 2 gate:** At least one representative revenue comparison reaches an evidence-backed report through the actual model and query tool; ambiguity, provider failure, query rejection, and exhausted retries have visible non-success states. Freeze features after this gate.

## Week 3 — Verify, polish, and release

**Goal:** The MVP meets its acceptance criteria, can be reliably demonstrated, and is packaged for a client-facing demo.

| Day | Work | End-of-day evidence |
|---|---|---|
| 11 | Run the golden questions against seeded facts. Verify expected metrics, periods, values, evidence links, and caveats. Add/adjust focused API, workflow, and UI tests for gaps. | Automated checks cover happy path, ambiguity, known facts, unsafe SQL, time/row/budget limits, provider errors, and retry exhaustion. |
| 12 | Run adversarial and failure-path checks: malformed inputs, SQL policy bypass attempts, empty/large result sets, database errors, model timeouts/invalid tool arguments, and repeated submits. Fix only release-blocking defects. | No unsafe query executes; failures remain visible; no unsupported conclusion is presented as fact. |
| 13 | Polish the user-facing states and accessibility basics; make sure SQL/results and caveats are understandable. Update README with clean setup, seed/reset, run, test, configuration, troubleshooting, limitations, and demo script. | A fresh setup can be followed without tribal knowledge; no API key or local database is committed. |
| 14 | Perform a clean-state rehearsal on the intended demo machine/environment: install dependencies, configure a new local key, seed data, start app, run the golden demo, reload it, and verify errors with the key unset. Prepare the version/release notes and demo backup/reset steps. | Rehearsal checklist passes; known blockers are fixed or release is held. |
| 15 | Release gate: rerun targeted tests and the clean-start walkthrough, verify the release scope and limitations, tag/package the MVP, and hand over the runbook plus demo script. Reserve remaining time for only critical fixes and repeat the affected checks. | A versioned, reproducible demo is ready to show to users/clients, with its single-user/local-demo limits disclosed. |

**Week 3 gate:** Do not call it shipped unless a fresh setup completes the primary question-to-report flow and all MVP acceptance criteria below pass. If a release blocker remains on Day 15, ship a dated release candidate only with the blocker and remediation owner explicit; do not represent it as complete.

## Release checklist

- [ ] A new user can install/configure the app and seed the dataset by following the README.
- [ ] A revenue comparison completes question → bounded plan → approved read-only query → validated evidence → report.
- [ ] The UI exposes metric, periods, plan/step status, relevant SQL and result evidence, answer, and caveats.
- [ ] Ambiguous or unsupported input does not cause the agent to invent a period, metric, or conclusion.
- [ ] Unsafe, disallowed, or over-budget SQL is rejected before execution; timeouts and retry exhaustion are visible failures.
- [ ] Automated tests verify known seeded facts, evidence linkage, SQL policy, and failure behavior.
- [ ] Analytics data is read-only to the query tool; there is no analytics write path or external publishing.
- [ ] API keys stay server-side and out of source control; missing/invalid configuration produces a clear error.
- [ ] Clean-start walkthrough and demo script work on the intended machine; scope limits are disclosed.

## Scope and schedule controls

- Keep a working vertical slice at all times. Prefer the narrowest known-question set that proves the core loop over broad, unreliable question coverage.
- Reserve the final two days for release validation and critical fixes; do not consume them with new features.
- Defer authentication, Slack, hosted deployment, queues, broad metrics/connectors, and production operations as specified in the MVP plan.
- If client access requires a hosted URL, multi-user accounts, or handling real client data, that changes the MVP boundary and should be planned separately before implementation; this schedule does not claim production readiness.
