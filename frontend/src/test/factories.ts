// Small helpers that build realistic test data, so each test only states what matters to it.
import type {
  AgentAskResponse,
  Application,
  ApplicationDetail,
  AskResponse,
  InterviewPrep,
  KnowledgeDocument,
  MatchResult,
  PrepItem,
  SearchResult,
} from '../api/types'

export function makeApplication(overrides: Partial<Application> = {}): Application {
  return {
    id: 1,
    company: 'Acme',
    job_title: 'Backend Engineer',
    status: 'wishlist',
    job_url: null,
    location: null,
    applied_date: null,
    notes: null,
    created_at: '2026-10-01T10:00:00Z',
    updated_at: '2026-10-01T10:00:00Z',
    ...overrides,
  }
}

export function makeDetail(overrides: Partial<ApplicationDetail> = {}): ApplicationDetail {
  return {
    ...makeApplication(),
    status_history: [
      { id: 1, from_status: null, to_status: 'wishlist', note: null, changed_at: '2026-10-01T10:00:00Z' },
    ],
    match_snapshot: null,
    ...overrides,
  }
}

export function makeMatchResult(overrides: Partial<MatchResult> = {}): MatchResult {
  return {
    job: {
      job_title: 'Backend Engineer',
      company: 'Acme Cloud',
      location: 'Remote',
      seniority: 'Mid-level',
      employment_type: 'Full-time',
      required_skills: ['Python', 'SQL', 'REST APIs'],
      preferred_skills: ['Docker', 'AWS'],
      responsibilities: ['Build APIs'],
      min_years_experience: 3,
    },
    score: 47,
    required: {
      matched: [
        { skill: 'Python', found_in: 'skills_section' },
        { skill: 'SQL', found_in: 'experience_text' },
      ],
      missing: ['REST APIs'],
    },
    preferred: { matched: [], missing: ['Docker', 'AWS'] },
    suggestions: ['Learn Docker by containerizing a small project.'],
    ...overrides,
  }
}

// ---------- knowledge base, agent, interview ----------

export function makeDocument(overrides: Partial<KnowledgeDocument> = {}): KnowledgeDocument {
  return {
    id: 'doc1',
    title: 'Faster deployments',
    chunk_count: 2,
    char_count: 1234,
    created_at: '2026-10-01T10:00:00Z',
    ...overrides,
  }
}

export function makeSearchResult(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    rank: 1,
    score: 0.53,
    doc_id: 'doc1',
    title: 'Faster deployments',
    chunk_index: 0,
    text: 'I cut deploys from 40 to 12 minutes.',
    ...overrides,
  }
}

export function makeAskResponse(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    question: 'How did I speed up deployments?',
    answer: 'I cut deployment time from forty to twelve minutes [1].',
    grounded: true,
    sources_used: [1],
    sources: [makeSearchResult()],
    used_llm: true,
    ...overrides,
  }
}

export function makeAgentResponse(overrides: Partial<AgentAskResponse> = {}): AgentAskResponse {
  return {
    question: 'Which application is furthest along?',
    answer: 'Acme Corp is furthest along.',
    stopped_reason: 'final',
    steps: [
      {
        number: 1,
        thought: 'I need the list.',
        tool: 'list_applications',
        arguments: { status: 'applied' },
        observation: '{"count":1,"applications":[{"id":1,"company":"Acme Corp"}]}',
        ok: true,
      },
    ],
    ...overrides,
  }
}

export function makePrepItem(overrides: Partial<PrepItem> = {}): PrepItem {
  return {
    number: 1,
    question: 'Tell me about a time you reduced deployment time.',
    category: 'behavioral',
    why_asked: 'Shows impact on delivery.',
    skill: null,
    story_found: true,
    answer_outline: 'Deployments took forty minutes. I automated rollbacks [Faster deployments].',
    sources: ['Faster deployments'],
    note: null,
    ...overrides,
  }
}

export function makePrep(overrides: Partial<InterviewPrep> = {}): InterviewPrep {
  return {
    application_id: 7,
    company: 'Acme Cloud',
    job_title: 'Backend Engineer',
    generated_at: '2026-10-15T12:00:00Z',
    items: [
      makePrepItem(),
      makePrepItem({
        number: 2,
        question: 'How would you use Docker in production?',
        category: 'gap',
        why_asked: 'Probes a skill you are missing.',
        skill: 'Docker',
        story_found: false,
        answer_outline: null,
        sources: [],
        note: 'No note in your knowledge base matched this question. Consider writing one.',
      }),
    ],
    questions_to_ask: ['What does success look like in six months?'],
    coverage: { total: 2, with_story: 1, without_story: [2] },
    ...overrides,
  }
}
