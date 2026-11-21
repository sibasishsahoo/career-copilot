import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  addDocument,
  askAgent,
  askKnowledge,
  attachMatch,
  changeStatus,
  createApplication,
  deleteApplication,
  deleteDocument,
  deleteInterviewPrep,
  describeError,
  errorMessage,
  generateInterviewPrep,
  getApplication,
  getDocument,
  getInterviewPrep,
  listApplications,
  listDocuments,
  matchJob,
  parseResume,
  removeMatch,
  searchKnowledge,
  updateApplication,
} from './client'
import type { ParsedResume } from './types'

// A fake fetch: no network is ever used, and each test decides what the "server" answers.
const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

/** Run a request that is expected to fail and hand back the error. */
async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (error) {
    return error as ApiError
  }
  throw new Error('Expected the request to fail, but it succeeded')
}

function lastCall(): { url: string; init: RequestInit } {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1]
  return { url: url as string, init: init as RequestInit }
}

describe('describeError', () => {
  it('uses a plain string detail as is', () => {
    expect(describeError(404, { detail: 'Application 5 was not found.' })).toBe('Application 5 was not found.')
  })

  it('turns FastAPI validation errors into "field: message"', () => {
    const body = { detail: [{ loc: ['body', 'company'], msg: 'Field required', type: 'missing' }] }
    expect(describeError(422, body)).toBe('company: Field required')
  })

  it('joins several validation errors', () => {
    const body = {
      detail: [
        { loc: ['body', 'company'], msg: 'Field required' },
        { loc: ['body', 'resume', 'full_name'], msg: 'String should have at least 1 character' },
      ],
    }
    expect(describeError(422, body)).toBe(
      'company: Field required; resume.full_name: String should have at least 1 character',
    )
  })

  it('shows just the message when an error has no location', () => {
    expect(describeError(422, { detail: [{ msg: 'Something is off' }] })).toBe('Something is off')
  })

  it('falls back to the status code when the body has no usable detail', () => {
    expect(describeError(500, null)).toBe('Request failed (HTTP 500).')
    expect(describeError(500, {})).toBe('Request failed (HTTP 500).')
    expect(describeError(500, { detail: [] })).toBe('Request failed (HTTP 500).')
    expect(describeError(502, 'text')).toBe('Request failed (HTTP 502).')
  })
})

describe('errorMessage', () => {
  it('reads the message of an Error', () => {
    expect(errorMessage(new ApiError(404, 'Not found'))).toBe('Not found')
  })

  it('has a fallback for things that are not errors', () => {
    expect(errorMessage('oops')).toBe('Something went wrong.')
    expect(errorMessage(undefined)).toBe('Something went wrong.')
  })
})

describe('request handling', () => {
  it('returns the parsed JSON body on success', async () => {
    fetchMock.mockResolvedValueOnce(json([{ id: 1 }]))
    expect(await listApplications()).toEqual([{ id: 1 }])
  })

  it('throws an ApiError carrying the status and the backend message', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Application 5 was not found.' }, 404))
    const error = await failure(getApplication(5))
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(404)
    expect(error.message).toBe('Application 5 was not found.')
  })

  it('explains validation errors (HTTP 422)', async () => {
    const body = { detail: [{ loc: ['body', 'company'], msg: 'Field required' }] }
    fetchMock.mockResolvedValueOnce(json(body, 422))
    const error = await failure(createApplication({ company: '', job_title: 'x' }))
    expect(error.status).toBe(422)
    expect(error.message).toBe('company: Field required')
  })

  it('copes with an error response that is not JSON', async () => {
    fetchMock.mockResolvedValueOnce(new Response('<html>Bad gateway</html>', { status: 502 }))
    const error = await failure(listApplications())
    expect(error.status).toBe(502)
    expect(error.message).toBe('Request failed (HTTP 502).')
  })

  it('reports an unreachable server with status 0', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const error = await failure(listApplications())
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(0)
    expect(error.message).toContain('Cannot reach the server')
  })

  it('treats 204 No Content as success with no body', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    expect(await deleteApplication(3)).toBeUndefined()
  })
})

describe('tracker endpoints', () => {
  it('lists applications with no query string by default', async () => {
    fetchMock.mockResolvedValueOnce(json([]))
    await listApplications()
    expect(lastCall().url).toBe('/api/applications')
  })

  it('adds only the filters that were given to the query string', async () => {
    fetchMock.mockResolvedValueOnce(json([]))
    await listApplications({ status: 'applied', search: 'acme corp', limit: 200 })
    const { url } = lastCall()
    expect(url.startsWith('/api/applications?')).toBe(true)
    expect(url).toContain('status=applied')
    expect(url).toContain('search=acme+corp')
    expect(url).toContain('limit=200')
    expect(url).not.toContain('offset')
  })

  it('creates an application with a JSON POST', async () => {
    fetchMock.mockResolvedValueOnce(json({ id: 1 }, 201))
    await createApplication({ company: 'Acme', job_title: 'Dev', status: 'applied' })
    const { url, init } = lastCall()
    expect(url).toBe('/api/applications')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body as string)).toEqual({ company: 'Acme', job_title: 'Dev', status: 'applied' })
  })

  it('updates with PATCH and sends only the given fields', async () => {
    fetchMock.mockResolvedValueOnce(json({ id: 7 }))
    await updateApplication(7, { location: null })
    const { url, init } = lastCall()
    expect(url).toBe('/api/applications/7')
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body as string)).toEqual({ location: null })
  })

  it('deletes with DELETE', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await deleteApplication(3)
    const { url, init } = lastCall()
    expect(url).toBe('/api/applications/3')
    expect(init.method).toBe('DELETE')
  })

  it('changes status through its own endpoint, with an optional note', async () => {
    fetchMock.mockResolvedValue(json({ id: 2 }))
    await changeStatus(2, 'interviewing', 'Phone screen')
    expect(lastCall().url).toBe('/api/applications/2/status')
    expect(JSON.parse(lastCall().init.body as string)).toEqual({ status: 'interviewing', note: 'Phone screen' })

    await changeStatus(2, 'offer')
    expect(JSON.parse(lastCall().init.body as string)).toEqual({ status: 'offer' })
  })

  it('attaches a match with PUT and removes it with DELETE', async () => {
    const snapshot = { job_description: 'text', score: 72, matched_skills: [], missing_skills: [] }
    fetchMock.mockResolvedValueOnce(json({ id: 1 }))
    await attachMatch(4, snapshot)
    expect(lastCall().url).toBe('/api/applications/4/match')
    expect(lastCall().init.method).toBe('PUT')
    expect(JSON.parse(lastCall().init.body as string)).toEqual(snapshot)

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await removeMatch(4)
    expect(lastCall().url).toBe('/api/applications/4/match')
    expect(lastCall().init.method).toBe('DELETE')
  })
})

describe('resume and job endpoints', () => {
  it('uploads the resume as multipart form data and lets the browser set the headers', async () => {
    fetchMock.mockResolvedValueOnce(json({ filename: 'resume.pdf', parsed: {} }))
    const file = new File(['%PDF-1.4'], 'resume.pdf', { type: 'application/pdf' })
    await parseResume(file)

    const { url, init } = lastCall()
    expect(url).toBe('/api/resumes/parse')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBeInstanceOf(File)
    // No Content-Type header: the browser must add it, because it includes the multipart boundary.
    expect(init.headers).toBeUndefined()
  })

  it('sends the resume and the job text to the match endpoint', async () => {
    fetchMock.mockResolvedValueOnce(json({ score: 47 }))
    const resume: ParsedResume = {
      full_name: 'Jane Doe',
      email: null,
      phone: null,
      location: null,
      summary: null,
      skills: ['Python'],
      experience: [],
      education: [],
    }
    await matchJob(resume, 'A job description')

    const { url, init } = lastCall()
    expect(url).toBe('/api/jobs/match')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ resume, job_description: 'A job description' })
  })

  it('surfaces rate-limit and AI-failure messages from the backend', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Gemini rate limit reached.' }, 429))
    const error = await failure(matchJob({} as ParsedResume, 'text'))
    expect(error.status).toBe(429)
    expect(error.message).toBe('Gemini rate limit reached.')
  })
})

describe('knowledge base endpoints', () => {
  it('lists, adds, reads and deletes notes', async () => {
    fetchMock.mockResolvedValueOnce(json([{ id: 'a' }]))
    expect(await listDocuments()).toEqual([{ id: 'a' }])
    expect(lastCall().url).toBe('/api/knowledge/documents')

    fetchMock.mockResolvedValueOnce(json({ id: 'a' }, 201))
    await addDocument({ title: 'T', text: 'Body' })
    expect(lastCall().url).toBe('/api/knowledge/documents')
    expect(lastCall().init.method).toBe('POST')
    expect(JSON.parse(lastCall().init.body as string)).toEqual({ title: 'T', text: 'Body' })

    fetchMock.mockResolvedValueOnce(json({ id: 'a', chunks: [] }))
    await getDocument('a b')
    expect(lastCall().url).toBe('/api/knowledge/documents/a%20b') // the id is URL-encoded

    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await deleteDocument('a')
    expect(lastCall().url).toBe('/api/knowledge/documents/a')
    expect(lastCall().init.method).toBe('DELETE')
  })

  it('searches with a default of 4 passages, or a given number', async () => {
    fetchMock.mockResolvedValue(json({ query: 'q', results: [] }))
    await searchKnowledge('deployments')
    expect(lastCall().url).toBe('/api/knowledge/search')
    expect(JSON.parse(lastCall().init.body as string)).toEqual({ query: 'deployments', k: 4 })
    await searchKnowledge('deployments', 2)
    expect(JSON.parse(lastCall().init.body as string)).toEqual({ query: 'deployments', k: 2 })
  })

  it('asks a question of the notes', async () => {
    fetchMock.mockResolvedValueOnce(json({ answer: 'x' }))
    await askKnowledge('Which story shows leadership?')
    expect(lastCall().url).toBe('/api/knowledge/ask')
    expect(JSON.parse(lastCall().init.body as string)).toEqual({ question: 'Which story shows leadership?', k: 4 })
  })

  it('reports a knowledge base that is down with the backend message', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'The local embedding model failed.' }, 503))
    const error = await failure(listDocuments())
    expect(error.status).toBe(503)
    expect(error.message).toBe('The local embedding model failed.')
  })
})

describe('agent endpoint', () => {
  it('posts the question', async () => {
    fetchMock.mockResolvedValueOnce(json({ answer: 'x', steps: [] }))
    await askAgent('Which application is furthest along?')
    expect(lastCall().url).toBe('/api/agent/ask')
    expect(lastCall().init.method).toBe('POST')
    expect(JSON.parse(lastCall().init.body as string)).toEqual({ question: 'Which application is furthest along?' })
  })

  it('surfaces a rate limit', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Gemini rate limit reached.' }, 429))
    const error = await failure(askAgent('hi'))
    expect(error.status).toBe(429)
  })
})

describe('interview prep endpoints', () => {
  it('reads a saved pack', async () => {
    fetchMock.mockResolvedValueOnce(json({ application_id: 7 }))
    await getInterviewPrep(7)
    expect(lastCall().url).toBe('/api/applications/7/interview-prep')
  })

  it('treats "no pack yet" as a 404 ApiError', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Application 7 has no interview prep yet.' }, 404))
    const error = await failure(getInterviewPrep(7))
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(404)
  })

  it('generates with POST and passes the question count in the query string', async () => {
    fetchMock.mockResolvedValue(json({ application_id: 7 }))
    await generateInterviewPrep(7, 5)
    expect(lastCall().url).toBe('/api/applications/7/interview-prep?question_count=5')
    expect(lastCall().init.method).toBe('POST')
    expect(lastCall().init.body).toBeUndefined() // the count travels in the URL, there is no body

    await generateInterviewPrep(7)
    expect(lastCall().url).toBe('/api/applications/7/interview-prep')
  })

  it('reports an application without a saved match as a 409', async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: 'Application 7 has no saved job match.' }, 409))
    const error = await failure(generateInterviewPrep(7, 8))
    expect(error.status).toBe(409)
    expect(error.message).toContain('no saved job match')
  })

  it('deletes a pack', async () => {
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await deleteInterviewPrep(7)
    expect(lastCall().url).toBe('/api/applications/7/interview-prep')
    expect(lastCall().init.method).toBe('DELETE')
  })
})
