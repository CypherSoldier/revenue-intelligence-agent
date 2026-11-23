'use client'

import {
  AlertCircle,
  Check,
  CircleAlert,
  Clock3,
  Database,
  FileText,
  MoreHorizontal,
  Play,
  Search,
  Sparkles,
} from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'

import {
  ApiHealth,
  EvidenceReference,
  checkApiHealth,
  createRun,
  getRun,
  InvestigationRun,
  PlanStep,
  RevenueApiError,
} from '@/lib/revenue-api'

type HealthState =
  | { phase: 'checking' }
  | { phase: 'online'; data: ApiHealth }
  | { phase: 'offline'; message: string }

const RUN_HISTORY_KEY = 'revenue-investigation-run-history-v1'
const TERMINAL_RUN_STATUSES: InvestigationRun['status'][] = [
  'completed',
  'needs_input',
  'failed',
]

function statusLabel(status: string) {
  return status.replaceAll('_', ' ')
}

function StatusIcon({ status }: { status: PlanStep['status'] }) {
  if (status === 'completed') {
    return <span className="status-icon complete"><Check size={13} strokeWidth={3} /></span>
  }
  if (status === 'failed' || status === 'needs_input') {
    return <span className="status-icon attention"><CircleAlert size={14} /></span>
  }
  if (status === 'running') {
    return <span className="status-icon running"><span className="status-spinner" /></span>
  }
  return <span className="status-icon pending"><Clock3 size={14} /></span>
}

function InvestigationSteps({ run }: { run: InvestigationRun | null }) {
  if (!run) {
    return <p className="empty-state compact">Submit a question to create an investigation run.</p>
  }
  if (run.steps.length === 0) {
    return (
      <p className="empty-state compact">
        {run.status === 'queued'
          ? 'This run is saved and waiting to start.'
          : run.status === 'needs_input'
            ? 'The question needs clarification before analysis can begin.'
            : run.status === 'failed'
              ? 'The run stopped before a complete plan was saved.'
              : 'The plan is being prepared.'}
      </p>
    )
  }

  return (
    <div className="steps-list">
      {run.steps
        .slice()
        .sort((a, b) => a.sequence - b.sequence)
        .map((step) => (
          <div className="step-row" key={step.step_id}>
            <div className="step-index">{String(step.sequence).padStart(2, '0')}</div>
            <StatusIcon status={step.status} />
            <div className="step-copy">
              <strong>{step.title}</strong>
              <span>{step.summary}</span>
            </div>
            <span className={`step-status status-${step.status.replace('_', '-')}`}>
              {statusLabel(step.status)}
            </span>
          </div>
        ))}
    </div>
  )
}

function QueryReferences({ run }: { run: InvestigationRun | null }) {
  if (!run || run.query_references.length === 0) {
    return (
      <p className="empty-state query-empty">
        SQL and result references will appear here when a query has run.
      </p>
    )
  }

  return (
    <div className="query-reference-list">
      {run.query_references.map((query) => (
        <details className="query-reference" key={query.id}>
          <summary>
            <span>{query.status.replace('_', ' ')} query</span>
            <span>{query.row_count === null ? 'Rows not recorded' : `${query.row_count} rows`}</span>
          </summary>
          <div className="query-reference-meta">
            Step {query.step_id} · {query.executed_at ? `Executed ${new Date(query.executed_at).toLocaleString()}` : 'Not executed'} · Ref {query.id.slice(0, 8)}
          </div>
          <code>{query.sql}</code>
        </details>
      ))}
    </div>
  )
}

function EvidenceCard({ evidence }: { evidence: EvidenceReference }) {
  const entries = Object.entries(evidence.values)
  return (
    <article className="evidence-card" id={`evidence-${evidence.id}`}>
      <div className="evidence-heading">
        <strong>{evidence.label}</strong>
        <span>{evidence.period}</span>
      </div>
      <p>{evidence.summary}</p>
      <div className="evidence-meta">Metric: {evidence.metric} · Query ref {evidence.query_id.slice(0, 8)}</div>
      {entries.length > 0 && (
        <dl className="evidence-values">
          {entries.map(([name, value]) => (
            <div key={name}>
              <dt>{name.replaceAll('_', ' ')}</dt>
              <dd>{value === null ? '—' : typeof value === 'number' ? value.toLocaleString('en-US') : String(value)}</dd>
            </div>
          ))}
        </dl>
      )}
    </article>
  )
}

function ReportPanel({ run }: { run: InvestigationRun | null }) {
  if (!run?.report) {
    return (
      <div className="panel findings-panel empty-report" aria-live="polite">
        <div className="empty-report-icon"><FileText size={18} /></div>
        <h3>{run ? `Run ${statusLabel(run.status)}` : 'No report yet'}</h3>
        <p>
          {!run
            ? 'Submit a question to create a saved investigation.'
            : run.status === 'needs_input'
              ? 'Please clarify the question, then start a new investigation.'
              : run.status === 'failed'
                ? 'This run did not produce a complete report.'
                : 'The investigation is running. Its report will appear here when ready.'}
        </p>
        {run?.clarification && (
          <div className="clarification-message" role="status">
            <CircleAlert size={15} /><span>{run.clarification}</span>
          </div>
        )}
        {run?.failure && (
          <div className="run-failure" role="alert">
            <AlertCircle size={15} />
            <span><strong>{run.failure.code}:</strong> {run.failure.message}</span>
          </div>
        )}
      </div>
    )
  }

  const evidenceById = new Map(run.evidence_references.map((item) => [item.id, item]))
  return (
    <div className="panel findings-panel">
      <div className="finding-head">
        <div>
          <span className="finding-kicker">Investigation report</span>
          <h3>Findings</h3>
          <p>{run.report.answer}</p>
        </div>
      </div>

      {run.report.findings.length > 0 && (
        <div className="report-findings">
          {run.report.findings.map((finding, index) => (
            <article className="report-finding" key={`${index}-${finding.text}`}>
              <span className="rank">{String(index + 1).padStart(2, '0')}</span>
              <div>
                <p>{finding.text}</p>
                {finding.evidence_ids.length > 0 && (
                  <div className="finding-evidence-links">
                    <span className="finding-evidence-count">
                      Supported by {finding.evidence_ids.length} evidence {finding.evidence_ids.length === 1 ? 'item' : 'items'}:
                    </span>
                    {finding.evidence_ids.map((id, evidenceIndex) => (
                      <a href={`#evidence-${id}`} key={id}>Evidence {evidenceIndex + 1}</a>
                    ))}
                  </div>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {run.evidence_references.length > 0 && (
        <div className="report-evidence">
          <div className="contributors-title">Supporting evidence</div>
          {run.evidence_references.map((evidence) => (
            <EvidenceCard evidence={evidence} key={evidence.id} />
          ))}
        </div>
      )}

      {run.report.caveats.length > 0 && (
        <div className="caveat">
          <CircleAlert size={15} />
          <span><strong>Interpretation notes:</strong> {run.report.caveats.join(' ')}</span>
        </div>
      )}

      {run.failure && (
        <div className="run-failure" role="alert">
          <AlertCircle size={15} />
          <span><strong>{run.failure.code}:</strong> {run.failure.message}</span>
        </div>
      )}

      {run.report.findings.some((finding) => finding.evidence_ids.some((id) => !evidenceById.has(id))) && (
        <div className="run-failure" role="status">
          <AlertCircle size={15} />
          <span>Some report evidence references are not available in this run record.</span>
        </div>
      )}
    </div>
  )
}

export function RevenueInvestigation() {
  const [question, setQuestion] = useState('')
  const [health, setHealth] = useState<HealthState>({ phase: 'checking' })
  const [run, setRun] = useState<InvestigationRun | null>(null)
  const [history, setHistory] = useState<InvestigationRun[]>([])
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isReloading, setIsReloading] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const [requestError, setRequestError] = useState<string | null>(null)
  const [reloadMessage, setReloadMessage] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    fetchHealth().then((result) => {
      if (active) setHealth(result)
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    const savedIds = readSavedRunIds()
    Promise.all(savedIds.map((id) => getRun(id).catch(() => null))).then((savedRuns) => {
      if (!active) return
      const availableRuns = savedRuns.filter((saved): saved is InvestigationRun => saved !== null)
      setHistory(availableRuns)
      setRun((current) => current ?? availableRuns[0] ?? null)
      if (availableRuns.length > 0) setQuestion((current) => current || availableRuns[0].question)
      setHistoryLoaded(savedRuns.every((saved) => saved !== null))
      if (savedRuns.some((saved) => saved === null)) {
        setReloadMessage('Some locally saved runs could not be reached. Their history IDs were kept in this browser.')
      }
    })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!historyLoaded) return
    try {
      window.localStorage.setItem(RUN_HISTORY_KEY, JSON.stringify(history.map((item) => item.id).slice(0, 10)))
    } catch {
      setReloadMessage('Run history could not be saved in this browser.')
    }
  }, [history, historyLoaded])

  useEffect(() => {
    if (!run || TERMINAL_RUN_STATUSES.includes(run.status)) return
    let active = true
    let refreshing = false
    const timer = window.setInterval(async () => {
      if (refreshing) return
      refreshing = true
      try {
        const latest = await getRun(run.id)
        if (active) {
          setRun((current) => current?.id === latest.id ? latest : current)
          setHistory((current) => mergeRunHistory(current, latest))
        }
      } catch (error) {
        if (active) {
          setReloadMessage(
            error instanceof RevenueApiError
              ? error.message
              : 'The run status could not be refreshed. Retrying…'
          )
        }
      } finally {
        refreshing = false
      }
    }, 1500)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [run?.id, run?.status])

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedQuestion = question.trim()
    setValidationError(null)
    setRequestError(null)
    setReloadMessage(null)

    if (!trimmedQuestion) {
      setValidationError('Enter a revenue question to continue.')
      return
    }
    if (trimmedQuestion.length > 2000) {
      setValidationError('Questions must be 2,000 characters or fewer.')
      return
    }

    setIsSubmitting(true)
    setRun(null)
    try {
      const created = await createRun(trimmedQuestion)
      setRun(created)
      setHistory((current) => mergeRunHistory(current, created))
    } catch (error) {
      setRequestError(
        error instanceof RevenueApiError
          ? error.message
          : 'The question could not be submitted. Please try again.'
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  async function reloadRun() {
    if (!run) return
    setIsReloading(true)
    setReloadMessage(null)
    try {
      const latest = await getRun(run.id)
      setRun(latest)
      setHistory((current) => mergeRunHistory(current, latest))
    } catch (error) {
      setReloadMessage(
        error instanceof RevenueApiError
          ? error.message
          : 'The saved run could not be reloaded. Please try again.'
      )
    } finally {
      setIsReloading(false)
    }
  }

  async function selectHistoryRun(runId: string) {
    setIsReloading(true)
    setReloadMessage(null)
    try {
      const selected = await getRun(runId)
      setRun(selected)
      setQuestion(selected.question)
      setHistory((current) => mergeRunHistory(current, selected))
      setValidationError(null)
      setRequestError(null)
    } catch (error) {
      setReloadMessage(
        error instanceof RevenueApiError
          ? error.message
          : 'That saved run could not be reloaded.'
      )
      setHistory((current) => current.filter((item) => item.id !== runId))
    } finally {
      setIsReloading(false)
    }
  }

  function startNewInvestigation() {
    setRun(null)
    setQuestion('')
    setValidationError(null)
    setRequestError(null)
    setReloadMessage(null)
  }

  const healthLabel = health.phase === 'checking'
    ? 'Checking API'
    : health.phase === 'offline'
      ? 'API unavailable'
      : health.data.model_configured
        ? 'API online · Gemini ready'
        : 'API online · Gemini key missing'

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><Sparkles size={14} /></span>
          <span>Revenue Intelligence</span>
          <span className="slash">/</span>
          <span className="muted">Investigation</span>
        </div>
        <div className="top-actions">
          <span className={`saved health-${health.phase}`} role="status" aria-live="polite">
            <span className="saved-dot" />{healthLabel}
          </span>
          <button className="icon-button" aria-label="More options" type="button"><MoreHorizontal size={18} /></button>
          <div className="avatar" aria-label="Analyst profile">AW</div>
        </div>
      </header>

      <div className="workspace">
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">{run ? `INVESTIGATION / ${run.id.slice(0, 8)}` : 'NEW INVESTIGATION'}</p>
            <h1>Revenue Investigation</h1>
            <p className="lede">Ask a question about the demo revenue data and review the run status.</p>
          </div>
          <div className="workspace-actions">
            {run && <button className="new-investigation-button" type="button" onClick={startNewInvestigation}>New investigation</button>}
            <button className="share-button" type="button" disabled title="Export will be added later">
              <FileText size={15} /> Export brief
            </button>
          </div>
        </div>

        {health.phase === 'offline' && (
          <div className="api-health-error" role="alert">
            <AlertCircle size={16} /><span>{health.message}</span>
          </div>
        )}

        {history.length > 0 && (
          <section className="history-section" aria-label="Recent saved investigations">
            <div className="history-heading">
              <div><strong>Recent investigations</strong><span>Saved in this browser</span></div>
              <span>{history.length} of 10</span>
            </div>
            <div className="history-list">
              {history.map((item) => (
                <button
                  className={`history-item${run?.id === item.id ? ' selected' : ''}`}
                  type="button"
                  key={item.id}
                  onClick={() => selectHistoryRun(item.id)}
                  disabled={isReloading}
                  aria-current={run?.id === item.id ? 'true' : undefined}
                >
                  <span className={`history-status history-status-${item.status.replace('_', '-')}`} />
                  <span className="history-copy"><strong>{item.question}</strong><small>{statusLabel(item.status)} · {new Date(item.updated_at).toLocaleString()}</small></span>
                  <span className="history-open">Open</span>
                </button>
              ))}
            </div>
          </section>
        )}

        <section className="question-section" aria-labelledby="question-title">
          <div className="section-label">
            <span className="label-number">01</span>
            <div><h2 id="question-title">Question</h2><p>What would you like to understand?</p></div>
          </div>

          <form onSubmit={onSubmit} noValidate>
            <div className="question-card">
              <div className="question-icon"><Search size={18} /></div>
              <label className="sr-only" htmlFor="revenue-question">Revenue question</label>
              <textarea
                id="revenue-question"
                className="question-input"
                value={question}
                onChange={(event) => {
                  setQuestion(event.target.value)
                  setValidationError(null)
                  setRequestError(null)
                }}
                placeholder="How did total revenue change in Q2 2025 compared with Q1 2025?"
                maxLength={2000}
                rows={2}
                aria-invalid={Boolean(validationError || requestError)}
                aria-describedby={validationError || requestError ? 'question-error' : 'question-help'}
              />
              <button className="submit-button" type="submit" disabled={isSubmitting}>
                {isSubmitting ? <span className="button-spinner" aria-hidden="true" /> : <Play size={14} fill="currentColor" />}
                {isSubmitting ? 'Submitting' : 'Investigate'}
              </button>
            </div>
            <div className="question-form-meta">
              <span id="question-help">Questions are limited to the synthetic January–June 2025 revenue dataset.</span>
              <span>{question.length}/2000</span>
            </div>
            {(validationError || requestError) && (
              <div className="request-error" id="question-error" role="alert">
                <AlertCircle size={15} /><span>{validationError ?? requestError}</span>
              </div>
            )}
          </form>

          <div className="question-meta">
            <span><Database size={13} /> Synthetic revenue dataset</span>
            <span className="meta-divider" />
            <span>Calendar quarters · USD · by region</span>
          </div>
        </section>

        {run && (
          <section className="run-summary" aria-label="Saved run status" aria-live="polite">
            <div className="run-summary-copy">
              <span className={`complete-pill run-status-${run.status.replace('_', '-')}`}>
                {run.status === 'completed' && <Check size={12} />}
                {run.status === 'failed' && <CircleAlert size={12} />}
                {statusLabel(run.status)}
              </span>
              <span className="run-summary-question">{run.question}</span>
              <span className="run-summary-id">Saved run · {run.id}</span>
            </div>
            <button className="reload-button" type="button" onClick={reloadRun} disabled={isReloading || isSubmitting}>
              {isReloading ? 'Reloading…' : 'Reload saved run'}
            </button>
          </section>
        )}
        {reloadMessage && <div className="reload-message" role="status">{reloadMessage}</div>}

        {isSubmitting && <p className="loading-message" role="status" aria-live="polite">Creating and loading the saved run…</p>}

        <div className="content-grid">
          <section className="investigation-section" aria-labelledby="investigation-title">
            <div className="section-label">
              <span className="label-number">02</span>
              <div><h2 id="investigation-title">Investigation path</h2><p>Steps and query activity for this run</p></div>
              {run && <span className={`complete-pill run-status-${run.status.replace('_', '-')}`}>{statusLabel(run.status)}</span>}
            </div>
            <div className="panel investigation-panel">
              {run?.plan_summary && <div className="run-plan"><strong>Plan</strong><span>{run.plan_summary}</span></div>}
              <div className="panel-top">
                <span className="panel-caption"><Play size={12} fill="currentColor" /> Investigation path</span>
                <span className="duration">{run ? `Updated ${new Date(run.updated_at).toLocaleTimeString()}` : 'Waiting for a question'}</span>
              </div>
              <InvestigationSteps run={run} />
              <div className="query-detail">
                <div className="query-top">
                  <span><Database size={13} /> Query references</span>
                  <span className="query-state">{run?.query_references.length ?? 0} recorded</span>
                </div>
                <QueryReferences run={run} />
              </div>
            </div>
          </section>

          <section className="findings-section" aria-labelledby="findings-title">
            <div className="section-label">
              <span className="label-number">03</span>
              <div><h2 id="findings-title">Findings</h2><p>Evidence-backed results for this run</p></div>
            </div>
            <ReportPanel run={run} />
          </section>
        </div>
      </div>
    </main>
  )
}

function readSavedRunIds(): string[] {
  try {
    const stored = window.localStorage.getItem(RUN_HISTORY_KEY)
    const parsed: unknown = stored ? JSON.parse(stored) : []
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is string => typeof item === 'string').slice(0, 10)
  } catch {
    return []
  }
}

function mergeRunHistory(current: InvestigationRun[], latest: InvestigationRun): InvestigationRun[] {
  return [latest, ...current.filter((item) => item.id !== latest.id)].slice(0, 10)
}

async function fetchHealth(): Promise<HealthState> {
  try {
    const data = await checkApiHealth()
    if (data.status !== 'ok') return { phase: 'offline', message: 'The API health check did not return an OK status.' }
    return { phase: 'online', data }
  } catch (error) {
    return {
      phase: 'offline',
      message: error instanceof RevenueApiError ? error.message : 'The API health check failed.',
    }
  }
}

export default RevenueInvestigation
