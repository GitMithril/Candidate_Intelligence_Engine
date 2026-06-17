import json
import os
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

_SYSTEM_PROMPT = """You are a recruitment assistant for a Candidate Intelligence System.
Help recruiters evaluate and compare candidates by answering questions grounded strictly in the profiles below.

Rules:
- Answer ONLY from the candidate profiles provided. Never use external knowledge about individuals.
- Always name the specific candidate(s) you are referring to.
- Cite real data: skills, job titles, companies, durations, schools directly from the profiles.
- When comparing candidates, format the comparison as a markdown table with candidates as rows and key attributes (Name, Role, Top Skills, Education, Location) as columns.
- When comparing candidates, base every claim on profile data.
- If no profile contains the answer, say so clearly — do not guess or hallucinate.
- If the question is unrelated to candidates or recruiting, politely clarify you can only assist with candidate evaluation.
- Include the candidate's GitHub or LinkedIn URL when available, so the recruiter can verify."""

_CLASSIFY_PROMPT = """You are a query classifier for a recruitment chatbot.

Return ONLY valid JSON (no markdown, no explanation). Choose one of these three schemas:

{"type": "irrelevant"}
{"type": "semantic", "top_k": <number>}
{"type": "filter", "criteria": {"location": "<city/country or null>", "skills": ["<exact technology>"], "school": "<university or null>"}}

Rules:
- "irrelevant": question unrelated to candidates or recruiting (greetings, math, general knowledge).
- "semantic": use for role or concept searches — backend engineers, full stack devs, data scientists, etc. The embedding model understands these concepts better than text matching.
  - top_k 10 → targeted ("find a senior React developer", "who is best at system design?")
  - top_k 30 → broad ("compare all backend engineers", "list all frontend devs", "show me all ML engineers")
- "filter": use ONLY when the query contains concrete, enumerable values — a specific city/country, a named university, or specific named technologies/tools.
  - skills must be specific technology names (Python, React, Node.js) — NOT role labels (backend, frontend, full-stack, engineer). Role labels belong in semantic.
  - Do NOT put role/concept words in filter criteria. The LLM will infer roles from the returned profiles.

Examples:
  "compare all backend engineers" → {"type": "semantic", "top_k": 30}
  "who knows React?" → {"type": "semantic", "top_k": 10}
  "list all applicants from Islamabad" → {"type": "filter", "criteria": {"location": "Islamabad", "skills": [], "school": null}}
  "how many NUST graduates know Python?" → {"type": "filter", "criteria": {"location": null, "skills": ["Python"], "school": "NUST"}}
  "hello" → {"type": "irrelevant"}"""


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        model="google/gemma-4-31b-it:free",
        temperature=0.2,
    )


def classify_query(question: str) -> dict:
    """Classify query type and extract retrieval parameters.

    Returns one of:
      {"type": "irrelevant"}
      {"type": "semantic", "top_k": int}
      {"type": "filter", "criteria": {"location": str|None, "skills": list, "school": str|None}}
    Defaults to {"type": "semantic", "top_k": 10} on any failure.
    """
    llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        model="google/gemma-4-31b-it:free",
        temperature=0,
    )
    try:
        raw = llm.invoke([
            SystemMessage(content=_CLASSIFY_PROMPT),
            HumanMessage(content=question),
        ]).content
        text = re.sub(r"```(?:json)?\s*|\s*```", "", raw).strip()
        result = json.loads(text)
        if result.get("type") not in ("irrelevant", "semantic", "filter"):
            return {"type": "semantic", "top_k": 10}
        if result["type"] == "semantic" and "top_k" not in result:
            result["top_k"] = 10
        return result
    except Exception:
        return {"type": "semantic", "top_k": 10}


def profile_to_text(doc: dict, rank: int) -> str:
    lines = [f"[Candidate {rank}]"]

    for field, label in [("name", "Name"), ("headline", "Headline"), ("current_role", "Role"), ("current_company", "Company"), ("location", "Location")]:
        if doc.get(field):
            lines.append(f"{label}: {doc[field]}")

    if doc.get("skills"):
        lines.append(f"Skills: {', '.join(doc['skills'])}")

    exp = doc.get("experience") or []
    if exp:
        exp_lines = []
        for e in exp[:3]:
            title = e.get("title") or ""
            company = e.get("company") or ""
            duration = e.get("duration") or ""
            description = e.get("description") or ""
            entry = f"  - {title} at {company}"
            if duration:
                entry += f" ({duration})"
            if description:
                entry += f": {description[:120]}"
            exp_lines.append(entry.strip())
        lines.append("Experience:\n" + "\n".join(exp_lines))

    edu = doc.get("education") or []
    if edu:
        edu_lines = []
        for e in edu[:2]:
            parts = [p for p in [e.get("degree"), e.get("field"), e.get("school"), e.get("dates")] if p]
            if parts:
                edu_lines.append(f"  - {' | '.join(parts)}")
        if edu_lines:
            lines.append("Education:\n" + "\n".join(edu_lines))

    if doc.get("github_username"):
        lines.append(f"GitHub: https://github.com/{doc['github_username']}")

    urls = doc.get("source_urls") or {}
    if urls.get("linkedin"):
        lines.append(f"LinkedIn: {urls['linkedin']}")

    return "\n".join(lines)


def build_messages(question: str, history: list[dict], candidates: list[dict]) -> list:
    """Build the LangChain message list for a chat turn."""
    if candidates:
        context = "\n\n---\n\n".join(profile_to_text(doc, i + 1) for i, doc in enumerate(candidates))
    else:
        context = "No candidate profiles are available for this query."

    messages: list = [
        SystemMessage(content=f"{_SYSTEM_PROMPT}\n\nCANDIDATE PROFILES:\n{context}"),
    ]
    for msg in history[-10:]:
        if msg["role"] == "human":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=question))
    return messages


def answer_question(question: str, history: list[dict], candidates: list[dict]) -> str:
    """Call the LLM with retrieved candidate context and conversation history.

    Raises on LLM errors — callers decide how to handle.
    """
    return get_llm().invoke(build_messages(question, history, candidates)).content
