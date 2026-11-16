const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000'
).replace(/\/$/, '')

export type RunStatus =
  | 'queued'
  | 'interpreting'
  | 'planning'
  | 'running'
  | 'validating'
  | 'completed'
  | 'needs_input'
  | 'failed'

export interface ApiHealth {
  status: string
  model_provider: string
  model: string
  model_configured: boolean
}

export interface PlanStep {
  step_id: string
  sequence: number
  title: string
  summary: string
  status: 'queued' | 'running' | 'completed' | 'needs_input' | 'failed'
}

export interface QueryReference {
  id: string
  step_id: string
  query_hash: string
  sql: string
  status: 'completed' | 'rejected' | 'failed'
  row_count: number | null
  executed_at: string | null
}

export interface EvidenceReference {
  id: string
  step_id: string
  query_id: string
  label: string
  metric: string
  period: string
  summary: string
  values: Record<string, string | number | boolean | null>
}

export interface ReportFinding {
  text: string
  evidence_ids: string[]
}

export interface RunReport {
  answer: string
  findings: ReportFinding[]
  caveats: string[]
}

export interface RunFailure {
  code: string
  message: string
  step_id: string | null
  retryable: boolean
}

export interface InvestigationRun {
  id: string
  question: string
  status: RunStatus
  created_at: string
  updated_at: string
  plan_summary: string | null
  steps: PlanStep[]
  query_references: QueryReference[]
  evidence_references: EvidenceReference[]
  report: RunReport | null
  failure: RunFailure | null
  error_code: string | null
  error_message: string | null
}

export class RevenueApiError extends Error {
  readonly status: number | null
  readonly code: string | null

  constructor(message: string, status: number | null = null, code: string | null = null) {
    super(message)
    this.name = 'RevenueApiError'
    this.status = status
    this.code = code
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  const headers = new Headers(init?.headers)
  if (init?.body) headers.set('Content-Type', 'application/json')
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      cache: 'no-store',
      headers,
    })
  } catch {
    throw new RevenueApiError(
      `Cannot reach the API at ${API_BASE_URL}. Check that the backend is running and that its CORS settings allow this frontend.`
    )
  }

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail
    if (typeof detail === 'object' && detail !== null) {
      const error = detail as { code?: unknown; message?: unknown }
      throw new RevenueApiError(
        typeof error.message === 'string'
          ? error.message
          : `The API request failed with status ${response.status}.`,
        response.status,
        typeof error.code === 'string' ? error.code : null
      )
    }
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') {
      throw new RevenueApiError(detail[0].msg, response.status)
    }
    throw new RevenueApiError(
      typeof detail === 'string'
        ? detail
        : `The API request failed with status ${response.status}.`,
      response.status
    )
  }

  return payload as T
}

export function checkApiHealth(): Promise<ApiHealth> {
  return request<ApiHealth>('/health')
}

export function createRun(question: string): Promise<InvestigationRun> {
  return request<InvestigationRun>('/runs', {
    method: 'POST',
    body: JSON.stringify({ question }),
  })
}

export function getRun(runId: string): Promise<InvestigationRun> {
  return request<InvestigationRun>(`/runs/${encodeURIComponent(runId)}`)
}
