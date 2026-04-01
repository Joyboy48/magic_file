from __future__ import annotations

import json
from datetime import datetime, timezone

import redis

from app.core.config import settings


def job_progress_channel(job_id: str) -> str:
    return f"job_progress:{job_id}"


def publish_job_event(
    *,
    job_id: str,
    event_type: str,
    stage: str | None = None,
    progress_percent: int | None = None,
    payload: dict | None = None,
) -> None:
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    channel = job_progress_channel(job_id)
    message = {
        "type": event_type,
        "job_id": job_id,
        "stage": stage,
        "progress_percent": progress_percent,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "payload": payload or {},
    }
    # Fire-and-forget: Pub/Sub messages are best-effort for real-time UI.
    r.publish(channel, json.dumps(message))

