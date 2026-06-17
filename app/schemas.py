"""
Typed output schemas for both scrapers and the unified candidate profile.

GitHubProfile schema
--------------------
{
  "username": "str",
  "name": "str | null",
  "bio": "str | null",
  "location": "str | null",
  "company": "str | null",
  "email": "str | null",
  "avatar_url": "str | null",
  "blog": "str | null",
  "public_repos": "int",
  "followers": "int",
  "following": "int",
  "created_at": "str (ISO 8601) | null",
  "top_languages": [{"name": "str", "repo_count": "int", "bytes": "int"}],
  "pinned_repos": [{"name": "str", "description": "str|null", "stars": "int", "url": "str", "primary_language": "str|null"}],
  "total_contributions_90d": "int",
  "most_starred_repo": "GitHubRepo | null",
  "most_starred_repo_readme": "str | null"
}

LinkedInProfile schema
----------------------
{
  "name": "str | null",
  "headline": "str | null",
  "current_role": "str | null",
  "current_company": "str | null",
  "location": "str | null",
  "experience": [{"title": "str|null", "company": "str|null", "duration": "str|null", "location": "str|null", "description": "str|null"}],
  "education": [{"school": "str|null", "degree": "str|null", "field": "str|null", "dates": "str|null"}],
  "skills": ["str"],
  "warning": "str | null  -- populated when blocked or partially parsed"
}

CandidateProfile schema (unified)
----------------------------------
{
  "scraped_at": "str (ISO 8601)",
  "source_urls": {"github": "str|null", "linkedin": "str|null"},
  "name": "str | null",
  "headline": "str | null",
  "current_role": "str | null",
  "current_company": "str | null",
  "location": "str | null",
  "experience": [...],
  "education": [...],
  "skills": ["str"],
  "linkedin_warning": "str | null",
  "github_username": "str | null",
  "github_bio": "str | null",
  "github_company": "str | null",
  "github_email": "str | null",
  "github_avatar_url": "str | null",
  "github_blog": "str | null",
  "public_repos": "int",
  "followers": "int",
  "following": "int",
  "github_created_at": "str (ISO 8601) | null",
  "top_languages": [...],
  "pinned_repos": [...],
  "total_contributions_90d": "int",
  "most_starred_repo": "GitHubRepo | null",
  "most_starred_repo_readme": "str | null"
}
"""
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class GitHubRepo(BaseModel):
    name: str
    description: Optional[str] = None
    stars: int = 0
    url: str
    primary_language: Optional[str] = None


class LanguageStats(BaseModel):
    name: str
    repo_count: int
    bytes: int


class GitHubProfile(BaseModel):
    username: str
    name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    blog: Optional[str] = None
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    created_at: Optional[str] = None
    top_languages: list[LanguageStats] = Field(default_factory=list)
    pinned_repos: list[GitHubRepo] = Field(default_factory=list)
    total_contributions_90d: int = 0
    most_starred_repo: Optional[GitHubRepo] = None
    most_starred_repo_readme: Optional[str] = None


class ExperienceEntry(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class EducationEntry(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    dates: Optional[str] = None


class LinkedInProfile(BaseModel):
    name: Optional[str] = None
    headline: Optional[str] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    warning: Optional[str] = None


# ── Unified profile ────────────────────────────────────────────────────────────

class SourceUrls(BaseModel):
    github: Optional[str] = None
    linkedin: Optional[str] = None


class CandidateProfile(BaseModel):
    scraped_at: str
    source_urls: SourceUrls
    # Identity fields — LinkedIn preferred, GitHub fallback
    name: Optional[str] = None
    headline: Optional[str] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    location: Optional[str] = None
    # LinkedIn-sourced
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    linkedin_warning: Optional[str] = None
    # GitHub-sourced
    github_username: Optional[str] = None
    github_bio: Optional[str] = None
    github_company: Optional[str] = None
    github_email: Optional[str] = None
    github_avatar_url: Optional[str] = None
    github_blog: Optional[str] = None
    public_repos: int = 0
    followers: int = 0
    following: int = 0
    github_created_at: Optional[str] = None
    top_languages: list[LanguageStats] = Field(default_factory=list)
    pinned_repos: list[GitHubRepo] = Field(default_factory=list)
    total_contributions_90d: int = 0
    most_starred_repo: Optional[GitHubRepo] = None
    most_starred_repo_readme: Optional[str] = None


class ProfileCreateRequest(BaseModel):
    github_username: Optional[str] = None
    github_profile: Optional[GitHubProfile] = None
    linkedin_url: Optional[str] = None
    linkedin_profile: Optional[LinkedInProfile] = None

    @model_validator(mode="after")
    def at_least_one(self) -> "ProfileCreateRequest":
        if not self.github_username and not self.linkedin_url:
            raise ValueError("Provide at least one of github_username or linkedin_url")
        return self


class ProfileResponse(CandidateProfile):
    id: str


class SearchResult(BaseModel):
    score: float
    profile: ProfileResponse


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    cached: bool


# ── Phase 2 schemas ────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    github_username: Optional[str] = None
    linkedin_url: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one(self) -> "ScrapeRequest":
        if not self.github_username and not self.linkedin_url:
            raise ValueError("Provide at least one of github_username or linkedin_url")
        return self


class ResumeExperience(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class ResumeEducation(BaseModel):
    school: Optional[str] = None
    degree: Optional[str] = None
    field: Optional[str] = None
    dates: Optional[str] = None


class ResumeExtraction(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_username: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ResumeExperience] = Field(default_factory=list)
    education: list[ResumeEducation] = Field(default_factory=list)


class IngestResponse(ProfileResponse):
    missing_links: list[str] = Field(default_factory=list)
    resume_parsed: bool = False


# ── Bulk ingestion schemas ─────────────────────────────────────────────────────

class BulkJobError(BaseModel):
    file: str
    error: str


class BulkJobStatus(BaseModel):
    job_id: str
    status: str  # pending | running | complete
    total: int
    processed: int
    failed: int
    errors: list[BulkJobError] = Field(default_factory=list)


class BulkIngestResponse(BaseModel):
    job_id: str
    status: str
    total: int


# ── Chat schemas ───────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatCitation(BaseModel):
    id: str
    name: str
    score: float
    source: str = "semantic"  # "semantic" | "filter"


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: list[ChatCitation]
