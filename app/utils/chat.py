import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

_SYSTEM_PROMPT = """You are a recruitment assistant for a Candidate Intelligence System.
Help recruiters evaluate and compare candidates by answering questions grounded strictly in the profiles below.

Rules:
- Answer ONLY from the candidate profiles provided. Never use external knowledge about individuals.
- Always name the specific candidate(s) you are referring to.
- Cite real data: skills, job titles, companies, durations, schools directly from the profiles.
- When comparing candidates, base every claim on profile data.
- If no profile contains the answer, say so clearly — do not guess or hallucinate.
- Include the candidate's GitHub or LinkedIn URL when available, so the recruiter can verify."""


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        model="google/gemma-4-31b-it:free",
        temperature=0.2,
    )


def profile_to_text(doc: dict, rank: int) -> str:
    lines = [f"[Candidate {rank}]"]

    for field, label in [("name", "Name"), ("headline", "Headline"), ("current_role", "Role"), ("current_company", "Company"), ("location", "Location")]:
        if doc.get(field):
            lines.append(f"{label}: {doc[field]}")

    if doc.get("skills"):
        lines.append(f"Skills: {', '.join(doc['skills'][:15])}")

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


def answer_question(question: str, history: list[dict], candidates: list[dict]) -> str:
    """Call the LLM with retrieved candidate context and conversation history.

    Raises on LLM errors — callers decide how to handle.
    """
    if candidates:
        context = "\n\n---\n\n".join(profile_to_text(doc, i + 1) for i, doc in enumerate(candidates))
    else:
        context = "No candidate profiles were retrieved for this query."

    messages: list = [
        SystemMessage(content=f"{_SYSTEM_PROMPT}\n\nCANDIDATE PROFILES:\n{context}"),
    ]
    for msg in history[-10:]:
        if msg["role"] == "human":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=question))

    return _get_llm().invoke(messages).content
