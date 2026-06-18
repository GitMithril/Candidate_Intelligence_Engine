"""
Firebase ID token verification for FastAPI.

Expects the client to send:  Authorization: Bearer <firebase-id-token>

Initialization priority:
  1. FIREBASE_SERVICE_ACCOUNT_JSON — JSON string (use on Railway / production)
  2. FIREBASE_SERVICE_ACCOUNT_PATH — local file path (use for local development)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

_firebase_initialized = False


def _init_firebase() -> None:
    global _firebase_initialized
    if _firebase_initialized:
        return

    import firebase_admin
    from firebase_admin import credentials

    service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")

    if service_account_json:
        cred = credentials.Certificate(json.loads(service_account_json))
        logger.info("[auth] Firebase initialized with service account JSON")
    elif service_account_path:
        cred = credentials.Certificate(service_account_path)
        logger.info("[auth] Firebase initialized with service account file: %s", service_account_path)
    else:
        raise RuntimeError(
            "Firebase credentials not configured. "
            "Set FIREBASE_SERVICE_ACCOUNT_PATH (local dev) or "
            "FIREBASE_SERVICE_ACCOUNT_JSON (Railway) in your .env."
        )

    firebase_admin.initialize_app(cred)
    _firebase_initialized = True


async def get_current_user(authorization: Optional[str] = Header(None)) -> str:
    """FastAPI dependency — verify Firebase ID token and return the Firebase uid."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required.")

    token = authorization.removeprefix("Bearer ").strip()
    _init_firebase()

    from firebase_admin import auth
    try:
        decoded = auth.verify_id_token(token)
        return decoded["uid"]
    except Exception as exc:
        logger.warning("[auth] Token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
