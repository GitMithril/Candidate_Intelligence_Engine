"""
GitHub profile scraper.

Uses REST API for profile metadata, repos, language stats, and README.
Uses GraphQL for pinned repos and 90-day contribution calendar since these two
fields have no REST equivalent.

Required env var: GITHUB_TOKEN (personal access token, classic or fine-grained)
"""
from __future__ import annotations

import base64
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from ..schemas import GitHubProfile, GitHubRepo, LanguageStats

load_dotenv()

logger = logging.getLogger(__name__)

_API = "https://api.github.com"
_GQL = "https://api.github.com/graphql"


def _session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
    )
    return s


def _get(
    s: requests.Session,
    url: str,
    params: dict | None = None,
    allow_404: bool = False,
) -> Any:
    """GET with automatic rate-limit retry (primary and secondary limits)."""
    while True:
        r = s.get(url, params=params, timeout=30)
        if r.status_code in (403, 429):
            # Secondary rate limit: 403 with Retry-After but remaining > 0.
            retry_after = int(r.headers.get("Retry-After", "0"))
            if retry_after > 0:
                time.sleep(retry_after)
                continue
            # Primary rate limit: remaining quota exhausted.
            if r.headers.get("X-RateLimit-Remaining") == "0" or r.status_code == 429:
                reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(reset - int(time.time()), 1)
                time.sleep(wait)
                continue
        if r.status_code == 404 and allow_404:
            return None
        r.raise_for_status()
        return r.json()


def _paginate(
    s: requests.Session, url: str, params: dict | None = None
) -> list:
    p = {**(params or {}), "per_page": 100, "page": 1}
    results: list = []
    while True:
        page = _get(s, url, p)
        if not isinstance(page, list):
            break
        results.extend(page)
        if len(page) < 100:
            break
        p["page"] += 1
    return results


def _graphql(s: requests.Session, query: str, variables: dict) -> dict:
    r = s.post(_GQL, json={"query": query, "variables": variables}, timeout=30)
    r.raise_for_status()
    return r.json()


def _fetch_pinned_repos(s: requests.Session, username: str) -> list[GitHubRepo]:
    query = """
    query($login: String!) {
      user(login: $login) {
        pinnedItems(first: 6, types: [REPOSITORY]) {
          nodes {
            ... on Repository {
              name
              description
              stargazerCount
              url
              primaryLanguage { name }
            }
          }
        }
      }
    }
    """
    data = _graphql(s, query, {"login": username})
    nodes = (
        data.get("data", {})
        .get("user", {})
        .get("pinnedItems", {})
        .get("nodes", [])
    )
    return [
        GitHubRepo(
            name=n["name"],
            description=n.get("description"),
            stars=n.get("stargazerCount", 0),
            url=n["url"],
            primary_language=(n.get("primaryLanguage") or {}).get("name"),
        )
        for n in (nodes or [])
        if n and "name" in n
    ]


def _fetch_contributions(s: requests.Session, username: str) -> int:
    now = datetime.now(timezone.utc)
    from_dt = (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = """
    query($login: String!, $from: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from) {
          contributionCalendar {
            totalContributions
          }
        }
      }
    }
    """
    data = _graphql(s, query, {"login": username, "from": from_dt})
    return (
        data.get("data", {})
        .get("user", {})
        .get("contributionsCollection", {})
        .get("contributionCalendar", {})
        .get("totalContributions", 0)
    )


def _fetch_language_stats(
    s: requests.Session, repos: list[dict]
) -> list[LanguageStats]:
    """
    Aggregate language stats across all repos.
    repo_count: number of repos whose primary language is X (from repo metadata, no extra call).
    bytes: total bytes written in X across all repos (requires one call per repo).
    """
    repo_count: dict[str, int] = defaultdict(int)
    byte_count: dict[str, int] = defaultdict(int)

    for repo in repos:
        lang = repo.get("language")
        if lang:
            repo_count[lang] += 1

        try:
            lang_bytes: dict = _get(s, f"{_API}/repos/{repo['full_name']}/languages")
            for name, b in lang_bytes.items():
                byte_count[name] += b
        except (requests.HTTPError, KeyError):
            pass

    all_langs = set(repo_count) | set(byte_count)
    stats = [
        LanguageStats(
            name=lang,
            repo_count=repo_count.get(lang, 0),
            bytes=byte_count.get(lang, 0),
        )
        for lang in all_langs
    ]
    stats.sort(key=lambda x: (x.bytes, x.repo_count), reverse=True)
    return stats


def _fetch_readme(s: requests.Session, full_name: str) -> Optional[str]:
    data = _get(s, f"{_API}/repos/{full_name}/readme", allow_404=True)
    if not data:
        return None
    # GitHub returns base64-encoded content with embedded newlines.
    encoded = data.get("content", "").replace("\n", "")
    if not encoded:
        return None
    return base64.b64decode(encoded).decode("utf-8", errors="replace")


def scrape_github(username: str) -> GitHubProfile:
    """
    Scrape a GitHub profile and return a GitHubProfile.

    Fetches: profile metadata, all public repos, top languages by repo count
    and bytes, pinned repos (GraphQL), 90-day contribution calendar (GraphQL),
    and the README of the most-starred repo.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("[github] GITHUB_TOKEN is not set")
        raise ValueError("GITHUB_TOKEN environment variable not set")

    logger.info("[github] Scraping: %s", username)
    s = _session(token)

    user: dict = _get(s, f"{_API}/users/{username}")
    logger.info("[github] User fetched: %s (name=%r, public_repos=%s)", username, user.get("name"), user.get("public_repos"))

    repos = _paginate(
        s, f"{_API}/users/{username}/repos", {"type": "owner", "sort": "pushed"}
    )

    # Exclude forks: language bytes and most-starred should reflect the
    # candidate's own code, not code from upstream projects they forked.
    own_repos = [r for r in repos if not r.get("fork")]
    logger.info("[github] Repos: total=%d own=%d", len(repos), len(own_repos))

    most_starred_raw = max(
        own_repos, key=lambda r: r.get("stargazers_count", 0), default=None
    )
    most_starred_obj: Optional[GitHubRepo] = None
    readme: Optional[str] = None
    if most_starred_raw:
        most_starred_obj = GitHubRepo(
            name=most_starred_raw["name"],
            description=most_starred_raw.get("description"),
            stars=most_starred_raw.get("stargazers_count", 0),
            url=most_starred_raw["html_url"],
            primary_language=most_starred_raw.get("language"),
        )
        logger.info("[github] Most starred repo: %s (%d stars)", most_starred_raw["name"], most_starred_raw.get("stargazers_count", 0))
        readme = _fetch_readme(s, most_starred_raw["full_name"])

    top_langs = _fetch_language_stats(s, own_repos)
    logger.info("[github] Top languages: %s", [l.name for l in top_langs[:5]])

    try:
        pinned = _fetch_pinned_repos(s, username)
        logger.info("[github] Pinned repos: %d", len(pinned))
    except Exception as exc:
        logger.warning("[github] Pinned repos failed: %s", exc)
        pinned = []

    try:
        total_contributions = _fetch_contributions(s, username)
        logger.info("[github] Contributions (90d): %d", total_contributions)
    except Exception as exc:
        logger.warning("[github] Contributions failed: %s", exc)
        total_contributions = 0

    return GitHubProfile(
        username=username,
        name=user.get("name"),
        bio=user.get("bio"),
        location=user.get("location"),
        company=user.get("company"),
        email=user.get("email"),
        avatar_url=user.get("avatar_url"),
        blog=user.get("blog") or None,
        public_repos=user.get("public_repos", 0),
        followers=user.get("followers", 0),
        following=user.get("following", 0),
        created_at=user.get("created_at"),
        top_languages=top_langs,
        pinned_repos=pinned,
        total_contributions_90d=total_contributions,
        most_starred_repo=most_starred_obj,
        most_starred_repo_readme=readme,
    )


if __name__ == "__main__":
    import json
    import sys

    username = sys.argv[1] if len(sys.argv) > 1 else "torvalds"
    profile = scrape_github(username)
    print(json.dumps(profile.model_dump(), indent=2))
