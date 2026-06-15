"""
Embedding utilities for candidate profiles.

Builds a descriptive text string from a CandidateProfile document, encodes it
with sentence-transformers/all-MiniLM-L6-v2 (384 dims, cosine metric), and
upserts the resulting vector into Pinecone keyed by the MongoDB _id string.

Model and Pinecone index are lazy-loaded on first use so the API boots fast.
"""
from __future__ import annotations

import os
from typing import Any

from bson import ObjectId
from dotenv import load_dotenv
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

load_dotenv()

_model: SentenceTransformer | None = None
_index = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _get_index():
    global _index
    if _index is None:
        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        _index = pc.Index(os.environ.get("PINECONE_INDEX", "candidate-intelligence"))
    return _index


def build_text(doc: dict[str, Any]) -> str:
    """
    Concatenate key profile fields into a single string for embedding.
    Fields used (in order): headline, bio, skills, experience titles, top languages.
    """
    parts: list[str] = []

    if doc.get("headline"):
        parts.append(doc["headline"])
    if doc.get("github_bio"):
        parts.append(doc["github_bio"])

    skills = [s for s in (doc.get("skills") or []) if s]
    if skills:
        parts.append("Skills: " + ", ".join(skills))

    exp_titles = [e["title"] for e in (doc.get("experience") or []) if e.get("title")]
    if exp_titles:
        parts.append("Experience: " + ", ".join(exp_titles))

    langs = [l["name"] for l in (doc.get("top_languages") or []) if l.get("name")]
    if langs:
        parts.append("Languages: " + ", ".join(langs))

    return " | ".join(parts)


def embed_and_store(profile_id: str, doc: dict[str, Any]) -> list[float]:
    """Embed a profile document and upsert the vector to Pinecone."""
    text = build_text(doc)
    vector: list[float] = _get_model().encode(text).tolist()

    metadata: dict[str, Any] = {}
    for key in ("name", "headline", "location"):
        if doc.get(key):
            metadata[key] = doc[key]
    skills = doc.get("skills") or []
    if skills:
        metadata["skills"] = skills[:20]

    _get_index().upsert(vectors=[{"id": profile_id, "values": vector, "metadata": metadata}])
    return vector


def embed_profile_by_id(profile_id: str, db) -> list[float]:
    """Fetch a profile from MongoDB by string id, embed it, and store in Pinecone."""
    doc = db.profiles.find_one({"_id": ObjectId(profile_id)})
    if doc is None:
        raise ValueError(f"Profile {profile_id} not found")
    return embed_and_store(profile_id, doc)
