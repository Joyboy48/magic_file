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

        # ── Immediately send a snapshot of the current DB state ──────────────
        # This fixes the race where the worker finishes (or advances) before
        # the frontend opens the SSE connection, causing the UI to stay at 0%.
        job_snap = db.get(Job, UUID(job_id))
        if job_snap:
            snapshot = {
                "type": "job_snapshot",
                "job_id": job_id,
                "stage": job_snap.stage,
                "progress_percent": job_snap.progress_percent,
                "status": job_snap.status,
                "error_message": job_snap.error_message,
                "timestamp_utc": job_snap.updated_at.isoformat() if job_snap.updated_at else None,
                "payload": {},
            }
            yield f"event: job_snapshot\n"
            yield f"data: {json.dumps(snapshot)}\n\n"

            # If already terminal, close immediately — no need to subscribe.
            if job_snap.status in ("completed", "failed"):
                return

        done = False
        while not done:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not msg:
                # Also stop if DB says the job has reached a terminal state.
                db.expire_all()  # refresh session cache
                job = db.get(Job, UUID(job_id))
                if job and job.status in ("completed", "failed"):
                    # Emit a final synthetic event so the frontend updates.
                    final_type = "job_completed" if job.status == "completed" else "job_failed"
                    final_ev = {
                        "type": final_type,
                        "job_id": job_id,
                        "stage": job.stage,
                        "progress_percent": job.progress_percent,
                        "status": job.status,
                        "error_message": job.error_message,
                        "timestamp_utc": job.updated_at.isoformat() if job.updated_at else None,
                        "payload": {},
                    }
                    yield f"event: {final_type}\n"
                    yield f"data: {json.dumps(final_ev)}\n\n"
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

