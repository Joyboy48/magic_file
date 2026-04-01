from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path


STOPWORDS = {
    "the",
    "and",
    "or",
    "a",
    "an",
    "to",
    "of",
    "in",
    "for",
    "on",
    "with",
    "is",
    "are",
    "was",
    "were",
    "it",
    "this",
    "that",
    "as",
    "at",
    "by",
    "from",
    "be",
    "we",
    "you",
    "your",
    "our",
    "their",
    "will",
    "can",
    "may",
}


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z]{3,}", text.lower())
    return [w for w in words if w not in STOPWORDS]


def pick_category(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["invoice", "payment", "bank", "balance", "contract"]):
        return "finance"
    if any(k in t for k in ["health", "patient", "doctor", "clinic", "hospital"]):
        return "health"
    if any(k in t for k in ["code", "software", "api", "frontend", "backend", "celery"]):
        return "technology"
    if any(k in t for k in ["travel", "flight", "hotel", "itinerary"]):
        return "travel"
    return "general"


def extract_from_text(*, filename: str, file_type: str | None, size_bytes: int, text: str) -> dict:
    base_title = Path(filename).stem or "Untitled"
    tokens = _tokenize(text)
    kw = [w for w, _ in Counter(tokens).most_common(10)]

    summary = " ".join(text.split())[:400]
    if not summary:
        summary = f"No readable text detected in {filename}. Using mock summary."

    category = pick_category(text)
    return {
        "title": base_title,
        "category": category,
        "summary": summary,
        "keywords": kw[:8],
        "status": "completed",
        "source": {
            "filename": filename,
            "mime_type": file_type,
            "size_bytes": size_bytes,
        },
    }


def read_text_preview(path: str, *, max_bytes: int = 200_000) -> str:
    # Best-effort decode. If it fails, we treat the content as non-text.
    with open(path, "rb") as f:
        raw = f.read(max_bytes)
    try:
        return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def should_fail(filename: str) -> bool:
    # Deterministic failure trigger for demonstrating retries.
    return "fail" in (filename or "").lower()

