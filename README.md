# Candidate Intelligence System

A backend system that aggregates professional data from GitHub and LinkedIn, builds unified candidate profiles, generates semantic vector embeddings, and exposes a search API that ranks candidates by relevance to a plain-English query.

**Built for:** Salik Labs Remote Internship - Week 1 Project  
**Live API:** `https://candidateintelligenceengine-production.up.railway.app`  
**API Docs:** `https://candidateintelligenceengine-production.up.railway.app/docs`

---

## Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Database | MongoDB (local) / MongoDB Atlas (production) |
| Vector DB | Pinecone (`all-MiniLM-L6-v2`, 384 dims, cosine) |
| Cache | Redis (local) / Upstash Redis REST (production) |
| Scraping | Playwright (LinkedIn) + GitHub REST & GraphQL API |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Containerisation | Docker + Docker Compose |
| Deployment | Railway |

---

## Project Structure

```
├── app/
│   ├── scrapers/
│   │   ├── github.py        # GitHub REST + GraphQL scraper
│   │   └── linkedin.py      # Playwright-based LinkedIn scraper
│   ├── schemas.py           # All Pydantic models
│   ├── embeddings.py        # Sentence-transformer + Pinecone logic
│   └── main.py              # FastAPI app and all endpoints
├── scrape_and_store.py      # CLI: scrape → store → embed in one command
├── embed_all.py             # Batch embed all MongoDB profiles to Pinecone
├── docker-compose.yml       # Local dev: API + MongoDB + Redis
├── Dockerfile               # Production image
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

# MongoDB (only needed if running scripts outside Docker against Atlas)
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/candidate_intelligence

# Pinecone
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX=candidate-intelligence

# Upstash Redis (production)
UPSTASH_REDIS_REST_URL=https://...upstash.io
UPSTASH_REDIS_REST_TOKEN=...
```

> `GITHUB_TOKEN` and `LINKEDIN_LI_AT` are only used by the local scraper scripts. They are not needed on Railway.

---

## Setup — Cold Clone (Local Development)

Everything runs locally using Docker for the API, MongoDB, and Redis.

### Prerequisites
- Docker Desktop
- Python 3.11+
- Git

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

# 4. Install Playwright browser (one-time)
playwright install chromium

# 5. Copy and fill in your environment variables
# Create .env from the template above

# 6. Start the API, MongoDB, and Redis containers
docker compose up -d

# 7. Confirm the API is running
# Open http://localhost:8000/docs
```

### Scrape and store a candidate profile

```powershell
# Scrape GitHub + LinkedIn, store in MongoDB, embed in Pinecone — all in one command
python scrape_and_store.py --github <github-username> --linkedin https://linkedin.com/in/<slug>

# GitHub only
python scrape_and_store.py --github torvalds

# LinkedIn only
python scrape_and_store.py --linkedin https://linkedin.com/in/williamhgates
```

### Embed all existing profiles (batch)

```powershell
python embed_all.py
```

---

## Setup — Production Testing (Cloud Services Locally)

Use this when you want to test against real Atlas, Upstash, and Pinecone without deploying to Railway.

```powershell
# 1. Activate venv
.venv\Scripts\activate

# 2. Ensure .env has your Atlas MONGODB_URI, Upstash, and Pinecone credentials

# 3. Run the API directly (reads .env, bypasses docker-compose overrides)
uvicorn app.main:app --reload

# 4. In a second terminal — scrape and store
python scrape_and_store.py --github <username> --linkedin <url>
```

Verify each service received data:

| Service | Where to check |
|---|---|
| MongoDB | Atlas dashboard → Collections → `candidate_intelligence.profiles` |
| Pinecone | Pinecone dashboard → your index → vector count |
| Redis | Run the same search query twice — second response returns `"cached": true` |

---

## API Reference

Interactive docs available at `/docs` (Swagger UI) and `/redoc`.

### `POST /profiles`
Insert or upsert a candidate profile. If a profile for the same GitHub username or LinkedIn URL already exists it is replaced with fresh data.

**Request body:**
```json
{
  "github_username": "torvalds",
  "github_profile": { ... },
  "linkedin_url": "https://linkedin.com/in/...",
  "linkedin_profile": { ... }
}
```

At least one of `github_username` or `linkedin_url` is required.

**Response:** `201 Created` — the stored profile with its MongoDB `id`.

---

### `GET /profiles/{id}`
Fetch a single profile by its MongoDB ObjectId string.

**Response:** `200 OK` — full candidate profile document.  
**Errors:** `400` malformed id, `404` not found.

---

### `POST /profiles/{id}/embed`
Generate a 384-dim vector embedding for the profile and upsert it to Pinecone. Called automatically by `scrape_and_store.py` after storing.

**Response:** `200 OK`
```json
{ "id": "...", "embedded": true }
```

---

### `GET /search`
Semantic search over all embedded profiles. Embeds the query, queries Pinecone for nearest vectors, fetches full documents from MongoDB, and returns results ranked by similarity score. Repeated queries are served from Redis cache (5-minute TTL).

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `q` | string | required | Plain-English search query |
| `skills` | string | — | Comma-separated required skills (profile must have all) |
| `location` | string | — | Location substring filter (case-insensitive) |
| `k` | integer | 10 | Number of results (max 50) |

**Response:** `200 OK`
```json
{
  "query": "Python backend developer",
  "results": [
    {
      "score": 0.87,
      "profile": { ... }
    }
  ],
  "cached": false
}
```

---

## Schema Documentation

### CandidateProfile (unified document stored in MongoDB)

| Field | Type | Source | Description |
|---|---|---|---|
| `id` | `string` | MongoDB | 24-character hex ObjectId |
| `scraped_at` | `string` (ISO 8601) | System | Timestamp of last scrape |
| `source_urls.github` | `string \| null` | — | GitHub profile URL |
| `source_urls.linkedin` | `string \| null` | — | LinkedIn profile URL |
| `name` | `string \| null` | LinkedIn → GitHub | Display name |
| `headline` | `string \| null` | LinkedIn | Profile headline |
| `current_role` | `string \| null` | LinkedIn → GitHub | Current job title |
| `current_company` | `string \| null` | LinkedIn → GitHub | Current employer |
| `location` | `string \| null` | LinkedIn → GitHub | Location string |
| `experience` | `ExperienceEntry[]` | LinkedIn | Work history |
| `education` | `EducationEntry[]` | LinkedIn | Education history |
| `skills` | `string[]` | LinkedIn | Skill list |
| `linkedin_warning` | `string \| null` | LinkedIn | Set if scraper was partially blocked |
| `github_username` | `string \| null` | GitHub | GitHub login |
| `github_bio` | `string \| null` | GitHub | GitHub bio |
| `github_company` | `string \| null` | GitHub | Company from GitHub profile |
| `github_email` | `string \| null` | GitHub | Public email on GitHub |
| `github_avatar_url` | `string \| null` | GitHub | Avatar image URL |
| `github_blog` | `string \| null` | GitHub | Blog/website URL |
| `public_repos` | `int` | GitHub | Number of public repositories |
| `followers` | `int` | GitHub | GitHub follower count |
| `following` | `int` | GitHub | GitHub following count |
| `github_created_at` | `string \| null` | GitHub | Account creation date (ISO 8601) |
| `top_languages` | `LanguageStats[]` | GitHub | Languages ranked by repo count and bytes |
| `pinned_repos` | `GitHubRepo[]` | GitHub | Up to 6 pinned repositories |
| `total_contributions_90d` | `int` | GitHub | Contribution count over last 90 days |
| `most_starred_repo` | `GitHubRepo \| null` | GitHub | Highest-starred owned repo |
| `most_starred_repo_readme` | `string \| null` | GitHub | README content of most-starred repo |

### Sub-types

**ExperienceEntry**
```
title: string | null
company: string | null
duration: string | null
location: string | null
description: string | null
```

**EducationEntry**
```
school: string | null
degree: string | null
field: string | null
dates: string | null
```

**GitHubRepo**
```
name: string
description: string | null
stars: int
url: string
primary_language: string | null
```

**LanguageStats**
```
name: string
repo_count: int
bytes: int
```

---

## Test Search Queries

All queries below were run against a dataset of real scraped profiles.

---

### Query 1: Location + Skill Filter

Find candidates from NUST Islamabad with Applied Machine Learning experience.

```
GET /search?q=NUST%2C%20Islamabad&skills=Applied%20Machine%20Learning&k=3
```

**Expected behaviour:** Only candidates with `Applied Machine Learning` in their skills list are returned, regardless of semantic similarity score.

**Result:**
> 1 result returned. Abdullah Ejaz at similarity score **0.29** — the only candidate in the dataset with `Applied Machine Learning` listed as a skill. Score is lower because the query targets location rather than a skill description, but the filter ensures correctness.

---

### Query 2: Semantic Role Match

Find candidates who fit a Product Developer profile.

```
GET /search?q=Product%20Developer&k=3
```

**Expected behaviour:** Profiles are ranked purely by semantic similarity to the query. No filters applied.

**Results:**

| Rank | Candidate | Score | Reason |
|---|---|---|---|
| 1 | Faizan Anwar | 0.51 | Headline: *Product Developer @ Particula Tech* |
| 2 | Muhammad Riyan Aslam | 0.43 | Current role: *Lead Product Engineer* |
| 3 | Abdullah Ejaz | 0.41 | No product-related information in embedded metadata |

---

### Query 3: Multi-filter: Role + Skill + Location

Find Full Stack Developers in Islamabad who know FastAPI.

```
GET /search?q=Full%20Stack%20Dev&skills=FastAPI&location=Islam%C4%81b%C4%81d&k=3
```

**Expected behaviour:** Results must have `FastAPI` in skills and `Islamabad` in location field. Query semantics rank by full-stack relevance.

**Results:**

| Rank | Candidate | Score | Reason |
|---|---|---|---|
| 1 | Abdullah Naeem | 0.57 | Full Stack Dev @ Salik Labs, has FastAPI, located in Islamabad |
| 2 | Muhammad Riyan Aslam | 0.40 | Has FastAPI in skills, located in Islamabad |

> No further results — only 2 candidates in the dataset matched both the `FastAPI` skill and `Islamabad` location filters.

---

## Deployment

### Railway (Production)

1. Push this repository to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
3. Select this repository — Railway auto-detects the `Dockerfile`
4. Go to **Variables** and add:

```
MONGODB_URI              = mongodb+srv://...
UPSTASH_REDIS_REST_URL   = https://...upstash.io
UPSTASH_REDIS_REST_TOKEN = ...
PINECONE_API_KEY         = ...
PINECONE_INDEX           = candidate-intelligence
```

5. Railway builds and deploys automatically. The first build is slow (~5–10 min) because the `Dockerfile` pre-downloads the `all-MiniLM-L6-v2` model at build time.

Once deployed, scrape profiles against the live URL:
```powershell
python scrape_and_store.py --github <username> --linkedin <url> --api https://your-app.up.railway.app
```

**Live URL:** `https://<your-railway-url>.up.railway.app` *(update after first deploy)*

---

## Deployment Postmortem

**What broke:** The LinkedIn scraper was by far the most time-consuming component to get right, taking several hours of debugging across multiple layers.

LinkedIn's bot protection sometimes would block access from a headless browser so i landed on using the browser headful to avoid any problems at all, This was just a start. The deeper problem was LinkedIn's DOM structure: class names are dynamically hashed on every page load, sections are lazy-loaded via IntersectionObserver (meaning a single `scrollTo` call lands at the bottom of the currently-rendered page, not the final one), and deeply nested divs make any CSS-selector-based approach brittle.

Skills were the worst offender. The skills section sits at the very bottom of the profile page and wouldn't render until scrolled to but even after scrolling, the skills array kept coming back empty. The fix was to navigate to LinkedIn's dedicated `/details/skills/` sub-page instead, scroll it incrementally using `page.mouse.wheel` (which fires the scroll events LinkedIn's IntersectionObserver actually listens to, unlike `window.scrollTo`), and extract text from `<p>` tags directly since class names couldn't be relied upon.

That still left noise in the output like navbar items, ad feedback strings, and skill proof entries (e.g. "Software Intern at Mezino Technologies" appearing alongside the actual skill name) all came through in the raw extraction. Each required its own filter: a NOISE regex for UI boilerplate and ad copy, an "at Company" pattern for proof entries, and keyword filters for institution names bleeding in from education data.
