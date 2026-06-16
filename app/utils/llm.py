import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..schemas import ResumeExtraction

_SYSTEM_PROMPT = """Extract information from the resume below and output ONLY a valid JSON object.

Use this exact structure (null for any missing field):
{
  "name": "Full Name",
  "email": "email@example.com",
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
- linkedin_url: full URL (https://linkedin.com/in/...) or null
- github_username: the plain username only, never the full URL
- experience[].company: the actual company/organisation name, not a handle or URL
- Scan the ENTIRE document including the bottom — education is often at the end
- Output ONLY the JSON object. No markdown fences. No explanation."""

_MAX_CHARS = 15000


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
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
