import axios from "axios"

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

const api = axios.create({ baseURL: BASE })

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ExperienceEntry {
  title?: string
  company?: string
  duration?: string
  location?: string
  description?: string
}

export interface EducationEntry {
  school?: string
  degree?: string
  field?: string
  dates?: string
}

export interface SourceUrls {
  github?: string
  linkedin?: string
}

export interface Profile {
  id: string
  name?: string
  headline?: string
  current_role?: string
  current_company?: string
  location?: string
  skills: string[]
  experience: ExperienceEntry[]
  education: EducationEntry[]
  github_username?: string
  github_bio?: string
  github_email?: string
  github_avatar_url?: string
  source_urls: SourceUrls
  top_languages?: { name: string; repo_count: number; bytes: number }[]
  total_contributions_90d?: number
  scraped_at?: string
}

export interface IngestResponse extends Profile {
  missing_links: string[]
  resume_parsed: boolean
}

export interface SearchResult {
  score: number
  profile: Profile
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  cached: boolean
}

export interface BulkIngestResponse {
  job_id: string
  status: string
  total: number
}

export interface BulkJobError {
  file: string
  error: string
}

export interface BulkJobStatus {
  job_id: string
  status: "pending" | "running" | "complete"
  total: number
  processed: number
  failed: number
  errors: BulkJobError[]
}

export interface ChatCitation {
  id: string
  name: string
  score: number
  source: "semantic" | "filter"
}

export interface ChatResponse {
  session_id: string
  answer: string
  citations: ChatCitation[]
}

export interface StreamChatCallbacks {
  onStage: (text: string) => void
  onToken: (text: string) => void
  onMeta: (sessionId: string, citations: ChatCitation[]) => void
  onDone: (fullText: string) => void
  onError: (e: Error) => void
}

// ── Endpoints ─────────────────────────────────────────────────────────────────

export const ingestSingle = (form: FormData) =>
  api.post<IngestResponse>("/ingest", form).then((r) => r.data)

export const ingestBulk = (form: FormData) =>
  api.post<BulkIngestResponse>("/ingest/bulk", form).then((r) => r.data)

export const pollBulkJob = (jobId: string) =>
  api.get<BulkJobStatus>(`/ingest/bulk/${jobId}`).then((r) => r.data)

export const searchProfiles = (
  q: string,
  skills?: string,
  location?: string,
  k = 10
) =>
  api
    .get<SearchResponse>("/search", { params: { q, skills, location, k } })
    .then((r) => r.data)

export const chatQuery = (question: string, session_id?: string) =>
  api.post<ChatResponse>("/chat", { question, session_id }).then((r) => r.data)

export const clearChat = (session_id: string) =>
  api.delete(`/chat/${session_id}`)

export function streamChat(
  question: string,
  sessionId: string | undefined,
  callbacks: StreamChatCallbacks,
): AbortController {
  const controller = new AbortController()

  ;(async () => {
    let fullText = ""
    try {
      const res = await fetch(`${BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, session_id: sessionId }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split("\n")
        buffer = lines.pop()!
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === "stage") callbacks.onStage(event.text)
            else if (event.type === "meta") callbacks.onMeta(event.session_id, event.citations)
            else if (event.type === "token") { fullText += event.text; callbacks.onToken(event.text) }
            else if (event.type === "done") callbacks.onDone(fullText)
            else if (event.type === "error") throw new Error(event.text)
          } catch { /* skip malformed lines */ }
        }
      }
    } catch (e: any) {
      if (e?.name !== "AbortError") callbacks.onError(e instanceof Error ? e : new Error(String(e)))
    }
  })()

  return controller
}
