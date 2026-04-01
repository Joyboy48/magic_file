from __future__ import annotations

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models import Document, Job
from app.schemas import JobListItemOut, JobOut, JobStatus, UpdateReviewedRequest
from app.utils.redis_pubsub import publish_job_event
from app.worker.celery_app import celery_app


router = APIRouter(prefix="/api", tags=["jobs"])


def _job_to_out(job: Job, doc: Document | None = None) -> JobOut:
    # Document schema is intentionally lightweight.
    document_blob = None
    if doc is not None:
        document_blob = {
            "id": str(doc.id),
            "original_filename": doc.original_filename,
            "mime_type": doc.mime_type,
            "size_bytes": doc.size_bytes,
            "storage_path": doc.storage_path,
        }

    return JobOut(
        id=job.id,
        document_id=job.document_id,
        status=job.status,  # type: ignore[arg-type]
        attempt=job.attempt,
        stage=job.stage,
        progress_percent=job.progress_percent,
        extracted_json=job.extracted_json,
        reviewed_json=job.reviewed_json,
        final_json=job.final_json,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        finalized_at=job.finalized_at,
        celery_task_id=job.celery_task_id,
        document=document_blob,
    )


@router.get("/jobs", response_model=list[JobListItemOut])
async def list_jobs(
    q: str | None = Query(default=None, description="Search by filename/title/summary/keywords"),
    status: JobStatus | None = Query(default=None, description="Filter by processing status"),
    sort: Literal[
        "created_at_desc",
        "created_at_asc",
        "filename_asc",
        "filename_desc",
        "status_asc",
        "status_desc",
        "progress_desc",
        "progress_asc",
    ] = "created_at_desc",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Any:
    stmt = (
        select(Job, Document)
        .join(Document, Job.document_id == Document.id)
        .order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    if status is not None:
        stmt = stmt.where(Job.status == status)

    if q:
        q_like = f"%{q}%"
        # Search in document filename and in JSON fields (best-effort with casting).
        stmt = stmt.where(
            or_(
                Document.original_filename.ilike(q_like),
                cast(Job.extracted_json, String).ilike(q_like),
                cast(Job.reviewed_json, String).ilike(q_like),
                cast(Job.final_json, String).ilike(q_like),
            )
        )

    # Apply sort on top.
    if sort == "created_at_desc":
        stmt = stmt.order_by(Job.created_at.desc())
    elif sort == "created_at_asc":
        stmt = stmt.order_by(Job.created_at.asc())
    elif sort == "filename_asc":
        stmt = stmt.order_by(Document.original_filename.asc())
    elif sort == "filename_desc":
        stmt = stmt.order_by(Document.original_filename.desc())
    elif sort == "status_asc":
        stmt = stmt.order_by(Job.status.asc())
    elif sort == "status_desc":
        stmt = stmt.order_by(Job.status.desc())
    elif sort == "progress_desc":
        stmt = stmt.order_by(Job.progress_percent.desc())
    elif sort == "progress_asc":
        stmt = stmt.order_by(Job.progress_percent.asc())

    rows = db.execute(stmt).all()
    out: list[JobListItemOut] = []
    for job, doc in rows:
        out.append(
            JobListItemOut(
                job=_job_to_out(job, doc),
                filename=doc.original_filename,
                size_bytes=doc.size_bytes,
                mime_type=doc.mime_type,
                created_at=job.created_at,
            )
        )
    return out


@router.get("/jobs/{job_id}", response_model=JobOut)
async def job_detail(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Any:
    stmt = select(Job, Document).join(Document, Job.document_id == Document.id).where(Job.id == job_id)
    row = db.execute(stmt).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    job, doc = row
    return _job_to_out(job, doc)


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
async def retry_failed_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Any:
    stmt = select(Job).where(Job.id == job_id)
    job = db.execute(stmt).scalars().one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried.")

    # Reset job state and enqueue again.
    job.status = "queued"
    job.stage = "job_queued"
    job.progress_percent = 0
    job.error_message = None
    job.attempt = (job.attempt or 1) + 1

    job.started_at = None
    job.completed_at = None
    job.finalized_at = None

    # Clear outputs to keep retry consistent.
    job.extracted_json = None
    job.reviewed_json = None
    job.final_json = None

    # Commit state reset before enqueue to avoid race with worker reads.
    db.commit()
    publish_job_event(job_id=str(job.id), event_type="job_queued", stage="job_queued", progress_percent=0)

    async_result = celery_app.send_task("app.worker.tasks.process_job", args=[str(job.id)])
    job.celery_task_id = async_result.id
    db.commit()

    # Load related document for schema convenience.
    doc = db.execute(select(Document).where(Document.id == job.document_id)).scalars().one()
    return _job_to_out(job, doc)


@router.patch("/jobs/{job_id}/reviewed", response_model=JobOut)
async def update_reviewed(job_id: uuid.UUID, req: UpdateReviewedRequest, db: Session = Depends(get_db)) -> Any:
    job = db.execute(select(Job).where(Job.id == job_id)).scalars().one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Only completed jobs can be reviewed.")
    if job.extracted_json is None:
        raise HTTPException(status_code=400, detail="No extracted output available yet.")

    job.reviewed_json = req.reviewed_json
    job.finalized_at = None  # invalidate previous finalization if any
    job.final_json = None
    db.commit()

    doc = db.execute(select(Document).where(Document.id == job.document_id)).scalars().one()
    return _job_to_out(job, doc)


@router.post("/jobs/{job_id}/finalize", response_model=JobOut)
async def finalize_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> Any:
    job = db.execute(select(Job).where(Job.id == job_id)).scalars().one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job must be completed before finalization.")

    if job.reviewed_json is None:
        if job.extracted_json is None:
            raise HTTPException(status_code=400, detail="Nothing to finalize.")
        job.reviewed_json = job.extracted_json

    job.final_json = job.reviewed_json
    job.finalized_at = datetime.now(timezone.utc)

    db.commit()
    doc = db.execute(select(Document).where(Document.id == job.document_id)).scalars().one()
    return _job_to_out(job, doc)


def _export_job_payload(job: Job, doc: Document) -> dict[str, Any]:
    if job.final_json is None:
        raise HTTPException(status_code=400, detail="Job is not finalized yet.")
    return {
        "document": {
            "id": str(doc.id),
            "filename": doc.original_filename,
            "mime_type": doc.mime_type,
            "size_bytes": doc.size_bytes,
        },
        "job": {
            "id": str(job.id),
            "status": job.status,
            "attempt": job.attempt,
            "stage": job.stage,
            "finalized_at": job.finalized_at.isoformat() if job.finalized_at else None,
        },
        "result": job.final_json,
    }


@router.get("/jobs/{job_id}/export")
async def export_job(
    job_id: uuid.UUID,
    format: Literal["json", "csv"] = Query(default="json"),
    db: Session = Depends(get_db),
) -> Any:
    stmt = select(Job, Document).join(Document, Job.document_id == Document.id).where(Job.id == job_id)
    row = db.execute(stmt).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    job, doc = row

    payload = _export_job_payload(job, doc)

    if format == "json":
        return JSONResponse(payload)

    if format == "csv":
        # Flatten common fields from our extraction schema.
        result = payload["result"] or {}
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["job_id", "document_id", "filename", "title", "category", "summary", "keywords", "status"])
        writer.writerow(
            [
                str(job.id),
                str(doc.id),
                doc.original_filename,
                result.get("title"),
                result.get("category"),
                result.get("summary"),
                ";".join(result.get("keywords") or []),
                result.get("status") or job.status,
            ]
        )
        csv_bytes = output.getvalue().encode("utf-8")
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="job_{job_id}.csv"'},
        )

    raise HTTPException(status_code=400, detail="Unsupported export format.")

