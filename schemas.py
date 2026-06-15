"""
Typed output schemas for both scrapers.

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
"""
from typing import Optional

from pydantic import BaseModel, Field


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
