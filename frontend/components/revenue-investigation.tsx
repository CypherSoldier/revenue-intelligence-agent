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
          ? 'This run is saved and queued. The investigation workflow will add steps in a later delivery.'
          : 'No plan steps have been recorded for this run.'}
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
        SQL activity will appear here when the investigation workflow is connected.
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
          <code>{query.sql}</code>
        </details>
      ))}
    </div>
  )
}

function EvidenceCard({ evidence }: { evidence: EvidenceReference }) {
  const entries = Object.entries(evidence.values)
  return (
    <article className="evidence-card">
      <div className="evidence-heading">
        <strong>{evidence.label}</strong>
        <span>{evidence.period}</span>
      </div>
      <p>{evidence.summary}</p>
      <div className="evidence-meta">Metric: {evidence.metric}</div>
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
          {run
            ? 'The run record is saved. Evidence and findings will appear when the investigation workflow is implemented.'
            : 'Submit a question to create a saved run. Evidence and findings will appear here when the investigation workflow is implemented.'}
        </p>
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
                  <span className="finding-evidence-count">
                    Supported by {finding.evidence_ids.length} evidence {finding.evidence_ids.length === 1 ? 'item' : 'items'}
                  </span>
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
      setQuestion(created.question)
      try {
        setRun(await getRun(created.id))
      } catch {
        setReloadMessage('The run was created, but its saved record could not be reloaded yet.')
      }
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
      setRun(await getRun(run.id))
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
          <button className="share-button" type="button" disabled title="Export will be added later">
            <FileText size={15} /> Export brief
          </button>
        </div>

        {health.phase === 'offline' && (
          <div className="api-health-error" role="alert">
            <AlertCircle size={16} /><span>{health.message}</span>
          </div>
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
