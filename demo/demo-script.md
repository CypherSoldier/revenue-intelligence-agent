# Client demo script

## Before the demo

1. Follow the clean setup in the [repository README](../README.md), configure the backend Gemini key, and seed the dataset.
2. Start the backend and frontend in separate terminals.
3. Open `http://localhost:3000` and confirm the header says **API online · Gemini ready**.
4. Keep the [Day 1 fact sheet](../docs/mvp-day-1-decisions.md#deterministic-seed-facts) available to compare the demo results.

## Walkthrough (about five minutes)

1. Ask: **“How did total revenue change in Q2 2025 compared with Q1 2025?”**
2. Follow the run status through interpretation and the investigation path. Explain that the UI shows the bounded plan and the SQL used for the approved, read-only query.
3. Open the query reference. Explain that `?` placeholders are safely bound filter values. Point to the evidence cards for the returned period, metric, and values, then show the report's evidence links and caveat.
4. Expected result: Q1 **$1,200,000**, Q2 **$1,000,000**, change **−$200,000 (−16.7%)**. The report should say these descriptive data do not establish why revenue changed.
5. Ask: **“How did revenue change?”** Show the clarification state and that no query runs until the period is specified.
6. Select the completed run in **Recent investigations** or use **Reload saved run** to demonstrate persistence. Use **New investigation** when finished.

## Demo boundaries to state

- The figures are synthetic, cover January–June 2025, and are not a client's business data.
- The dataset supports descriptive revenue comparisons by region; it cannot establish causal drivers.
- The demo is local and single-user. It does not publish externally or modify analytics data.

## Reset after the demo

Stop the API, then rerun the seed command from the repository root to restore the 18 documented analytics rows. This does not delete saved runs. To clear saved run history as well, remove `backend/data/run-metadata.sqlite3` while the API is stopped.

## Back up and restore local demo data

Stop the API before copying SQLite files so the backup is consistent. From the repository root:

```powershell
$backupDir = "backend/data/demo-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
New-Item -ItemType Directory -Path $backupDir | Out-Null
Copy-Item backend/data/analytics.sqlite3 $backupDir/analytics.sqlite3
Copy-Item backend/data/run-metadata.sqlite3 $backupDir/run-metadata.sqlite3
```

To restore, stop the API and copy the files back from the chosen backup directory:

```powershell
$backupDir = 'backend/data/demo-backup-YYYYMMDD-HHMMSS'
Copy-Item $backupDir/analytics.sqlite3 backend/data/analytics.sqlite3 -Force
Copy-Item $backupDir/run-metadata.sqlite3 backend/data/run-metadata.sqlite3 -Force
```

The database files are ignored by Git. Keep backups on the demo machine or another approved local location; they contain saved question and report history.
