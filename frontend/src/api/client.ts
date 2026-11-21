/**
 * The ONLY file that talks to the backend.
 *
 * Components never call fetch() themselves. They call the small functions at the bottom
 * (listApplications, createApplication, ...), which gives us one place to handle URLs,
 * JSON, and errors.
 */

import type {
  AgentAskResponse,
  Application,
  ApplicationCreate,
  ApplicationDetail,
  ApplicationStatus,
  ApplicationUpdate,
  AskResponse,
  InterviewPrep,
  KnowledgeDocument,
  KnowledgeDocumentDetail,
  MatchResult,
  MatchSnapshot,
  MatchSnapshotCreate,
  ParsedResume,
  ResumeParseResponse,
  SearchResponse,
} from './types'

// In development, Vite forwards /api/... to the FastAPI backend (see vite.config.ts).
export const API_BASE = '/api'

/** An error that carries the HTTP status code (0 = the server could not be reached). */
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Turn an error response body into one readable sentence.
 *
 * The backend sends two shapes:
 *   our own errors:      { "detail": "Application 5 was not found." }
 *   FastAPI validation:  { "detail": [ { "loc": ["body", "company"], "msg": "Field required" } ] }
 */
export function describeError(status: number, body: unknown): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail

    if (typeof detail === 'string') return detail

    if (Array.isArray(detail)) {
      const problems = detail.map((item: { loc?: unknown; msg?: unknown }) => {
        const field = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== 'body').join('.')
          : ''
        const message = typeof item.msg === 'string' ? item.msg : 'Invalid value'
        return field ? `${field}: ${message}` : message
      })
      if (problems.length > 0) return problems.join('; ')
    }
  }
  return `Request failed (HTTP ${status}).`
}

/** Safe way to show any caught error to the user. */
export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong.'
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, init)
  } catch {
    // fetch() only throws when the request could not be made at all (server down, no network).
    throw new ApiError(0, 'Cannot reach the server. Is the backend running on port 8000?')
  }

  if (response.status === 204) return undefined as T // "No Content": nothing to parse

  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null // the body was empty or not JSON
  }

  if (!response.ok) throw new ApiError(response.status, describeError(response.status, body))
  return body as T
}

function jsonRequest(method: string, payload: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }
}

// ---------------------------------------------------------------- tracker

export interface ListParams {
  status?: ApplicationStatus
  search?: string
  limit?: number
  offset?: number
}

export function listApplications(params: ListParams = {}): Promise<Application[]> {
  const query = new URLSearchParams()
  if (params.status) query.set('status', params.status)
  if (params.search) query.set('search', params.search)
  if (params.limit !== undefined) query.set('limit', String(params.limit))
  if (params.offset !== undefined) query.set('offset', String(params.offset))
  const queryString = query.toString()
  return request<Application[]>(`/applications${queryString ? `?${queryString}` : ''}`)
}

export function getApplication(id: number): Promise<ApplicationDetail> {
  return request<ApplicationDetail>(`/applications/${id}`)
}

export function createApplication(body: ApplicationCreate): Promise<ApplicationDetail> {
  return request<ApplicationDetail>('/applications', jsonRequest('POST', body))
}

export function updateApplication(id: number, changes: ApplicationUpdate): Promise<ApplicationDetail> {
  return request<ApplicationDetail>(`/applications/${id}`, jsonRequest('PATCH', changes))
}

export function deleteApplication(id: number): Promise<void> {
  return request<void>(`/applications/${id}`, { method: 'DELETE' })
}

export function changeStatus(
  id: number,
  status: ApplicationStatus,
  note?: string,
): Promise<ApplicationDetail> {
  const body = note ? { status, note } : { status }
  return request<ApplicationDetail>(`/applications/${id}/status`, jsonRequest('POST', body))
}

export function attachMatch(id: number, snapshot: MatchSnapshotCreate): Promise<MatchSnapshot> {
  return request<MatchSnapshot>(`/applications/${id}/match`, jsonRequest('PUT', snapshot))
}

export function removeMatch(id: number): Promise<void> {
  return request<void>(`/applications/${id}/match`, { method: 'DELETE' })
}

// ---------------------------------------------------------------- resume + job matching

export function parseResume(file: File): Promise<ResumeParseResponse> {
  const form = new FormData()
  form.append('file', file)
  // No Content-Type header here: the browser must add it itself because it includes a
  // random "boundary" string that separates the parts of the upload.
  return request<ResumeParseResponse>('/resumes/parse', { method: 'POST', body: form })
}

export function matchJob(resume: ParsedResume, jobDescription: string): Promise<MatchResult> {
  return request<MatchResult>('/jobs/match', jsonRequest('POST', { resume, job_description: jobDescription }))
}

// ---------------------------------------------------------------- knowledge base (your notes)

export function listDocuments(): Promise<KnowledgeDocument[]> {
  return request<KnowledgeDocument[]>('/knowledge/documents')
}

export function addDocument(body: { title: string; text: string }): Promise<KnowledgeDocument> {
  return request<KnowledgeDocument>('/knowledge/documents', jsonRequest('POST', body))
}

export function getDocument(id: string): Promise<KnowledgeDocumentDetail> {
  return request<KnowledgeDocumentDetail>(`/knowledge/documents/${encodeURIComponent(id)}`)
}

export function deleteDocument(id: string): Promise<void> {
  return request<void>(`/knowledge/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

/** Retrieval only, no AI: shows which passages match and how well. */
export function searchKnowledge(query: string, k = 4): Promise<SearchResponse> {
  return request<SearchResponse>('/knowledge/search', jsonRequest('POST', { query, k }))
}

/** The full RAG flow: retrieve the best passages, then let the AI answer from them. */
export function askKnowledge(question: string, k = 4): Promise<AskResponse> {
  return request<AskResponse>('/knowledge/ask', jsonRequest('POST', { question, k }))
}

// ---------------------------------------------------------------- agent

export function askAgent(question: string): Promise<AgentAskResponse> {
  return request<AgentAskResponse>('/agent/ask', jsonRequest('POST', { question }))
}

// ---------------------------------------------------------------- interview preparation

export function getInterviewPrep(applicationId: number): Promise<InterviewPrep> {
  return request<InterviewPrep>(`/applications/${applicationId}/interview-prep`)
}

export function generateInterviewPrep(applicationId: number, questionCount?: number): Promise<InterviewPrep> {
  const query = questionCount === undefined ? '' : `?question_count=${questionCount}`
  return request<InterviewPrep>(`/applications/${applicationId}/interview-prep${query}`, { method: 'POST' })
}

export function deleteInterviewPrep(applicationId: number): Promise<void> {
  return request<void>(`/applications/${applicationId}/interview-prep`, { method: 'DELETE' })
}
