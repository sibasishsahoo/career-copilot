/**
 * TypeScript versions of the backend's Pydantic schemas.
 *
 * If you rename a field in the backend (backend/app/schemas/*.py), TypeScript will point at every
 * place in the frontend that still uses the old name - that is the main benefit of using it.
 * Field names stay in snake_case because that is exactly what the API sends.
 */

// ---------- tracker ----------

export const APPLICATION_STATUSES = [
  'wishlist',
  'applied',
  'interviewing',
  'offer',
  'rejected',
  'withdrawn',
] as const

// "wishlist" | "applied" | ... - derived from the array above so the two can never disagree.
export type ApplicationStatus = (typeof APPLICATION_STATUSES)[number]

export interface Application {
  id: number
  company: string
  job_title: string
  status: ApplicationStatus
  job_url: string | null
  location: string | null
  applied_date: string | null // "YYYY-MM-DD"
  notes: string | null
  created_at: string // ISO 8601, always UTC
  updated_at: string
}

export interface StatusChange {
  id: number
  from_status: ApplicationStatus | null // null = the creation entry
  to_status: ApplicationStatus
  note: string | null
  changed_at: string
}

export type SkillCategory = 'required' | 'preferred'

export interface SkillEntry {
  skill: string
  category: SkillCategory
}

export interface MatchSnapshot {
  id: number
  job_description: string
  score: number
  matched_skills: SkillEntry[]
  missing_skills: SkillEntry[]
  attached_at: string
}

export interface ApplicationDetail extends Application {
  status_history: StatusChange[]
  match_snapshot: MatchSnapshot | null
}

export interface ApplicationCreate {
  company: string
  job_title: string
  status?: ApplicationStatus
  job_url?: string | null
  location?: string | null
  applied_date?: string | null
  notes?: string | null
}

// PATCH body: any subset of the fields. (Status has its own endpoint, so it is not here.)
export type ApplicationUpdate = Partial<Omit<ApplicationCreate, 'status'>>

export interface MatchSnapshotCreate {
  job_description: string
  score: number
  matched_skills: SkillEntry[]
  missing_skills: SkillEntry[]
}

// ---------- resume ----------

export interface Experience {
  company: string
  title: string
  start_date: string | null
  end_date: string | null
  highlights: string[]
}

export interface Education {
  institution: string
  degree: string | null
  field_of_study: string | null
  graduation_year: number | null
}

export interface ParsedResume {
  full_name: string
  email: string | null
  phone: string | null
  location: string | null
  summary: string | null
  skills: string[]
  experience: Experience[]
  education: Education[]
}

export interface ResumeParseResponse {
  filename: string
  characters_extracted: number
  text_truncated: boolean
  text_preview: string
  parsed: ParsedResume
}

// ---------- job analysis and matching ----------

export interface JobAnalysis {
  job_title: string
  company: string | null
  location: string | null
  seniority: string | null
  employment_type: string | null
  required_skills: string[]
  preferred_skills: string[]
  responsibilities: string[]
  min_years_experience: number | null
}

export type SkillSource = 'skills_section' | 'experience_text'

export interface SkillMatch {
  skill: string
  found_in: SkillSource
}

export interface SkillGroupResult {
  matched: SkillMatch[]
  missing: string[]
}

export interface MatchResult {
  job: JobAnalysis
  score: number
  required: SkillGroupResult
  preferred: SkillGroupResult
  suggestions: string[]
}

// ---------- knowledge base (your own career notes) ----------

export interface KnowledgeDocument {
  id: string
  title: string
  chunk_count: number
  char_count: number
  created_at: string
}

export interface KnowledgeChunk {
  index: number
  text: string
}

export interface KnowledgeDocumentDetail extends KnowledgeDocument {
  chunks: KnowledgeChunk[]
}

export interface SearchResult {
  rank: number // 1 = best match; also the number the AI uses to cite it as [rank]
  score: number // cosine similarity: higher = better match
  doc_id: string
  title: string
  chunk_index: number
  text: string
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
}

export interface AskResponse {
  question: string
  answer: string
  grounded: boolean // true only if the answer cites at least one real source
  sources_used: number[]
  sources: SearchResult[]
  used_llm: boolean // false when no note was relevant, so the AI was never called
}

// ---------- agent ----------

export interface AgentStep {
  number: number
  thought: string | null // the model's own explanation; useful, but not guaranteed to be faithful
  tool: string
  arguments: Record<string, unknown>
  observation: string // exactly what the model was shown as the tool's result
  ok: boolean
}

export interface AgentAskResponse {
  question: string
  answer: string
  stopped_reason: 'final' | 'max_steps'
  steps: AgentStep[]
}

// ---------- interview preparation ----------

export interface PrepItem {
  number: number
  question: string
  category: string // behavioral | technical | role | gap
  why_asked: string
  skill: string | null
  story_found: boolean
  answer_outline: string | null
  sources: string[] // titles of the notes the outline is built from
  note: string | null // why there is no story, when story_found is false
}

export interface PrepCoverage {
  total: number
  with_story: number
  without_story: number[] // question numbers you still need a note for
}

export interface InterviewPrep {
  application_id: number
  company: string
  job_title: string
  generated_at: string
  items: PrepItem[]
  questions_to_ask: string[]
  coverage: PrepCoverage
}
