# Revenue Investigation Agent 0.1.0 — Release rehearsal

**Rehearsed:** 26 November 2026
**Target:** Windows local demo
**Release state:** Candidate ready for local demo; configure the demo machine's approved Gemini key before use.

## Rehearsal results

- Backend dependencies installed with `uv sync --project backend --locked`.
- Frontend dependencies installed with `pnpm --dir frontend install --frozen-lockfile`.
- Frontend local config created from `frontend/.env.example`.
- The existing backend-local Gemini key was used server-side; no key was printed, changed, or committed.
- The repeatable seed restored all 18 expected rows. Q1 total: **$1,200,000**; Q2 total: **$1,000,000**.
- API health and catalog responded. The Next.js page returned HTTP 200.
- The live golden comparison completed and returned **−$200,000 (−16.7%)**, with Q1/Q2 evidence and the caveat that descriptive data do not establish causes.
- The completed run was reloaded from `GET /runs/{id}` with its report and evidence intact.
- The Next.js page returned HTTP 200, but the computer-use helper could not initialize, so a human screen-level check of the UI's reload control is still required on the intended demo machine.
- With `GEMINI_API_KEY` overridden to empty for a separate API process, health reported the model as unconfigured and `POST /runs` returned `503 model_not_configured`. The real local `.env` was left intact.
- Backend suite: **48 tests passed** after rehearsal fixes.
- Release gate rerun: `uv sync --locked`, all **48 backend tests passed**, `pnpm install --frozen-lockfile`, Next.js **16.4.6**, and the production build succeeded.
- Clean-start API/UI servers returned healthy API status and HTTP 200 for the frontend. A new golden run completed, and a second `GET /runs/{id}` returned the saved completed report and evidence: Q1 **$1,200,000**, Q2 **$1,000,000**, change **−$200,000 (−16.67%)**.
- The UI source exposes the question, plan and step statuses, SQL and row counts, evidence metric/period/values, linked findings, caveats, failure messages, and saved-run reload. Windows browser automation stopped because it could not establish the current browser URL safely; no screen-level click-through was recorded in this pass.
- Missing-key behavior was verified on 25 November: health remains available and submitting a run returns `503 model_not_configured`. This release-gate pass did not alter or print the existing local key.

## Rehearsal fixes

- Send Pydantic structured-output schemas through Gemini's JSON Schema field and remove decoder size constraints from the generation copy; application-side Pydantic validation still enforces the original bounds.
- Use Gemini Developer API `v1beta`, which supports the configured developer instruction.
- Tell the query planner to return both labeled periods and bind both boundaries for comparison questions.

## Release gate notes

The guided Next.js security upgrade to `16.4.6` was installed and verified with a successful production build. A newly issued Gemini key was not provided; the golden run used the preconfigured local key. On the intended demo machine, configure its client-approved demo credential before presenting. The browser-level screen check should be included in that machine's first walkthrough.

## Version scope

Application package versions are `0.1.0` in the backend, frontend, and FastAPI app. The release is local and single-user: it uses synthetic data, has no authentication, and has no external publishing or analytics write path. See the [demo backup and reset steps](../demo/demo-script.md#back-up-and-restore-local-demo-data) before a client presentation.
