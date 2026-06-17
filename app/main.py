"""
Candidate Intelligence API — FastAPI application.

Endpoints
---------
POST /profiles                  Insert or update a candidate profile.
GET  /profiles/{id}             Fetch a single profile by MongoDB ObjectId.
POST /profiles/{id}/embed       Generate and store a vector embedding.
GET  /search                    Semantic search over candidate profiles.
POST /scrape                    Scrape GitHub/LinkedIn by URL, store and embed automatically.
POST /ingest                    Accept resume PDF + optional URLs, build and store a profile.
POST /ingest/bulk               Start a background bulk ingestion job (PDFs, ZIP, or Drive URL).
GET  /ingest/bulk/{job_id}      Poll progress of a bulk ingestion job.
POST /chat                      Conversational RAG over the candidate database; returns answer + citations.
DELETE /chat/{session_id}       Clear a chat session history.
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pymongo import MongoClient, ReturnDocument

from .embeddings import embed_and_store, embed_profile_by_id, embed_text, query_similar
from .scrapers.github import scrape_github
from .scrapers.linkedin import scrape_linkedin
from .schemas import (
    BulkIngestResponse,
    BulkJobStatus,
    ChatCitation,
    ChatRequest,
    ChatResponse,
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    GitHubProfile,
    IngestResponse,
    LinkedInProfile,
    ProfileCreateRequest,
    ProfileResponse,
    ResumeExtraction,
    ScrapeRequest,
    SearchResponse,
    SearchResult,
    SourceUrls,
)
from .utils.llm import parse_resume
from .utils.pdf import extract_pdf_text

load_dotenv()

app = FastAPI(
    title="Candidate Intelligence API",
    description="Aggregates GitHub and LinkedIn data into searchable candidate profiles.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://candidate-intelligence-engine.vercel.app", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_client: Optional[MongoClient] = None
_REDIS_UNSET = object()
_redis_client = _REDIS_UNSET


class _RedisAdapter:
    """Normalises upstash-redis and redis-py behind a single get/set interface.

    upstash-redis returns str | None; redis-py returns bytes | None.
    Both support set(key, value, ex=seconds).
    """
    def __init__(self, client, decode: bool = False):
        self._c = client
        self._decode = decode

    def get(self, key: str) -> Optional[str]:
        val = self._c.get(key)
        if val is None:
            return None
        return val.decode() if self._decode else val

    def set(self, key: str, value: str, ex: int = 300) -> None:
        self._c.set(key, value, ex=ex)

    def delete(self, key: str) -> None:
        self._c.delete(key)


def _db():
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/candidate_intelligence")
        _client = MongoClient(uri)
    return _client["candidate_intelligence"]


def _redis() -> Optional[_RedisAdapter]:
    """Return a Redis adapter.

    Priority:
      1. UPSTASH_REDIS_REST_URL + UPSTASH_REDIS_REST_TOKEN  (cloud / production)
      2. REDIS_URL (e.g. redis://localhost:6379)             (local Docker)
      3. None — caching disabled, search still works
    """
    global _redis_client
    if _redis_client is _REDIS_UNSET:
        upstash_url = os.environ.get("UPSTASH_REDIS_REST_URL")
        upstash_token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
        redis_url = os.environ.get("REDIS_URL")

        if upstash_url and upstash_token:
            from upstash_redis import Redis as UpstashRedis
            _redis_client = _RedisAdapter(UpstashRedis(url=upstash_url, token=upstash_token), decode=False)
        elif redis_url:
            import redis as redis_py
            _redis_client = _RedisAdapter(redis_py.from_url(redis_url), decode=True)
        else:
            _redis_client = None
    return _redis_client


_job_store: dict[str, dict] = {}
_chat_store: dict[str, list] = {}


def _save_job(job_id: str, state: dict) -> None:
    _job_store[job_id] = state
    r = _redis()
    if r:
        r.set(f"bulk_job:{job_id}", json.dumps(state), ex=3600)


def _load_job(job_id: str) -> Optional[dict]:
    r = _redis()
    if r:
        raw = r.get(f"bulk_job:{job_id}")
        if raw:
            return json.loads(raw)
    return _job_store.get(job_id)


def _load_history(session_id: str) -> list[dict]:
    r = _redis()
    if r:
        raw = r.get(f"chat:{session_id}")
        if raw:
            return json.loads(raw)
    return _chat_store.get(session_id, [])


def _save_history(session_id: str, history: list[dict]) -> None:
    _chat_store[session_id] = history
    r = _redis()
    if r:
        r.set(f"chat:{session_id}", json.dumps(history), ex=86400)


def _delete_history(session_id: str) -> None:
    _chat_store.pop(session_id, None)
    r = _redis()
    if r:
        r.delete(f"chat:{session_id}")


def _merge(req: ProfileCreateRequest) -> CandidateProfile:
    gh: Optional[GitHubProfile] = req.github_profile
    li: Optional[LinkedInProfile] = req.linkedin_profile

    source_urls = SourceUrls(
        github=f"https://github.com/{req.github_username}" if req.github_username else None,
        linkedin=req.linkedin_url,
    )

    return CandidateProfile(
        scraped_at=datetime.now(timezone.utc).isoformat(),
        source_urls=source_urls,
        name=(li.name if li else None) or (gh.name if gh else None),
        headline=li.headline if li else None,
        current_role=(li.current_role if li else None) or (gh.company if gh else None),
        current_company=(li.current_company if li else None) or (gh.company if gh else None),
        location=(li.location if li else None) or (gh.location if gh else None),
        experience=li.experience if li else [],
        education=li.education if li else [],
        skills=li.skills if li else [],
        linkedin_warning=li.warning if li else None,
        github_username=gh.username if gh else req.github_username,
        github_bio=gh.bio if gh else None,
        github_company=gh.company if gh else None,
        github_email=gh.email if gh else None,
        github_avatar_url=gh.avatar_url if gh else None,
        github_blog=gh.blog if gh else None,
        public_repos=gh.public_repos if gh else 0,
        followers=gh.followers if gh else 0,
        following=gh.following if gh else 0,
        github_created_at=gh.created_at if gh else None,
        top_languages=gh.top_languages if gh else [],
        pinned_repos=gh.pinned_repos if gh else [],
        total_contributions_90d=gh.total_contributions_90d if gh else 0,
        most_starred_repo=gh.most_starred_repo if gh else None,
        most_starred_repo_readme=gh.most_starred_repo_readme if gh else None,
    )


def _serialize(doc: dict) -> dict:
    """Convert MongoDB _id ObjectId to string id for API responses."""
    doc["id"] = str(doc.pop("_id"))
    return doc


@app.post(
    "/profiles",
    response_model=ProfileResponse,
    status_code=201,
    summary="Insert or update a candidate profile",
    response_description="The stored candidate profile with its MongoDB id.",
)
def create_profile(req: ProfileCreateRequest):
    """
    Merge GitHub and LinkedIn scraper outputs into a unified candidate profile
    and store it in MongoDB. If a profile for the same github_username (or
    linkedin_url when no GitHub username is provided) already exists, it is
    replaced with fresh data.
    """
    profile = _merge(req)
    doc = profile.model_dump()

    db = _db()
    filter_q = (
        {"github_username": req.github_username}
        if req.github_username
        else {"source_urls.linkedin": req.linkedin_url}
    )

    result = db.profiles.find_one_and_replace(
        filter_q,
        doc,
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return _serialize(result)


@app.get(
    "/profiles/{profile_id}",
    response_model=ProfileResponse,
    summary="Fetch a candidate profile by ID",
    response_description="The candidate profile matching the given MongoDB ObjectId.",
)
def get_profile(profile_id: str):
    """
    Retrieve a single candidate profile by its MongoDB ObjectId string.
    Returns 400 for a malformed id and 404 if no profile is found.
    """
    try:
        oid = ObjectId(profile_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid profile id format — expected a 24-character hex ObjectId.")

    doc = _db().profiles.find_one({"_id": oid})
    if doc is None:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return _serialize(doc)


@app.post(
    "/profiles/{profile_id}/embed",
    summary="Generate and store a vector embedding for a profile",
    response_description="Confirmation that the embedding was stored in Pinecone.",
)
def embed_profile(profile_id: str):
    """
    Embed the candidate profile identified by `profile_id` using
    all-MiniLM-L6-v2 and upsert the 384-dim vector to Pinecone.
    Returns 400 for a malformed id and 404 if no profile is found.
    """
    try:
        ObjectId(profile_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid profile id format — expected a 24-character hex ObjectId.")

    try:
        embed_profile_by_id(profile_id, _db())
    except ValueError:
        raise HTTPException(status_code=404, detail="Profile not found.")

    return {"id": profile_id, "embedded": True}


@app.get(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search over candidate profiles",
    response_description="Profiles ranked by similarity score, optionally filtered.",
)
def search_profiles(
    q: str = Query(..., min_length=1, description="Plain-English search query"),
    skills: Optional[str] = Query(None, description="Comma-separated required skills (must match all)"),
    location: Optional[str] = Query(None, description="Location substring filter (case-insensitive)"),
    k: int = Query(10, ge=1, le=50, description="Number of results to return (default 10, max 50)"),
):
    """
    Embed the query with all-MiniLM-L6-v2, retrieve the top-k nearest profiles
    from Pinecone, fetch full documents from MongoDB, and apply optional
    skills / location filters. Repeated identical queries are served from a
    Redis cache with a 5-minute TTL.
    """
    cache_key = f"search:{q}|{skills or ''}|{location or ''}|{k}"
    r = _redis()

    if r:
        raw = r.get(cache_key)
        if raw:
            stored = json.loads(raw)
            return {"query": q, "results": stored["results"], "cached": True}

    vector = embed_text(q)
    # Fetch extra candidates to absorb any filter losses before capping at k.
    fetch_k = min(k * 4, 100) if (skills or location) else k
    matches = query_similar(vector, fetch_k)

    db = _db()
    results = []
    for match in matches.matches:
        try:
            doc = db.profiles.find_one({"_id": ObjectId(match.id)})
        except Exception:
            continue
        if doc is None:
            continue

        if skills:
            required = {s.strip().lower() for s in skills.split(",")}
            doc_skills = {s.lower() for s in (doc.get("skills") or [])}
            if not required.issubset(doc_skills):
                continue

        if location:
            if location.lower() not in (doc.get("location") or "").lower():
                continue

        _serialize(doc)
        results.append({"score": match.score, "profile": doc})
        if len(results) >= k:
            break

    if r:
        r.set(cache_key, json.dumps({"results": results}), ex=300)

    return {"query": q, "results": results, "cached": False}


def _build_from_resume(resume_data: ResumeExtraction) -> CandidateProfile:
    """Construct a CandidateProfile from resume-extracted data alone (no scraping)."""
    first = resume_data.experience[0] if resume_data.experience else None
    return CandidateProfile(
        scraped_at=datetime.now(timezone.utc).isoformat(),
        source_urls=SourceUrls(),
        name=resume_data.name,
        location=resume_data.location,
        current_role=first.title if first else None,
        current_company=first.company if first else None,
        skills=resume_data.skills,
        experience=[ExperienceEntry(**e.model_dump()) for e in resume_data.experience],
        education=[EducationEntry(**e.model_dump()) for e in resume_data.education],
        github_email=resume_data.email,
    )


def _store_and_embed(doc: dict, filter_q: Optional[dict]) -> dict:
    """Upsert doc into MongoDB and embed in Pinecone. Returns the serialized doc."""
    db = _db()
    if filter_q:
        result = db.profiles.find_one_and_replace(
            filter_q, doc, upsert=True, return_document=ReturnDocument.AFTER
        )
    else:
        ins = db.profiles.insert_one(doc)
        result = db.profiles.find_one({"_id": ins.inserted_id})
    logger.info("[ingest] Stored profile id=%s name=%r", result["_id"], result.get("name"))
    embed_and_store(str(result["_id"]), result)
    logger.info("[ingest] Embedded profile id=%s", result["_id"])
    return result


def _assemble_and_store(
    resume_data: Optional[ResumeExtraction],
    linkedin_url: Optional[str],
    github_username: Optional[str],
) -> dict:
    """Scrape URLs, merge with resume data, store in MongoDB, embed in Pinecone.

    Returns the serialized stored document (with 'id').
    Raises ValueError if no usable profile data can be assembled.
    """
    gh_profile: Optional[GitHubProfile] = None
    li_profile: Optional[LinkedInProfile] = None

    if github_username:
        logger.info("[ingest] GitHub scrape start: %s", github_username)
        try:
            gh_profile = scrape_github(github_username)
            logger.info("[ingest] GitHub scrape OK: %s (repos=%s, langs=%s)", github_username, gh_profile.public_repos, len(gh_profile.top_languages))
        except Exception as exc:
            logger.warning("[ingest] GitHub scrape failed: %s — %s", github_username, exc)

    if linkedin_url:
        logger.info("[ingest] LinkedIn scrape start: %s", linkedin_url)
        li_profile = scrape_linkedin(linkedin_url)
        if li_profile.warning:
            logger.warning("[ingest] LinkedIn scrape warning: %s", li_profile.warning)
        else:
            logger.info("[ingest] LinkedIn scrape OK: name=%r, exp=%d, edu=%d, skills=%d", li_profile.name, len(li_profile.experience), len(li_profile.education), len(li_profile.skills))

    li_failed = li_profile is not None and li_profile.warning and not li_profile.name
    if li_failed:
        logger.info("[ingest] LinkedIn scrape failed with no data — falling back to resume data")
    if (li_profile is None or li_failed) and resume_data:
        first = resume_data.experience[0] if resume_data.experience else None
        li_profile = LinkedInProfile(
            name=resume_data.name,
            location=resume_data.location,
            current_role=first.title if first else None,
            current_company=first.company if first else None,
            skills=resume_data.skills,
            experience=[ExperienceEntry(**e.model_dump()) for e in resume_data.experience],
            education=[EducationEntry(**e.model_dump()) for e in resume_data.education],
            warning=li_profile.warning if li_failed else None,
        )
    elif li_profile is not None and resume_data:
        existing_lower = {s.lower() for s in li_profile.skills}
        extra = [s for s in resume_data.skills if s.lower() not in existing_lower]
        li_profile.skills.extend(extra)

    if github_username or linkedin_url:
        profile_req = ProfileCreateRequest(
            github_username=github_username,
            github_profile=gh_profile,
            linkedin_url=linkedin_url,
            linkedin_profile=li_profile,
        )
        profile = _merge(profile_req)
    elif resume_data:
        profile = _build_from_resume(resume_data)
    else:
        raise ValueError("No profile data could be assembled.")

    # Resume location takes priority over scraped LinkedIn/GitHub location.
    if resume_data and resume_data.location:
        profile.location = resume_data.location

    doc = profile.model_dump()
    if resume_data and resume_data.email and not doc.get("github_email"):
        doc["github_email"] = resume_data.email

    if github_username:
        filter_q: Optional[dict] = {"github_username": github_username}
    elif linkedin_url:
        filter_q = {"source_urls.linkedin": linkedin_url}
    elif resume_data and resume_data.email:
        filter_q = {"github_email": resume_data.email}
    else:
        filter_q = None

    result = _store_and_embed(doc, filter_q)
    return _serialize(result)


def _extract_zip_pdfs(zip_bytes: bytes) -> tuple[list[tuple[str, bytes]], list[dict]]:
    """Extract PDFs from a ZIP archive.

    Returns (pdf_items, errors). Non-PDFs and directories are recorded in errors.
    """
    pdf_items: list[tuple[str, bytes]] = []
    errors: list[dict] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            if name.endswith("/") or name.startswith("__MACOSX") or name.startswith("."):
                continue
            data = zf.read(name)
            if data[:4] == b"%PDF":
                pdf_items.append((name, data))
            else:
                errors.append({"file": name, "error": f"'{name}' is not a PDF — skipped."})

    return pdf_items, errors


def _process_resume_bytes(filename: str, pdf_bytes: bytes) -> dict:
    """Extract, parse, and store a single resume PDF. Raises on any error."""
    logger.info("[bulk] Processing: %s", filename)
    if pdf_bytes[:4] != b"%PDF":
        raise ValueError(f"'{filename}' is not a valid PDF.")

    text = extract_pdf_text(pdf_bytes)
    if not text.strip():
        raise ValueError(f"Could not extract text from '{filename}'.")
    logger.info("[bulk] PDF text extracted: %d chars — %s", len(text), filename)

    resume_data = parse_resume(text)
    logger.info("[bulk] LLM parse OK: name=%r, skills=%d, exp=%d — %s", resume_data.name, len(resume_data.skills), len(resume_data.experience), filename)

    if not any([resume_data.name, resume_data.email, resume_data.skills, resume_data.experience]):
        raise ValueError(f"LLM could not extract usable data from '{filename}'.")

    return _assemble_and_store(resume_data, resume_data.linkedin_url, resume_data.github_username)


def _run_bulk_ingest(job_id: str, items: list[tuple[str, bytes]], drive_url: Optional[str]) -> None:
    """Background task: process each PDF, updating job state after every file."""
    state = _load_job(job_id)
    state["status"] = "running"
    _save_job(job_id, state)

    all_items = list(items)

    if drive_url:
        try:
            from .utils.drive import download_drive_pdfs
            drive_items = download_drive_pdfs(drive_url)
            all_items.extend(drive_items)
            state["total"] = len(all_items)
            _save_job(job_id, state)
        except Exception as exc:
            state["failed"] += 1
            state["errors"].append({"file": "google_drive", "error": str(exc)})
            _save_job(job_id, state)
            if not all_items:
                state["status"] = "complete"
                _save_job(job_id, state)
                return

    for filename, pdf_bytes in all_items:
        try:
            _process_resume_bytes(filename, pdf_bytes)
            state["processed"] += 1
        except Exception as exc:
            state["failed"] += 1
            state["errors"].append({"file": filename, "error": str(exc)})
        _save_job(job_id, state)

    state["status"] = "complete"
    _save_job(job_id, state)


@app.post(
    "/scrape",
    response_model=ProfileResponse,
    status_code=201,
    summary="Scrape GitHub and/or LinkedIn and store the result",
    response_description="The scraped, stored, and embedded candidate profile.",
)
def scrape(req: ScrapeRequest):
    """
    Trigger a live GitHub and/or LinkedIn scrape by providing a username / URL.
    The resulting profile is stored in MongoDB and automatically embedded in Pinecone.
    """
    gh_profile: Optional[GitHubProfile] = None
    li_profile: Optional[LinkedInProfile] = None

    if req.github_username:
        try:
            gh_profile = scrape_github(req.github_username)
        except Exception as exc:
            if not req.linkedin_url:
                raise HTTPException(status_code=502, detail=f"GitHub scraping failed: {exc}")

    if req.linkedin_url:
        li_profile = scrape_linkedin(req.linkedin_url)

    profile_req = ProfileCreateRequest(
        github_username=req.github_username,
        github_profile=gh_profile,
        linkedin_url=req.linkedin_url,
        linkedin_profile=li_profile,
    )
    doc = _merge(profile_req).model_dump()

    filter_q = (
        {"github_username": req.github_username}
        if req.github_username
        else {"source_urls.linkedin": req.linkedin_url}
    )
    result = _store_and_embed(doc, filter_q)
    return _serialize(result)


@app.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=201,
    summary="Ingest a resume PDF and optional URLs into a unified candidate profile",
    response_description="The stored profile, with missing_links listing any URLs not found.",
)
def ingest(
    linkedin_url: Optional[str] = Form(default=None, example="https://linkedin.com/in/username"),
    github_username: Optional[str] = Form(default=None, example="github-username"),
    resume: Optional[UploadFile] = File(None),
):
    """
    Accept any combination of a resume PDF, a LinkedIn URL, and a GitHub username.
    The resume is parsed by an LLM to extract structured fields and any embedded URLs.
    Missing URLs are returned in `missing_links` so the caller can prompt the user.
    The profile is stored in MongoDB and embedded in Pinecone automatically.
    """
    if not linkedin_url and not github_username and not resume:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one of: resume (PDF), linkedin_url, github_username",
        )

    resume_data: Optional[ResumeExtraction] = None
    missing_links: list[str] = []

    if resume:
        logger.info("[ingest] Resume upload: %s", resume.filename)
        content = resume.file.read()
        if content[:4] != b"%PDF":
            raise HTTPException(status_code=400, detail=f"'{resume.filename}' is not a valid PDF.")
        text = extract_pdf_text(content)
        logger.info("[ingest] PDF text extracted: %d chars", len(text))
        try:
            resume_data = parse_resume(text)
            logger.info("[ingest] LLM parse OK: name=%r, email=%r, skills=%d, exp=%d", resume_data.name, resume_data.email, len(resume_data.skills), len(resume_data.experience))
        except Exception as exc:
            logger.error("[ingest] LLM parse failed: %s", exc)
            if not linkedin_url and not github_username:
                raise HTTPException(
                    status_code=422,
                    detail=f"Resume parsing failed and no URLs were provided: {exc}",
                )
            resume_data = None

        if resume_data is not None:
            if not linkedin_url:
                if resume_data.linkedin_url:
                    linkedin_url = resume_data.linkedin_url
                    logger.info("[ingest] LinkedIn URL from resume: %s", linkedin_url)
                else:
                    missing_links.append("linkedin_url")
            if not github_username:
                if resume_data.github_username:
                    github_username = resume_data.github_username
                    logger.info("[ingest] GitHub username from resume: %s", github_username)
                else:
                    missing_links.append("github_username")

    try:
        result = _assemble_and_store(resume_data, linkedin_url, github_username)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    result["missing_links"] = missing_links
    result["resume_parsed"] = resume_data is not None
    return result


@app.post(
    "/ingest/bulk",
    response_model=BulkIngestResponse,
    status_code=202,
    summary="Start a background bulk resume ingestion job",
    response_description="Job ID to poll via GET /ingest/bulk/{job_id}.",
)
def ingest_bulk(
    background_tasks: BackgroundTasks,
    files: Optional[list[UploadFile]] = File(None),
    drive_url: Optional[str] = Form(default=None, example="https://drive.google.com/drive/folders/FOLDER_ID"),
):
    """
    Accept multiple PDFs, a ZIP archive containing PDFs, or a public Google Drive
    folder URL (or any combination). Processing runs in the background.

    Non-PDF direct uploads are rejected immediately with HTTP 400.
    Non-PDF files inside a ZIP or Drive folder are recorded as errors and skipped.

    Poll GET /ingest/bulk/{job_id} for progress.
    """
    if not files and not drive_url:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one of: files (PDF or ZIP), drive_url (public Google Drive folder URL).",
        )

    items: list[tuple[str, bytes]] = []
    pre_errors: list[dict] = []

    for f in (files or []):
        data = f.file.read()
        name = f.filename or "upload"

        if data[:4] == b"PK\x03\x04":
            pdf_items, zip_errors = _extract_zip_pdfs(data)
            items.extend(pdf_items)
            pre_errors.extend(zip_errors)
        elif data[:4] == b"%PDF":
            items.append((name, data))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"'{name}' is not a PDF or ZIP file. Only PDF and ZIP uploads are accepted.",
            )

    if not items and not drive_url:
        raise HTTPException(status_code=422, detail="No valid PDF files found in the uploaded files.")

    job_id = str(uuid.uuid4())
    _save_job(job_id, {
        "status": "pending",
        "total": len(items),
        "processed": 0,
        "failed": len(pre_errors),
        "errors": pre_errors,
    })

    background_tasks.add_task(_run_bulk_ingest, job_id, items, drive_url)

    return {"job_id": job_id, "status": "pending", "total": len(items)}


@app.get(
    "/ingest/bulk/{job_id}",
    response_model=BulkJobStatus,
    summary="Poll the status of a bulk ingestion job",
    response_description="Current progress of the bulk ingestion job.",
)
def get_bulk_job(job_id: str):
    """
    Returns the current status (pending / running / complete), counts of processed
    and failed files, and a per-file error list for anything that was skipped.
    """
    state = _load_job(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {"job_id": job_id, **state}


def _build_mongo_filter(criteria: dict) -> dict:
    """Translate LLM-extracted filter criteria into a MongoDB query.

    Only handles concrete, enumerable values: location, named skills, school.
    Role/concept filtering is handled by semantic search, not here.
    """
    conditions: list[dict] = []

    location = criteria.get("location")
    if location:
        conditions.append({"location": {"$regex": re.escape(location), "$options": "i"}})

    for skill in (criteria.get("skills") or []):
        conditions.append({"skills": {"$elemMatch": {"$regex": re.escape(skill), "$options": "i"}}})

    school = criteria.get("school")
    if school:
        conditions.append({"education": {"$elemMatch": {"school": {"$regex": re.escape(school), "$options": "i"}}}})

    if not conditions:
        return {}
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _filter_response(candidates: list[dict]) -> str:
    """Generate a concise template answer for filter queries — no LLM needed."""
    n = len(candidates)
    if n == 0:
        return "No candidates found matching your criteria."
    noun = "candidate" if n == 1 else "candidates"
    return f"Found **{n} {noun}** matching your criteria. Open any profile chip below to view their full details."


def _fetch_candidates(
    question: str,
    classification: dict,
    db,
) -> tuple[list[dict], list[ChatCitation]]:
    """Fetch candidate docs and build citations based on query classification.

    Shared by both the sync /chat endpoint and the async /chat/stream endpoint.
    Always sync — the streaming endpoint wraps it with asyncio.to_thread.
    """
    query_type = classification.get("type", "semantic")
    candidates: list[dict] = []
    citations: list[ChatCitation] = []

    if query_type == "filter":
        criteria = classification.get("criteria") or {}
        mongo_filter = _build_mongo_filter(criteria)
        for doc in db.profiles.find(mongo_filter).limit(30):
            _serialize(doc)
            candidates.append(doc)
            citations.append(ChatCitation(
                id=doc["id"],
                name=doc.get("name") or "Unknown",
                score=1.0,
                source="filter",
            ))
    elif query_type == "semantic":
        top_k = int(classification.get("top_k") or 10)
        vector = embed_text(question)
        matches = query_similar(vector, top_k)
        for match in matches.matches:
            try:
                doc = db.profiles.find_one({"_id": ObjectId(match.id)})
            except Exception:
                continue
            if doc is None:
                continue
            _serialize(doc)
            candidates.append(doc)
            citations.append(ChatCitation(
                id=doc["id"],
                name=doc.get("name") or "Unknown",
                score=round(match.score, 4),
                source="semantic",
            ))
    # "irrelevant": returns empty lists — LLM politely declines

    return candidates, citations


@app.post(
    "/chat",
    response_model=ChatResponse,
    summary="Conversational RAG over the candidate database",
    response_description="The assistant's answer grounded in matching candidate profiles, plus citations.",
)
def chat(req: ChatRequest):
    """
    Non-streaming chat. Classify query, fetch candidates, call LLM, return full answer.
    Prefer POST /chat/stream for a real-time experience.
    """
    from .utils.chat import answer_question, classify_query

    session_id = req.session_id or str(uuid.uuid4())
    history = _load_history(session_id)
    classification = classify_query(req.question)
    candidates, citations = _fetch_candidates(req.question, classification, _db())

    if classification.get("type") == "filter":
        answer = _filter_response(candidates)
    else:
        try:
            answer = answer_question(req.question, history, candidates)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"LLM error: {exc}")

    history.append({"role": "human", "content": req.question})
    history.append({"role": "assistant", "content": answer})
    _save_history(session_id, history)

    return ChatResponse(session_id=session_id, answer=answer, citations=citations)


@app.post(
    "/chat/stream",
    summary="Streaming conversational RAG (SSE)",
    response_description="Server-sent events: stage → meta → token… → done.",
)
async def chat_stream(req: ChatRequest):
    """
    Streaming variant of POST /chat.

    Emits server-sent events in this order:
      {"type": "stage",  "text": "Classifying query…"}
      {"type": "stage",  "text": "Searching database…"}
      {"type": "meta",   "session_id": "…", "citations": […]}
      {"type": "stage",  "text": "Generating answer…"}
      {"type": "token",  "text": "<chunk>"}   (many)
      {"type": "done"}
    On error: {"type": "error", "text": "…"}
    """
    from .utils.chat import classify_query, build_messages, get_llm

    session_id = req.session_id or str(uuid.uuid4())
    history = _load_history(session_id)

    async def generate():
        try:
            yield f"data: {json.dumps({'type': 'stage', 'text': 'Classifying query…'})}\n\n"
            classification = await asyncio.to_thread(classify_query, req.question)

            yield f"data: {json.dumps({'type': 'stage', 'text': 'Searching database…'})}\n\n"
            candidates, citations = await asyncio.to_thread(
                _fetch_candidates, req.question, classification, _db()
            )

            yield f"data: {json.dumps({'type': 'meta', 'session_id': session_id, 'citations': [c.model_dump() for c in citations]})}\n\n"

            if classification.get("type") == "filter":
                # Filter results are exact DB matches — no LLM needed.
                full_text = _filter_response(candidates)
                yield f"data: {json.dumps({'type': 'token', 'text': full_text})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'stage', 'text': 'Generating answer…'})}\n\n"
                messages = build_messages(req.question, history, candidates)
                llm = get_llm()
                full_text = ""
                async for chunk in llm.astream(messages):
                    token = chunk.content or ""
                    if token:
                        full_text += token
                        yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

            history.append({"role": "human", "content": req.question})
            history.append({"role": "assistant", "content": full_text})
            await asyncio.to_thread(_save_history, session_id, history)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'text': str(exc)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.delete(
    "/chat/{session_id}",
    status_code=204,
    summary="Clear a chat session",
    response_description="No content — session history has been deleted.",
)
def delete_chat_session(session_id: str):
    """
    Delete all conversation history for the given session_id from Redis.
    After this call the session_id is invalid; the next POST /chat with this
    session_id will start a fresh conversation.
    """
    _delete_history(session_id)
    return Response(status_code=204)
