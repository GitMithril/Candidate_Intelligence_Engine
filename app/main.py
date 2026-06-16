"""
Candidate Intelligence API — FastAPI application.

Endpoints
---------
POST /profiles              Insert or update a candidate profile.
GET  /profiles/{id}         Fetch a single profile by MongoDB ObjectId.
POST /profiles/{id}/embed   Generate and store a vector embedding.
GET  /search                Semantic search over candidate profiles.
POST /scrape                Scrape GitHub/LinkedIn by URL, store and embed automatically.
POST /ingest                Accept resume PDF + optional URLs, build and store a profile.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from pymongo import MongoClient, ReturnDocument

from .embeddings import embed_and_store, embed_profile_by_id, embed_text, query_similar
from .scrapers.github import scrape_github
from .scrapers.linkedin import scrape_linkedin
from .schemas import (
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
    embed_and_store(str(result["_id"]), result)
    return result


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
    linkedin_url: Optional[str] = Form(None),
    github_username: Optional[str] = Form(None),
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
        content = resume.file.read()
        text = extract_pdf_text(content)
        try:
            resume_data = parse_resume(text)
        except Exception as exc:
            if not linkedin_url and not github_username:
                raise HTTPException(
                    status_code=422,
                    detail=f"Resume parsing failed and no URLs were provided: {exc}",
                )
            # URLs are available — continue without resume-extracted fields.
            resume_data = None

        if not linkedin_url:
            if resume_data.linkedin_url:
                linkedin_url = resume_data.linkedin_url
            else:
                missing_links.append("linkedin_url")

        if not github_username:
            if resume_data.github_username:
                github_username = resume_data.github_username
            else:
                missing_links.append("github_username")

    gh_profile: Optional[GitHubProfile] = None
    li_profile: Optional[LinkedInProfile] = None

    if github_username:
        try:
            gh_profile = scrape_github(github_username)
        except Exception:
            pass  # not fatal — resume or LinkedIn may cover identity fields

    if linkedin_url:
        li_profile = scrape_linkedin(linkedin_url)

    # Resume fills gaps when LinkedIn is unavailable or blocked.
    if li_profile is None and resume_data:
        first = resume_data.experience[0] if resume_data.experience else None
        li_profile = LinkedInProfile(
            name=resume_data.name,
            current_role=first.title if first else None,
            current_company=first.company if first else None,
            skills=resume_data.skills,
            experience=[ExperienceEntry(**e.model_dump()) for e in resume_data.experience],
            education=[EducationEntry(**e.model_dump()) for e in resume_data.education],
        )
    elif li_profile is not None and resume_data:
        # Union resume skills into LinkedIn skills (LinkedIn takes precedence for duplicates).
        existing_lower = {s.lower() for s in li_profile.skills}
        extra = [s for s in resume_data.skills if s.lower() not in existing_lower]
        li_profile.skills.extend(extra)

    # Build the unified CandidateProfile.
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
        raise HTTPException(status_code=422, detail="Could not extract any usable profile data.")

    doc = profile.model_dump()

    # Supplement email from resume when GitHub didn't provide one.
    if resume_data and resume_data.email and not doc.get("github_email"):
        doc["github_email"] = resume_data.email

    # Dedup key: GitHub username > LinkedIn URL > resume email > no dedup (fresh insert).
    if github_username:
        filter_q: Optional[dict] = {"github_username": github_username}
    elif linkedin_url:
        filter_q = {"source_urls.linkedin": linkedin_url}
    elif resume_data and resume_data.email:
        filter_q = {"github_email": resume_data.email}
    else:
        filter_q = None

    result = _store_and_embed(doc, filter_q)
    _serialize(result)
    result["missing_links"] = missing_links
    result["resume_parsed"] = resume_data is not None
    return result
