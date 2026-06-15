"""
Candidate Intelligence API — FastAPI application.

Endpoints
---------
POST /profiles        Insert or update a candidate profile.
GET  /profiles/{id}   Fetch a single profile by MongoDB ObjectId.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pymongo import MongoClient, ReturnDocument

from schemas import (
    CandidateProfile,
    GitHubProfile,
    LinkedInProfile,
    ProfileCreateRequest,
    ProfileResponse,
    SourceUrls,
)

load_dotenv()

app = FastAPI(
    title="Candidate Intelligence API",
    description="Aggregates GitHub and LinkedIn data into searchable candidate profiles.",
    version="1.0.0",
)

_client: Optional[MongoClient] = None


def _db():
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/candidate_intelligence")
        _client = MongoClient(uri)
    return _client["candidate_intelligence"]


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
