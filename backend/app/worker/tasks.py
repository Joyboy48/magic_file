from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Document, Job
from app.services.extraction import extract_from_text, read_text_preview, should_fail
from app.utils.redis_pubsub import publish_job_event
from app.worker.celery_app import celery_app


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@celery_app.task(name="app.worker.tasks.process_job", bind=True)
def process_job(self, job_id: str) -> None:
    db = SessionLocal()
    job_uuid = uuid.UUID(job_id)

    try:
        job = db.get(Job, job_uuid)
        if job is None:
            return

        doc = db.get(Document, job.document_id)
        if doc is None:
            raise RuntimeError("Document not found for job.")

        # job_started
        job.status = "processing"
        job.started_at = _now_utc()
        job.error_message = None
        job.stage = "job_started"
        job.progress_percent = 5
        publish_job_event(
            job_id=job_id,
            event_type="job_started",
            stage="job_started",
            progress_percent=job.progress_percent,
            payload={},
        )
        db.commit()

        # document_parsing_started
        job.stage = "document_parsing_started"
        job.progress_percent = 15
        publish_job_event(
            job_id=job_id,
            event_type="document_parsing_started",
            stage=job.stage,
            progress_percent=job.progress_percent,
        )
        db.commit()
        time.sleep(0.4)

        if should_fail(doc.original_filename):
            raise RuntimeError("Simulated failure requested by filename (contains 'fail').")

        # Simulated "parsing": read text preview
        text_preview = read_text_preview(doc.storage_path)
        time.sleep(0.4)

        # document_parsing_completed
        job.stage = "document_parsing_completed"
        job.progress_percent = 35
        publish_job_event(
            job_id=job_id,
            event_type="document_parsing_completed",
            stage=job.stage,
            progress_percent=job.progress_percent,
            payload={"preview_chars": len(text_preview)},
        )
        db.commit()

        # field_extraction_started
        job.stage = "field_extraction_started"
        job.progress_percent = 45
        publish_job_event(
            job_id=job_id,
            event_type="field_extraction_started",
            stage=job.stage,
            progress_percent=job.progress_percent,
        )
        db.commit()
        time.sleep(0.4)

        # Simulated extraction -> structured JSON
        extracted = extract_from_text(
            filename=doc.original_filename,
            file_type=doc.mime_type,
            size_bytes=doc.size_bytes,
            text=text_preview or "",
        )
        time.sleep(0.4)

        # field_extraction_completed
        job.stage = "field_extraction_completed"
        job.progress_percent = 75
        publish_job_event(
            job_id=job_id,
            event_type="field_extraction_completed",
            stage=job.stage,
            progress_percent=job.progress_percent,
            payload={"extracted_fields": list(extracted.keys())},
        )
        db.commit()

        # final result stored
        job.extracted_json = extracted
        # Pre-fill reviewed JSON so the UI can start editing immediately.
        job.reviewed_json = extracted
        job.stage = "final_result_stored"
        job.progress_percent = 90
        publish_job_event(
            job_id=job_id,
            event_type="final_result_stored",
            stage=job.stage,
            progress_percent=job.progress_percent,
        )
        db.commit()
        time.sleep(0.2)

        # job completed
        job.status = "completed"
        job.stage = "job_completed"
        job.progress_percent = 100
        job.completed_at = _now_utc()
        publish_job_event(
            job_id=job_id,
            event_type="job_completed",
            stage=job.stage,
            progress_percent=job.progress_percent,
            payload={},
        )
        db.commit()

    except Exception as e:
        # job_failed
        job = db.get(Job, job_uuid)
        if job is not None:
            job.status = "failed"
            job.stage = "job_failed"
            job.error_message = str(e)
            job.completed_at = _now_utc()
            job.progress_percent = 100
            publish_job_event(
                job_id=job_id,
                event_type="job_failed",
                stage=job.stage,
                progress_percent=job.progress_percent,
                payload={"error": str(e)},
            )
            db.commit()
        raise
    finally:
        db.close()

