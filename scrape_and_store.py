"""
Scrape GitHub and/or LinkedIn for a candidate and POST the combined profile
to the Candidate Intelligence API.

Usage:
    python scrape_and_store.py --github torvalds
    python scrape_and_store.py --linkedin https://linkedin.com/in/williamhgates
    python scrape_and_store.py --github torvalds --linkedin https://linkedin.com/in/williamhgates
"""
import argparse
import os
import sys

import requests
from dotenv import load_dotenv

from app.scrapers.github import scrape_github
from app.scrapers.linkedin import scrape_linkedin

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Scrape and store a candidate profile.")
    parser.add_argument("--github", metavar="USERNAME", help="GitHub username")
    parser.add_argument("--linkedin", metavar="URL", help="LinkedIn profile URL")
    parser.add_argument(
        "--api",
        default=os.environ.get("API_URL", "http://localhost:8000"),
        help="API base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    if not args.github and not args.linkedin:
        parser.error("Provide at least one of --github or --linkedin")

    body = {}

    if args.github:
        print(f"Scraping GitHub: {args.github} ...")
        try:
            gh = scrape_github(args.github)
            body["github_username"] = args.github
            body["github_profile"] = gh.model_dump()
            print(f"  Done — {gh.public_repos} repos, {gh.total_contributions_90d} contributions (90d)")
        except Exception as e:
            print(f"  GitHub scrape failed: {e}", file=sys.stderr)

    if args.linkedin:
        print(f"Scraping LinkedIn: {args.linkedin} ...")
        li = scrape_linkedin(args.linkedin)
        body["linkedin_url"] = args.linkedin
        body["linkedin_profile"] = li.model_dump()
        if li.warning:
            print(f"  Warning: {li.warning}", file=sys.stderr)
        else:
            print(f"  Done — {li.name}, {len(li.skills)} skills")

    if not body:
        print("Both scrapers failed — nothing to store.", file=sys.stderr)
        sys.exit(1)

    print(f"POSTing to {args.api}/profiles ...")
    r = requests.post(f"{args.api}/profiles", json=body, timeout=60)

    if r.status_code == 201:
        doc = r.json()
        profile_id = doc["id"]
        print(f"Stored — id: {profile_id}, name: {doc.get('name')}")
    else:
        print(f"API error {r.status_code}: {r.text}", file=sys.stderr)
        sys.exit(1)

    print(f"Embedding profile {profile_id} in Pinecone ...")
    re = requests.post(f"{args.api}/profiles/{profile_id}/embed", timeout=60)
    if re.status_code == 200:
        print("Embedded.")
    else:
        print(f"Embed error {re.status_code}: {re.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
