import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..schemas import ResumeExtraction
from .openrouter import get_next_openrouter_api_key

_SYSTEM_PROMPT = """Extract information from the resume below and output ONLY a valid JSON object.

Use this exact structure (null for any missing field):
{
  "name": "Full Name",
  "email": "email@example.com",
  "location": "City, Country",
  "linkedin_url": "https://linkedin.com/in/username",
  "github_username": "username_only_no_url",
  "skills": ["Python", "FastAPI", "..."],
  "experience": [
    {"title": "Job Title", "company": "Company Name", "duration": "Jan 2022 - Present", "location": "City", "description": "What they did"}
  ],
  "education": [
    {"school": "University Name", "degree": "BS", "field": "Computer Science", "dates": "2018-2022"}
  ]
}

Rules:
- All field values MUST be in English. If the resume contains text in any other language, translate it to English before including it in the JSON.
- location: extract the candidate's current city/country from the resume header or contact section (e.g. "Islamabad, Pakistan"). null if not found.
- linkedin_url: full URL (https://linkedin.com/in/...) or null. Check both visible text and the "Links found in document" section at the end.
- github_username: the plain username only, never the full URL. Check both visible text and the "Links found in document" section at the end.
- experience[].company: the actual company/organisation name, not a handle or URL
- Scan the ENTIRE document including the bottom — education is often at the end
- Output ONLY the JSON object. No markdown fences. No explanation."""

_MAX_CHARS = 15000


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=get_next_openrouter_api_key(),
        model="google/gemma-4-31b-it:free",
        temperature=0,
    )


def _extract_json(text: str) -> dict:
    # Strip markdown fences that some models add despite being told not to.
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return json.loads(text)


def parse_resume(text: str) -> ResumeExtraction:
    """Call the LLM to extract structured fields from raw resume text.

    Raises on LLM or JSON errors — callers decide whether to treat this as fatal.
    """
    llm = _get_llm()
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=text[:_MAX_CHARS]),
    ]
    response = llm.invoke(messages)
    data = _extract_json(response.content)
    return ResumeExtraction.model_validate(data)
