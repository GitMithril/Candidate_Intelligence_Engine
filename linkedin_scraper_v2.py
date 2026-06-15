
"""
LinkedIn profile scraper using the *new* Playwright-based linkedin-scraper v3+.

Requires:
$ pip install "linkedin-scraper>=3.0.0" playwright
$ playwright install chromium
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

from linkedin_scraper import (
    BrowserManager, 
    PersonScraper,
    AuthenticationError, 
    RateLimitError, 
    ProfileNotFoundError
)
from schemas import EducationEntry, ExperienceEntry, LinkedInProfile

load_dotenv()

async def _scrape_linkedin_v2(profile_url: str, li_at: str) -> LinkedInProfile:
    async with BrowserManager(headless=False) as browser:
        # Inject the li_at cookie directly into the Page context
        await browser.page.context.add_cookies([
            {
                "name": "li_at",
                "value": li_at,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }
        ])

        scraper = PersonScraper(browser.page)
        field_warnings = []

        try:
            person = await scraper.scrape(profile_url)
        except AuthenticationError:
            return LinkedInProfile(warning="linkedin-scraper: Authentication failed or cookie expired.")
        except RateLimitError:
            return LinkedInProfile(warning="linkedin-scraper: Rate limited by LinkedIn.")
        except ProfileNotFoundError:
            return LinkedInProfile(warning="linkedin-scraper: Profile not found or private.")
        except Exception as e:
            return LinkedInProfile(warning=f"linkedin-scraper failed: {e}")

        # Map the returned Pydantic Person object to our expected LinkedInProfile schema
        experiences = []
        for exp in (person.experiences or []):
            try:
                title = getattr(exp, "title", None)
                company = getattr(exp, "company", None)
                location_val = getattr(exp, "location", None)
                desc = getattr(exp, "description", None)
                
                duration = None
                from_date = getattr(exp, "from_date", None)
                to_date = getattr(exp, "to_date", None)
                if from_date:
                    duration = f"{from_date} - {to_date or ''}".strip(" -")

                experiences.append(ExperienceEntry(
                    title=title,
                    company=company,
                    duration=duration,
                    location=location_val,
                    description=desc,
                ))
            except Exception as e:
                field_warnings.append(f"experience mapping error: {e}")

        educations = []
        for edu in (person.educations or []):
            try:
                school = getattr(edu, "institution_name", getattr(edu, "school", None))
                degree = getattr(edu, "degree", None)
                field = getattr(edu, "field_of_study", None)
                
                dates = None
                from_date = getattr(edu, "from_date", None)
                to_date = getattr(edu, "to_date", None)
                if from_date:
                    dates = f"{from_date} - {to_date or ''}".strip(" -")

                educations.append(EducationEntry(
                    school=school,
                    degree=degree,
                    field=field,
                    dates=dates
                ))
            except Exception as e:
                field_warnings.append(f"education mapping error: {e}")

        skills_list = []
        for skill in (person.skills or []):
            if isinstance(skill, str):
                skills_list.append(skill)
            elif hasattr(skill, "name"):
                skills_list.append(skill.name)

        current_role = experiences[0].title if experiences else None
        current_company = experiences[0].company if experiences else None

        return LinkedInProfile(
            name=person.name,
            headline=person.headline or person.about,
            current_role=current_role,
            current_company=current_company,
            location=person.location,
            experience=experiences,
            education=educations,
            skills=skills_list,
            warning="; ".join(field_warnings) if field_warnings else None,
        )

def scrape_linkedin_v2(profile_url: str) -> LinkedInProfile:
    li_at = os.environ.get("LINKEDIN_LI_AT")
    if not li_at:
        return LinkedInProfile(warning="LINKEDIN_LI_AT environment variable not set")
    return asyncio.run(_scrape_linkedin_v2(profile_url, li_at))

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.linkedin.com/in/williamhgates"
    profile = scrape_linkedin_v2(url)
    print(json.dumps(profile.model_dump(), indent=2))