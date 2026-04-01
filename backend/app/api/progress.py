from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator
from uuid import UUID

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models import Job
from app.utils.redis_pubsub import job_progress_channel


router = APIRouter(prefix="/api", tags=["progress"])


async def _sse_event_stream(*, job_id: str, db: Session) -> AsyncGenerator[str, None]:
    redis = redis_async.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    channel = job_progress_channel(job_id)

    await pubsub.subscribe(channel)

    try:
        # Basic keep-alive so browsers open the stream reliably.
        yield ": connected\n\n"

        done = False
        while not done:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not msg:
                # Also stop if DB says the job has reached a terminal state.
                job = db.get(Job, UUID(job_id))
                if job and job.status in ("completed", "failed"):
                    break
                continue

            raw = msg.get("data")
            if raw is None:
                continue

            # We publish JSON strings.
            try:
                parsed = json.loads(raw)
                event_type = parsed.get("type", "progress")
            except Exception:
                event_type = "progress"
                parsed = {"raw": raw}

            # SSE format: `event:` optional, `data:` must be present.
            yield f"event: {event_type}\n"
            yield f"data: {json.dumps(parsed)}\n\n"

            if isinstance(parsed, dict) and parsed.get("type") in ("job_completed", "job_failed"):
                done = True
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass
        await pubsub.close()
        await redis.close()


@router.get("/jobs/{job_id}/events")
async def stream_job_progress(job_id: UUID, db: Session = Depends(get_db)) -> StreamingResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    generator = _sse_event_stream(job_id=str(job_id), db=db)
    return StreamingResponse(generator, media_type="text/event-stream")

