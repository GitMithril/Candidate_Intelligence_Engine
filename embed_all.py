"""
Batch-embed all profiles currently in MongoDB and upsert their vectors to Pinecone.

Run from the project root:
    python embed_all.py
"""
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient

from app.embeddings import embed_and_store

load_dotenv()


def main():
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/candidate_intelligence")
    client = MongoClient(uri)
    db = client["candidate_intelligence"]

    profiles = list(db.profiles.find({}))
    total = len(profiles)
    print(f"Found {total} profile(s) in MongoDB")

    ok = 0
    for i, doc in enumerate(profiles, 1):
        pid = str(doc["_id"])
        name = doc.get("name") or "unknown"
        try:
            embed_and_store(pid, doc)
            print(f"[{i}/{total}] OK  {pid}  ({name})")
            ok += 1
        except Exception as e:
            print(f"[{i}/{total}] ERR {pid}  ({name}): {e}", file=sys.stderr)

    print(f"\nDone — {ok}/{total} embedded successfully.")


if __name__ == "__main__":
    main()
