# Frontend

This Next.js app is the local investigation workspace. It submits questions to the FastAPI backend and displays the plan, query references, validated evidence, report, caveats, and saved-run history.

See the [repository README](../README.md) for clean setup, seeding, troubleshooting, limitations, and the demo script.

## Run locally

From the repository root, start the backend first. Then configure and start the frontend:

```powershell
Copy-Item frontend\.env.example frontend\.env.local
pnpm --dir frontend install
pnpm --dir frontend dev
```

Open `http://localhost:3000`. Set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` if the backend is not at `http://127.0.0.1:8000`. The model key belongs only in `backend/.env`.

## Build

```powershell
pnpm --dir frontend build
```

Run history IDs are saved in this browser's local storage; run contents are reloaded from the backend metadata store.
