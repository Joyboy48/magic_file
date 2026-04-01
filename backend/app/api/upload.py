from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models import Document, Job
from app.schemas import JobListItemOut, JobOut, UploadResponse
from app.services.storage import save_upload_to_disk
from app.utils.redis_pubsub import publish_job_event
from app.worker.celery_app import celery_app


router = APIRouter(prefix="/api", tags=["upload"])


def _job_list_item(job: Job, filename: str) -> JobListItemOut:
    # The Pydantic schema allows an optional lightweight document info blob.
    return JobListItemOut(
        job=job,
        filename=filename,
        size_bytes=job.document.size_bytes if job.document else 0,
        mime_type=job.document.mime_type if job.document else None,
        created_at=job.created_at,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> Any:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    jobs_out: list[JobListItemOut] = []
    jobs_to_enqueue: list[Job] = []
    docs_by_job_id: dict[str, Document] = {}

    for f in files:
        if not f.filename:
            raise HTTPException(status_code=400, detail="Every uploaded file must have a filename.")

        document_id = uuid.uuid4()
        try:
            storage_path, size_bytes, mime_type = await save_upload_to_disk(
                f, upload_dir=settings.upload_dir, document_id=document_id
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to save upload: {e}") from e

        doc = Document(
            id=document_id,
            original_filename=f.filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            storage_path=storage_path,
        )
        db.add(doc)

        job = Job(
            document_id=document_id,
            status="queued",
            attempt=1,
            stage="job_queued",
            progress_percent=0,
        )
        db.add(job)
        db.flush()  # assign job.id

        jobs_to_enqueue.append(job)
        docs_by_job_id[str(job.id)] = doc

    # Commit first so worker can always read the job row.
    db.commit()

    for job in jobs_to_enqueue:
        publish_job_event(job_id=str(job.id), event_type="job_queued", stage="job_queued", progress_percent=0)
        async_result = celery_app.send_task("app.worker.tasks.process_job", args=[str(job.id)])
        job.celery_task_id = async_result.id

    db.commit()

    for job in jobs_to_enqueue:
        doc = docs_by_job_id[str(job.id)]
        jobs_out.append(
            JobListItemOut(
                job=JobOut(
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
                    document={
                        "id": str(doc.id),
                        "original_filename": doc.original_filename,
                        "mime_type": doc.mime_type,
                        "size_bytes": doc.size_bytes,
                        "storage_path": doc.storage_path,
                    },
                ),
                filename=doc.original_filename,
                size_bytes=doc.size_bytes,
                mime_type=doc.mime_type,
                created_at=job.created_at,
            )
        )

    return UploadResponse(jobs=jobs_out)

