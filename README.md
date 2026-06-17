# Candidate Intelligence System

A full-stack recruitment intelligence platform. Aggregates professional data from GitHub and LinkedIn, builds unified candidate profiles from resumes or scraped data, generates semantic vector embeddings, and exposes a search API and RAG chatbot that lets recruiters query the candidate database in plain English.

**Built for:** Salik Labs Remote Internship  
**Live API:** `https://candidateintelligenceengine-production.up.railway.app`  
**API Docs:** `https://candidateintelligenceengine-production.up.railway.app/docs`  
**Frontend:** `https://candidate-intelligence-engine.vercel.app`

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Database | MongoDB (local Docker) / MongoDB Atlas (production) |
| Vector DB | Pinecone (`all-MiniLM-L6-v2`, 384 dims, cosine) |
| Cache | Redis (local Docker) / Upstash Redis REST (production) |
| Scraping | Playwright (LinkedIn) + GitHub REST & GraphQL API |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| LLM | `google/gemma-4-31b-it:free` via OpenRouter (LangChain) |
| PDF parsing | `pypdf` |
| Drive download | `gdown >= 5.0` |
| Containerisation | Docker + Docker Compose |
| Deployment | Railway (API) + Vercel (frontend) |
| Frontend | React 19 + Vite + TypeScript + Tailwind CSS v4 |

---

## Project Structure

```
├── app/
│   ├── scrapers/
│   │   ├── github.py            # GitHub REST + GraphQL scraper
│   │   └── linkedin.py          # Playwright-based LinkedIn scraper
│   ├── utils/
│   │   ├── chat.py              # Query classification + LLM answer generation
│   │   ├── drive.py             # Google Drive folder download (gdown)
│   │   ├── llm.py               # Resume parsing via LLM
│   │   └── pdf.py               # PDF text + hyperlink extraction
│   ├── schemas.py               # All Pydantic models
│   ├── embeddings.py            # Sentence-transformer + Pinecone logic
│   └── main.py                  # FastAPI app and all endpoints
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/              # Reusable UI primitives
│   │   │   ├── search/          # SearchPanel, ChatPanel
│   │   │   ├── upload/          # SingleUpload, BulkImport
│   │   │   ├── Layout.tsx       # Sidebar and nav
│   │   │   └── ProfileModal.tsx # Full candidate profile dialog
│   │   ├── api.ts               # Typed axios + fetch client
│   │   ├── App.tsx              # Root component and view routing
│   │   └── index.css            # Tailwind v4 + CSS variables
│   ├── .env                     # VITE_API_URL (not committed)
│   └── package.json
├── scrape_and_store.py          # CLI: scrape → store → embed in one command
├── embed_all.py                 # Batch embed all MongoDB profiles to Pinecone
├── docker-compose.yml           # Local dev: API + MongoDB + Redis
├── Dockerfile                   # Production image
└── requirements.txt
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
# GitHub
GITHUB_TOKEN=ghp_...

# LinkedIn (extract li_at cookie after logging in manually)
LINKEDIN_LI_AT=AQE...
LINKEDIN_EMAIL=you@email.com
LINKEDIN_PASSWORD=yourpassword

# MongoDB
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/candidate_intelligence

# Pinecone
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX=candidate-intelligence

# Upstash Redis (production)
UPSTASH_REDIS_REST_URL=https://...upstash.io
UPSTASH_REDIS_REST_TOKEN=...

# OpenRouter (LLM for resume parsing + RAG chat)
OPENROUTER_API_KEY=sk-or-...
```

> `GITHUB_TOKEN`, `LINKEDIN_*` are only used by local scraper scripts — not needed on Railway.

---

## Setup — Local Development

Everything runs locally using Docker for the API, MongoDB, and Redis.

### Prerequisites
- Docker Desktop
- Python 3.11+
- Node.js 18+

### Steps

```powershell
# 1. Clone the repository
git clone https://github.com/<your-username>/candidate-intelligence-system.git
cd candidate-intelligence-system

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browser (one-time, for LinkedIn scraping)
playwright install chromium

# 5. Create .env from the template above

# 6. Start the API, MongoDB, and Redis containers
docker compose up --build -d

# 7. Start the frontend
cd frontend
npm install
npm run dev
```

- API: `http://localhost:8000` / Swagger UI: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

### Data routing when running locally

| Service | Where data goes | Why |
|---|---|---|
| MongoDB | **Local container** | `docker-compose.yml` overrides `MONGODB_URI` to the local container |
| Redis | **Upstash (cloud)** | Upstash credentials from `.env` are checked first in the Redis initialiser |
| Pinecone | **Cloud** | No local alternative — uses the same index as production |

If you want fully isolated local data, comment out `UPSTASH_REDIS_REST_URL` in `.env` (falls back to local Redis) and use a separate Pinecone index (e.g. `candidate-intelligence-dev`).

### Scrape and store a candidate

```powershell
# GitHub + LinkedIn
python scrape_and_store.py --github <username> --linkedin https://linkedin.com/in/<slug>

# GitHub only
python scrape_and_store.py --github torvalds

# LinkedIn only
python scrape_and_store.py --linkedin https://linkedin.com/in/williamhgates
```

### Batch embed all existing profiles

```powershell
python embed_all.py
```

---

## Setup — Production Testing (Cloud Services Locally)

```powershell
# 1. Activate venv
.venv\Scripts\activate

# 2. Ensure .env has Atlas MONGODB_URI, Upstash, and Pinecone credentials

# 3. Run the API directly (reads .env, bypasses docker-compose overrides)
uvicorn app.main:app --reload
```

All three services (MongoDB Atlas, Upstash, Pinecone) receive data directly.

---

## API Reference

Interactive docs at `/docs` (Swagger UI) and `/redoc`.

---

### `POST /profiles`
Insert or upsert a candidate profile. Replaced if the same GitHub username or LinkedIn URL already exists.

**Request body:**
```json
{
  "github_username": "torvalds",
  "github_profile": { "..." },
  "linkedin_url": "https://linkedin.com/in/...",
  "linkedin_profile": { "..." }
}
```
At least one of `github_username` or `linkedin_url` is required.

**Response:** `201 Created` — stored profile with MongoDB `id`.

---

### `GET /profiles/{id}`
Fetch a single profile by MongoDB ObjectId.

**Errors:** `400` malformed id · `404` not found.

---

### `POST /profiles/{id}/embed`
Generate and upsert a 384-dim vector to Pinecone for the given profile.

**Response:**
```json
{ "id": "...", "embedded": true }
```

---

### `GET /search`
Semantic search over all embedded profiles. Embeds the query with `all-MiniLM-L6-v2`, retrieves nearest vectors from Pinecone, fetches full documents from MongoDB, and applies optional hard filters. Results are Redis-cached for 5 minutes.

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | string | required | Plain-English search query |
| `skills` | string | — | Comma-separated skills (profile must have **all**) |
| `location` | string | — | Location substring filter (case-insensitive) |
| `k` | integer | 10 | Number of results (max 50) |

**Response:**
```json
{
  "query": "Python backend developer",
  "results": [{ "score": 0.87, "profile": { "..." } }],
  "cached": false
}
```

---

### `POST /scrape`
Trigger a live GitHub and/or LinkedIn scrape, store, and embed in one call.

**Request body:**
```json
{ "github_username": "torvalds", "linkedin_url": "https://linkedin.com/in/..." }
```

**Response:** `201 Created` — the scraped, stored, and embedded profile.

---

### `POST /ingest`
Accept a resume PDF (and optionally a LinkedIn URL and GitHub username). Extracts text from the PDF, parses structured fields via LLM, scrapes any provided social links, merges all sources, stores in MongoDB, and embeds in Pinecone.

**Form fields:**

| Field | Type | Notes |
|---|---|---|
| `resume` | file (PDF) | At least one of the three is required |
| `linkedin_url` | string | optional |
| `github_username` | string | optional |

**Response:** `201 Created` — merged profile + `missing_links` array for any URLs not found in the resume.

---

### `POST /ingest/bulk`
Accept multiple PDFs, ZIP archives, and/or a public Google Drive folder URL. Processing runs in the background; returns a job ID to poll.

**Form fields:**

| Field | Type | Description |
|---|---|---|
| `files` | file[] | PDF or ZIP files |
| `drive_url` | string | Public Google Drive folder URL |

**Response:** `202 Accepted`
```json
{ "job_id": "550e8400-...", "status": "pending", "total": 12 }
```

---

### `GET /ingest/bulk/{job_id}`
Poll the status of a bulk ingestion job.

**Response:**
```json
{
  "job_id": "...",
  "status": "running",
  "total": 12,
  "processed": 7,
  "failed": 1,
  "errors": [{ "file": "corrupted.pdf", "error": "not a valid PDF" }]
}
```

`status` is one of `pending` → `running` → `complete`.

---

### `POST /chat`
Non-streaming RAG chat. Classifies the query, fetches candidates (via vector search or MongoDB filter), then either generates an LLM answer (semantic/irrelevant queries) or returns a template response (filter queries). See `/chat/stream` for the real-time streaming variant.

**Request body:**
```json
{ "question": "Who are the strongest Python developers?", "session_id": null }
```

**Response:**
```json
{
  "session_id": "550e8400-...",
  "answer": "Based on the candidates in your database, **Abdullah Naeem** stands out...",
  "citations": [
    { "id": "...", "name": "Abdullah Naeem", "score": 0.91, "source": "semantic" }
  ]
}
```

`citations[].source` is `"semantic"` (vector search result) or `"filter"` (MongoDB exact match).

---

### `POST /chat/stream`
Streaming variant of `POST /chat`. Returns `text/event-stream` (SSE). The frontend uses this endpoint for real-time token-by-token output.

**Request body:** Same as `POST /chat`.

**Event sequence:**
```
data: {"type": "stage",  "text": "Classifying query…"}
data: {"type": "stage",  "text": "Searching database…"}
data: {"type": "meta",   "session_id": "…", "citations": […]}
data: {"type": "stage",  "text": "Generating answer…"}   ← omitted for filter queries
data: {"type": "token",  "text": "<chunk>"}              ← many; one per LLM token
data: {"type": "done"}
```

Filter queries skip the LLM entirely — after `meta`, a single `token` event carries the template response and `done` follows immediately.

On error: `{"type": "error", "text": "…"}`

---

### `DELETE /chat/{session_id}`
Clear all conversation history for a session from Redis. Returns `204 No Content`.

---

## Chat — Query Routing

Every chat message is first classified by a zero-temperature LLM call into one of three types:

| Type | When | Retrieval | LLM answer |
|---|---|---|---|
| `irrelevant` | Greetings, general knowledge, off-topic | None | Polite decline |
| `semantic` | Role / concept searches ("compare backend engineers") | Pinecone vector search · `top_k=10` targeted, `top_k=30` broad | Full LLM synthesis |
| `filter` | Concrete criteria ("list all from Islamabad", "how many know Python?") | MongoDB regex filter · up to 30 results | Template only — no LLM |

**Why filter queries skip the LLM:** MongoDB is the exact source of truth for concrete matches. Feeding the results back to the LLM to re-count or re-list them adds latency, burns rate-limit quota, and introduces a chance of mis-counting. The profile chips in the chat UI carry all the detail the recruiter needs.

---

## Schema Documentation

### CandidateProfile

| Field | Type | Source |
|---|---|---|
| `id` | `string` | MongoDB ObjectId |
| `scraped_at` | `string` (ISO 8601) | System |
| `source_urls.github` | `string \| null` | — |
| `source_urls.linkedin` | `string \| null` | — |
| `name` | `string \| null` | LinkedIn → GitHub |
| `headline` | `string \| null` | LinkedIn |
| `current_role` | `string \| null` | LinkedIn → GitHub |
| `current_company` | `string \| null` | LinkedIn → GitHub |
| `location` | `string \| null` | Resume → LinkedIn → GitHub |
| `experience` | `ExperienceEntry[]` | LinkedIn / Resume |
| `education` | `EducationEntry[]` | LinkedIn / Resume |
| `skills` | `string[]` | LinkedIn / Resume |
| `github_username` | `string \| null` | GitHub / Resume |
| `github_bio` | `string \| null` | GitHub |
| `github_email` | `string \| null` | GitHub |
| `github_avatar_url` | `string \| null` | GitHub |
| `public_repos` | `int` | GitHub |
| `followers` | `int` | GitHub |
| `top_languages` | `LanguageStats[]` | GitHub |
| `pinned_repos` | `GitHubRepo[]` | GitHub |
| `total_contributions_90d` | `int` | GitHub |
| `most_starred_repo` | `GitHubRepo \| null` | GitHub |
| `most_starred_repo_readme` | `string \| null` | GitHub |

---

## Frontend

A single-page React app in the `frontend/` directory with three views.

**Single Upload** — Upload one PDF resume with optional LinkedIn URL and GitHub username. Displays the merged profile on success.

**Bulk Import** — Upload multiple PDFs, ZIP archives, or paste a Google Drive folder link. Live progress bar polls the job status endpoint every 2 seconds.

**Search & Chat** — Two-panel layout:
- *Left:* Semantic search with skill and location filters, paginated results.
- *Right:* RAG chatbot with streaming responses, stage indicators (`Classifying query… → Searching database… → Generating answer…`), copy-to-clipboard per message, and clickable citation chips that open the full candidate profile in a modal. Filter query responses are instant (no LLM) and show a count with profile chips. Chat history is persisted in `localStorage`.

### Frontend Environment Variables

```env
VITE_API_URL=http://localhost:8000
```

For production, set `VITE_API_URL` to your Railway backend URL in the Vercel dashboard before deploying — Vite bakes it in at build time.

---

## Deployment

### Backend — Railway

1. Push this repository to GitHub.
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub.
3. Railway auto-detects the `Dockerfile`.
4. Add environment variables:

```
MONGODB_URI              = mongodb+srv://...
UPSTASH_REDIS_REST_URL   = https://...upstash.io
UPSTASH_REDIS_REST_TOKEN = ...
PINECONE_API_KEY         = pcsk_...
PINECONE_INDEX           = candidate-intelligence
OPENROUTER_API_KEY       = sk-or-...
```

The first build is slow (~5–10 min) because the `Dockerfile` pre-downloads the `all-MiniLM-L6-v2` model at build time.

### Frontend — Vercel

1. Import the repository on [vercel.com](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Add environment variable: `VITE_API_URL=https://your-app.up.railway.app`
4. Deploy.

After deploying, ensure the Vercel domain is in `allow_origins` in `app/main.py` and redeploy the backend.

---

## Deployment Notes

**LinkedIn scraper complexity:** LinkedIn's bot protection required running Chromium in headful mode. The DOM uses dynamically hashed class names and lazy-loads sections via `IntersectionObserver`, so `window.scrollTo` doesn't trigger rendering — `page.mouse.wheel` was needed instead. Skills required navigating to the dedicated `/details/skills/` sub-page. Raw extraction picked up navbar copy, ad strings, and skill proof entries ("Software Intern at X" appearing next to a skill), each requiring its own filter: a NOISE regex for UI boilerplate, an "at Company" pattern for proof entries, and keyword filters for education data bleeding in.

**Google Drive ingestion:** Uses `gdown >= 5.0`. The folder must be publicly shared. Files are downloaded to a temp directory, PDFs are extracted, and the temp directory is cleaned up automatically.
